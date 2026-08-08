"""
RoboLab AI - Avtonom Vision Calibration
--------------------------------------------
Robot O'ZI shoulder_pan/shoulder_lift panjarasi (grid) bo'ylab avtomatik
harakatlanadi. Har bir nuqtada gripper uchidagi QIZIL BELGI kamerada
qidiriladi va topilsa (piksel, pan, lift) juftligi yoziladi. Inson
aralashuvisiz - bu haqiqiy "hand-eye calibration" texnikasi.

TALAB: gripper uchiga kichik qizil belgi (skotch/qog'oz) yopishtirilgan
bo'lishi kerak - kamera aynan shuni kuzatadi.

Xavfsizlik: elbow_flex/wrist_flex/wrist_roll butun skanerlash davomida
'approach_pick' andozasidagi qiymatlarda QOTIB turadi (stol sathidan
yuqorida, hech narsaga tegmaydi) - faqat pan/lift o'zgaradi.

Ishga tushirish: python calibrate_vision_auto.py
"""

import time
import yaml
import numpy as np
import cv2

from joint_controller import JointController
from camera import Camera, detect_red_object

import argparse

CALIBRATION_PATH = "config/vision_calibration.yaml"
POSES_PATH = "config/poses.yaml"
MOVE_SPEED = 200
SETTLE_S = 0.9
FRAMES_PER_POINT = 5          # bir nuqtada bir necha kadr o'rtachasi - shovqinni kamaytiradi

# Panjara parametrlari - DEFAULT qiymatlar (buyruq qatoridan o'zgartirish mumkin)
PAN_SPAN_DEG = 12.0
LIFT_SPAN_DEG = 10.0
GRID_STEPS = 6                 # 6x6 = 36 nuqta (zichroq, kichikroq maydon)


