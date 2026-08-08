"""
RoboLab AI - Home Position
----------------------------
Manipulyatorni xavfsiz "home" holatiga qaytaradi.
Bu skript har bir sessiya boshida va yakunida ishga tushirilishi kerak
(demo, test, kalibrlash - hammasi shu holatdan boshlanadi).

Ishga tushirish: python home_position.py
"""

import logging
import time

from joint_controller import JointController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("motion.log"),  # elektron jurnal prototipi
    ],
)
logger = logging.getLogger("robolab.home")

# Xavfsizlik uchun: barcha jointlar bitta vaqtda emas, ketma-ket,
# sekin tezlikda home holatga qaytariladi (MVP bosqichida qulash xavfini kamaytiradi)
HOME_ORDER = ["gripper", "wrist_roll", "wrist_flex", "elbow_flex", "shoulder_lift", "shoulder_pan"]
HOME_SPEED = 300  # sekin, xavfsiz tezlik


def go_home(controller: JointController) -> None:
    logger.info("=== HOME POSITION boshlandi ===")
    for name in HOME_ORDER:
        joint = controller.joints[name]

        if not controller.check_health(name):
            logger.error("Xavfsizlik tekshiruvi muvaffaqiyatsiz: %s. To'xtatildi.", name)
            raise RuntimeError(f"Safety check failed for {name}")

        controller.set_position_deg(name, joint.home_deg, speed=HOME_SPEED)
        time.sleep(0.5)  # servolar orasida qisqa pauza

    logger.info("=== HOME POSITION yakunlandi: barcha jointlar 0 holatda ===")


if __name__ == "__main__":
    controller = JointController()
    try:
        controller.connect()
        go_home(controller)
    except Exception as exc:
        logger.exception("Home position xatoligi: %s", exc)
    finally:
        controller.disconnect()
