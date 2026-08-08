"""
RoboLab AI - Pick and Place (MVP Demo Scenario)
---------------------------------------------------
Bugungi (3-avgust) maqsad: home -> approach_pick -> pick -> lift ->
approach_place -> place -> home ketma-ketligini bajarish.

Talab qilinadigan pose'lar config/poses.yaml faylida oldindan
record_pose.py orqali yozilgan bo'lishi kerak:
  - approach_pick   (olinadigan narsa ustida, biroz yuqorida)
  - pick             (narsani ushlash uchun pastroq holat)
  - approach_place   (qo'yiladigan joy ustida, biroz yuqorida)
  - place             (narsani qo'yish uchun pastroq holat)

Ishga tushirish: python pick_and_place.py
"""

import logging
import os
import time

import yaml

from joint_controller import JointController
from home_position import go_home
from gripper import Gripper, GRIPPER_JOINT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("motion.log")],
)
logger = logging.getLogger("robolab.pick_place")

POSES_PATH = "config/poses.yaml"
MOVE_SPEED = 250
SETTLE_S = 1.2

REQUIRED_POSES = ["approach_pick", "pick", "approach_place", "place"]


def load_poses() -> dict:
    if not os.path.exists(POSES_PATH):
        raise FileNotFoundError(
            f"{POSES_PATH} topilmadi. Avval 'python record_pose.py' orqali "
            f"kerakli pozitsiyalarni yozib oling: {REQUIRED_POSES}"
        )
    with open(POSES_PATH, "r", encoding="utf-8") as f:
        poses = yaml.safe_load(f) or {}

    missing = [p for p in REQUIRED_POSES if p not in poses]
    if missing:
        raise ValueError(
            f"Quyidagi pose'lar yetishmayapti: {missing}. "
            f"'python record_pose.py' orqali yozib oling."
        )
    return poses


def move_to_pose(controller: JointController, pose: dict, exclude: list = None) -> None:
    """Berilgan pose'dagi barcha jointlarni (gripperdan tashqari, agar exclude
    berilmasa) shu holatga harakatlantiradi."""
    exclude = exclude or []
    for joint_name, deg in pose.items():
        if joint_name in exclude:
            continue
        if not controller.check_health(joint_name):
            raise RuntimeError(f"Safety check failed: {joint_name}")
        controller.set_position_deg(joint_name, deg, speed=MOVE_SPEED)
        time.sleep(0.15)  # jointlar orasida qisqa pauza
    time.sleep(SETTLE_S)


def run_pick_and_place(controller: JointController, poses: dict) -> bool:
    gripper = Gripper(controller)

    logger.info("=== PICK & PLACE boshlandi ===")

    # 1. Xavfsiz boshlang'ich holat
    go_home(controller)
    gripper.open()

    # 2. Olish nuqtasi ustiga yaqinlashish (gripperni bu bosqichda o'zgartirmaymiz)
    logger.info("--- approach_pick ---")
    move_to_pose(controller, poses["approach_pick"], exclude=[GRIPPER_JOINT])

    # 3. Pastga tushish va ushlash
    logger.info("--- pick ---")
    move_to_pose(controller, poses["pick"], exclude=[GRIPPER_JOINT])
    holding = gripper.close()

    if not holding:
        logger.warning(
            "Gripper hech narsa ushlamagandek ko'rinadi (load past). "
            "Baribir davom etiladi - MVP bosqichida bu faqat ogohlantirish."
        )

    # 4. Xavfsiz balandlikka ko'tarilish (to'qnashuvdan saqlanish uchun)
    logger.info("--- approach_pick (ko'tarilish) ---")
    move_to_pose(controller, poses["approach_pick"], exclude=[GRIPPER_JOINT])

    # 5. Qo'yish nuqtasi ustiga yaqinlashish
    logger.info("--- approach_place ---")
    move_to_pose(controller, poses["approach_place"], exclude=[GRIPPER_JOINT])

    # 6. Pastga tushish va qo'yish
    logger.info("--- place ---")
    move_to_pose(controller, poses["place"], exclude=[GRIPPER_JOINT])
    gripper.open()

    # 7. Xavfsiz balandlikka qaytish va home
    logger.info("--- approach_place (ko'tarilish) ---")
    move_to_pose(controller, poses["approach_place"], exclude=[GRIPPER_JOINT])
    go_home(controller)

    logger.info("=== PICK & PLACE yakunlandi: holding=%s ===", holding)
    return holding


if __name__ == "__main__":
    poses = load_poses()
    controller = JointController()
    try:
        controller.connect()
        success = run_pick_and_place(controller, poses)
        print(f"\nNatija: {'MUVAFFAQIYATLI (narsa ushlangan)' if success else 'OGOHLANTIRISH (load past, tekshiring)'}")
    except Exception as exc:
        logger.exception("Pick&Place xatoligi: %s", exc)
    finally:
        controller.disconnect()