def load_poses() -> dict:
    with open(POSES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def detect_marker_averaged(camera: Camera, n_frames: int):
    """Bir nechta kadr o'rtachasini olib, shovqinni kamaytiradi."""
    found_points = []
    last_frame = None
    for _ in range(n_frames):
        frame = camera.get_frame()
        last_frame = frame
        found, uv, _ = detect_red_object(frame)
        if found:
            found_points.append(uv)
        cv2.imshow("RoboLab AI - Avtonom Kalibrlash", frame)
        cv2.waitKey(1)
        time.sleep(0.05)

    if len(found_points) < n_frames // 2 + 1:
        return None  # ko'p kadrlarda topilmadi - noishonchli, o'tkazib yuboriladi

    arr = np.array(found_points)
    u = int(np.median(arr[:, 0]))
    v = int(np.median(arr[:, 1]))
    return (u, v)


def main():
    parser = argparse.ArgumentParser(description="RoboLab AI - Avtonom Vision Calibration")
    parser.add_argument("--pan-span", type=float, default=PAN_SPAN_DEG,
                         help="Pan uchun markazdan necha gradus atrofda skanerlash (default: %(default)s)")
    parser.add_argument("--lift-span", type=float, default=LIFT_SPAN_DEG,
                         help="Lift uchun markazdan necha gradus atrofda skanerlash (default: %(default)s)")
    parser.add_argument("--grid-steps", type=int, default=GRID_STEPS,
                         help="Panjara zichligi (NxN), default: %(default)s")
    parser.add_argument("--center-pan", type=float, default=None,
                         help="Markaziy pan qiymati (default: approach_pick pose'idan olinadi)")
    parser.add_argument("--center-lift", type=float, default=None,
                         help="Markaziy lift qiymati (default: approach_pick pose'idan olinadi)")
    args = parser.parse_args()

    poses = load_poses()
    if "approach_pick" not in poses:
        print("XATO: avval 'approach_pick' pozitsiyasini record_pose.py orqali yozing.")
        return

    template = poses["approach_pick"]
    center_pan = args.center_pan if args.center_pan is not None else template["shoulder_pan"]
    center_lift = args.center_lift if args.center_lift is not None else template["shoulder_lift"]

    controller = JointController()
    controller.connect()
    camera = Camera()

    print("Boshlang'ich holatga (approach_pick) o'tilmoqda...")
    for name, deg in template.items():
        controller.set_position_deg(name, deg, speed=MOVE_SPEED)
        time.sleep(0.15)
    time.sleep(1.0)

    pan_values = np.linspace(center_pan - args.pan_span, center_pan + args.pan_span, args.grid_steps)
    lift_values = np.linspace(center_lift - args.lift_span, center_lift + args.lift_span, args.grid_steps)

    collected_points = []
    total = len(pan_values) * len(lift_values)
    count = 0

    print(f"Avtonom skanerlash boshlandi: {total} nuqta ({GRID_STEPS}x{GRID_STEPS} grid)")
    print("Kamera oynasida 'Q' bosib to'xtatishingiz mumkin.\n")

    try:
        for pan in pan_values:
            for lift in lift_values:
                count += 1

                if not controller.check_health("shoulder_pan") or not controller.check_health("shoulder_lift"):
                    print("Xavfsizlik tekshiruvi muvaffaqiyatsiz - to'xtatildi.")
                    break

                controller.set_position_deg("shoulder_pan", float(pan), speed=MOVE_SPEED)
                controller.set_position_deg("shoulder_lift", float(lift), speed=MOVE_SPEED)
                time.sleep(SETTLE_S)

                uv = detect_marker_averaged(camera, FRAMES_PER_POINT)

                if uv is not None:
                    collected_points.append((uv[0], uv[1], pan, lift))
                    status = f"TOPILDI piksel={uv}"
                else:
                    status = "o'tkazib yuborildi (belgi ko'rinmadi)"

                print(f"[{count}/{total}] pan={pan:.1f} lift={lift:.1f} -> {status}")

                # 'Q' bosilsa to'xtatish imkoniyati
                if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q'), 27):
                    print("Foydalanuvchi tomonidan to'xtatildi.")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\nSkanerlash to'xtatildi, yig'ilgan nuqtalar bilan davom etiladi.")

    print(f"\nJami yig'ilgan nuqtalar: {len(collected_points)}/{total}")

    if len(collected_points) < 3:
        print("Kamida 3 nuqta kerak - kalibrlash saqlanmadi. Yorug'lik/belgi holatini tekshiring.")
    else:
        pts = np.array(collected_points)
        U, V = pts[:, 0], pts[:, 1]
        SP, SL = pts[:, 2], pts[:, 3]
        A_design = np.column_stack([U, V, np.ones_like(U)])
        coef_pan, _, _, _ = np.linalg.lstsq(A_design, SP, rcond=None)
        coef_lift, _, _, _ = np.linalg.lstsq(A_design, SL, rcond=None)

        pred_pan = A_design @ coef_pan
        pred_lift = A_design @ coef_lift
        err_pan = np.abs(pred_pan - SP).max()
        err_lift = np.abs(pred_lift - SL).max()
        print(f"Fit xatosi: pan max={err_pan:.2f} grad, lift max={err_lift:.2f} grad")

        calibration = {
            "pan_coef": [float(x) for x in coef_pan],
            "lift_coef": [float(x) for x in coef_lift],
            "num_points": len(collected_points),
            "pan_deg_range": [float(SP.min()), float(SP.max())],
            "lift_deg_range": [float(SL.min()), float(SL.max())],
        }
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            yaml.dump(calibration, f)
        print(f"Kalibrlash saqlandi -> {CALIBRATION_PATH}")

    print("\nBoshlang'ich holatga qaytilmoqda...")
    for name, deg in template.items():
        controller.set_position_deg(name, deg, speed=MOVE_SPEED)
        time.sleep(0.15)

    cv2.destroyAllWindows()
    camera.release()
    controller.disconnect()
    print("Yakunlandi.")


if __name__ == "__main__":
    main()
