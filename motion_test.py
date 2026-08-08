"""
RoboLab AI - Motion Test
--------------------------
Kun 1 maqsadi: har bir joint alohida sekin harakat qilishi va
qaytadan home holatga qaytishini tasdiqlash.

Bu MVP uchun birinchi "smoke test" - agar bu skript muvaffaqiyatli
o'tsa, ertangi kun (Gripper, Pick&Place) uchun poydevor tayyor.

Ishga tushirish: python motion_test.py
"""

import logging
import time

from joint_controller import JointController
from home_position import go_home

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("motion.log")],
)
logger = logging.getLogger("robolab.motion_test")

# Har bir joint uchun kichik, xavfsiz test harakati (home'dan +15 grad)
TEST_OFFSET_DEG = 15
TEST_SPEED = 200


def test_single_joint(controller: JointController, name: str) -> bool:
    joint = controller.joints[name]

    # Joint diapazonning qaysi chetiga yaqinroq ekanini aniqlaymiz va
    # ko'proq joy bor tomonga xavfsiz siljiymiz (chegarada turgan
    # jointlar - masalan gripper, shoulder_lift - uchun ham to'g'ri ishlaydi)
    margin_up = joint.max_deg - joint.home_deg
    margin_down = joint.home_deg - joint.min_deg

    if margin_up >= margin_down:
        offset = min(TEST_OFFSET_DEG, margin_up)
    else:
        offset = -min(TEST_OFFSET_DEG, margin_down)

    if abs(offset) < 2.0:
        logger.warning("%s: diapazon juda tor (%.1f grad), test o'tkazib yuborildi", name, abs(offset))
        return True

    target = joint.home_deg + offset

    logger.info("TEST boshlandi: %s (offset=%.1f)", name, offset)
    controller.set_position_deg(name, target, speed=TEST_SPEED)
    time.sleep(1.5)  # servoga "tinchlanish" uchun ko'proq vaqt (og'ir yuk ostidagi jointlar uchun)

    actual = controller.get_position_deg(name)
    error = abs(actual - target)

    if error > 5.0:  # 5 gradusdan katta xato - muammo bor
        logger.error("%s: kutilgan %.1f, haqiqiy %.1f (xato %.1f grad)", name, target, actual, error)
        return False

    controller.set_position_deg(name, joint.home_deg, speed=TEST_SPEED)
    time.sleep(1.0)
    logger.info("TEST muvaffaqiyatli: %s (xato %.1f grad)", name, error)
    return True


def run_all_tests(controller: JointController) -> dict:
    results = {}
    for name in controller.joints:
        try:
            results[name] = test_single_joint(controller, name)
        except Exception as exc:
            logger.exception("%s testida xatolik: %s", name, exc)
            results[name] = False
    return results


if __name__ == "__main__":
    controller = JointController()
    try:
        controller.connect()
        go_home(controller)  # avval xavfsiz boshlang'ich holat
        results = run_all_tests(controller)
        go_home(controller)  # test yakunida yana home

        passed = sum(results.values())
        total = len(results)
        logger.info("=== NATIJA: %d/%d joint testdan o'tdi ===", passed, total)
        for name, ok in results.items():
            status = "OK" if ok else "XATO"
            logger.info("  %s: %s", name, status)
    except Exception as exc:
        logger.exception("Motion test umumiy xatolik: %s", exc)
    finally:
        controller.disconnect()
