"""
RoboLab AI - Vision Pick and Place (avtomatik)
---------------------------------------------------
Kamera orqali qizil predmetni topadi, kalibrlash xaritasi yordamida
uning shoulder_pan/shoulder_lift burchaklarini hisoblaydi, so'ng
approach_pick/pick pozitsiyalaridagi qolgan jointlarni (elbow_flex,
wrist_flex, wrist_roll) andoza sifatida olib, to'liq pick&place
sinariysini avtomatik bajaradi.

TAXMIN (MVP cheklovi): predmet doim bir xil balandlikdagi tekis
stol yuzasida deb faraz qilinadi (depth kamera yo'q). Qo'yish nuqtasi
hozircha statik 'place'/'approach_place' pozitsiyalarida qoladi.

Talab: avval calibrate_vision.py orqali config/vision_calibration.yaml
yaratilgan bo'lishi kerak.

Ishga tushirish: python vision_pick_and_place.py
"""

import logging
import time
import yaml
import cv2

from joint_controller import JointController
from home_position import go_home
from gripper import Gripper, GRIPPER_JOINT
from camera import Camera, detect_red_object

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("motion.log")],
)
logger = logging.getLogger("robolab.vision_pick_place")

CALIBRATION_PATH = "config/vision_calibration.yaml"
POSES_PATH = "config/poses.yaml"
MOVE_SPEED = 250
SETTLE_S = 1.2


def load_calibration() -> dict:
    try:
        with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"{CALIBRATION_PATH} topilmadi. Avval 'python calibrate_vision.py' "
            f"orqali kamerani kalibrlang."
        )


def load_poses() -> dict:
    with open(POSES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pixel_to_angles(u: int, v: int, calibration: dict) -> tuple:
    a, b, c = calibration["pan_coef"]
    d, e, f = calibration["lift_coef"]
    pan = a * u + b * v + c
    lift = d * u + e * v + f
    return pan, lift


def build_vision_pose(base_pose: dict, pan: float, lift: float) -> dict:
    """Andoza pozitsiyadan elbow/wrist/gripper qiymatlarini oladi,
    faqat pan/lift'ni kamera hisoblagan qiymat bilan almashtiradi."""
    pose = dict(base_pose)
    pose["shoulder_pan"] = pan
    pose["shoulder_lift"] = lift
    return pose


def move_to_pose(controller: JointController, pose: dict, exclude=None) -> None:
    exclude = exclude or []
    for joint_name, deg in pose.items():
        if joint_name in exclude:
            continue
        if not controller.check_health(joint_name):
            raise RuntimeError(f"Safety check failed: {joint_name}")
        controller.set_position_deg(joint_name, deg, speed=MOVE_SPEED)
        time.sleep(0.15)
    time.sleep(SETTLE_S)


def find_object(camera: Camera, attempts: int = 15, delay_s: float = 0.2):
    """Bir necha marta urinib, predmetni kameradan topishga harakat qiladi
    (bitta kadr shovqinli bo'lishi mumkin - bir necha kadr o'rtachasi yaxshiroq)."""
    for _ in range(attempts):
        frame = camera.get_frame()
        found, uv, mask = detect_red_object(frame)
        cv2.imshow("RoboLab AI - Vision Pick&Place", frame)
        cv2.waitKey(1)
        if found:
            return uv
        time.sleep(delay_s)
    return None


def run_vision_pick_and_place(controller: JointController, poses: dict, calibration: dict, camera: Camera) -> bool:
    gripper = Gripper(controller)

    logger.info("=== VISION PICK & PLACE boshlandi ===")
    go_home(controller)
    gripper.open()

    logger.info("Predmet qidirilmoqda...")
    uv = find_object(camera)
    if uv is None:
        logger.error("Predmet topilmadi - kamera oldida qizil predmet borligini tekshiring.")
        return False

    pan, lift = pixel_to_angles(uv[0], uv[1], calibration)
    logger.info("Predmet topildi: piksel=%s -> shoulder_pan=%.1f, shoulder_lift(approach)=%.1f", uv, pan, lift)

    # EKSTRAPOLYATSIYA HIMOYASI: agar hisoblangan qiymat kalibrlash paytida
    # qamrab olingan diapazondan sezilarli uzoqda bo'lsa, natija ishonchsiz -
    # to'xtatamiz (chegaraga "kesib qo'yish" o'rniga, chunki bu ma'nosiz
    # harakatga olib kelishi mumkin - avvalgi sinovda ko'rilganidek).
    margin = 10.0  # gradus - kalibrlash chegarasidan qancha "kechirim" berilishi
    pan_range = calibration.get("pan_deg_range")
    lift_range = calibration.get("lift_deg_range")
    if pan_range and lift_range:
        if not (pan_range[0] - margin <= pan <= pan_range[1] + margin):
            logger.error(
                "Ekstrapolyatsiya xavfi: pan=%.1f kalibrlash diapazonidan [%.1f, %.1f] tashqarida. To'xtatildi.",
                pan, pan_range[0], pan_range[1]
            )
            return False
        if not (lift_range[0] - margin <= lift <= lift_range[1] + margin):
            logger.error(
                "Ekstrapolyatsiya xavfi: lift=%.1f kalibrlash diapazonidan [%.1f, %.1f] tashqarida. To'xtatildi.",
                lift, lift_range[0], lift_range[1]
            )
            return False

    # MUHIM: kalibrlash 'approach_pick' (yuqori, xavfsiz) balandlikda avtonom
    # skanerlash orqali olingan - shuning uchun hisoblangan (pan, lift) approach
    # balandligini ifodalaydi. Pastga tushish (pick) uchun shu farqni ayiramiz.
    lift_offset = poses["approach_pick"]["shoulder_lift"] - poses["pick"]["shoulder_lift"]

    vision_approach = build_vision_pose(poses["approach_pick"], pan, lift)
    vision_pick = build_vision_pose(poses["pick"], pan, lift - lift_offset)

    logger.info("--- vision_approach ---")
    move_to_pose(controller, vision_approach, exclude=[GRIPPER_JOINT])

    logger.info("--- vision_pick ---")
    move_to_pose(controller, vision_pick, exclude=[GRIPPER_JOINT])
    holding = gripper.close()

    if not holding:
        logger.warning("Gripper hech narsa ushlamagandek ko'rinadi (load past).")

    logger.info("--- ko'tarilish ---")
    move_to_pose(controller, vision_approach, exclude=[GRIPPER_JOINT])

    logger.info("--- approach_place (statik) ---")
    move_to_pose(controller, poses["approach_place"], exclude=[GRIPPER_JOINT])

    logger.info("--- place (statik) ---")
    move_to_pose(controller, poses["place"], exclude=[GRIPPER_JOINT])
    gripper.open()

    logger.info("--- ko'tarilish va home ---")
    move_to_pose(controller, poses["approach_place"], exclude=[GRIPPER_JOINT])
    go_home(controller)

    logger.info("=== VISION PICK & PLACE yakunlandi: holding=%s ===", holding)
    return holding


if __name__ == "__main__":
    calibration = load_calibration()
    poses = load_poses()
    controller = JointController()
    camera = Camera()
    try:
        controller.connect()
        success = run_vision_pick_and_place(controller, poses, calibration, camera)
        print(f"\nNatija: {'MUVAFFAQIYATLI' if success else 'OGOHLANTIRISH - tekshiring'}")
    except Exception as exc:
        logger.exception("Vision Pick&Place xatoligi: %s", exc)
    finally:
        cv2.destroyAllWindows()
        camera.release()
        controller.disconnect()
