"""
RoboLab AI - Vision Calibration
-----------------------------------
Kamera piksel koordinatasi (u, v) bilan robot burchaklari
(shoulder_pan, shoulder_lift) orasidagi chiziqli bog'liqlikni topadi.

MUHIM (tuzatilgan versiya): boshqaruv endi konsol input() o'rniga
TO'G'RIDAN-TO'G'RI kamera oynasidagi klaviatura tugmalari orqali
amalga oshiriladi. Bu oynani "javob bermayapti" holatidan saqlaydi,
chunki endi hech qachon uzoq vaqt bloklovchi input() chaqirilmaydi -
har bir sikl doim yangi kadr o'qiydi va oynani yangilaydi.

Boshqaruv tugmalari (kamera oynasi FOKUSDA bo'lganda bosing):
  A / D     -> shoulder_pan  -1 / +1 grad
  W / S     -> shoulder_lift +1 / -1 grad
  SHIFT+A/D -> shoulder_pan  -0.2 / +0.2 grad (nozik)
  SHIFT+W/S -> shoulder_lift +0.2 / -0.2 grad (nozik)
  C         -> joriy nuqtani yozib olish (capture)
  F         -> yig'ilgan nuqtalar bo'yicha xaritalashni hisoblash va saqlash
  Q / ESC   -> chiqish

Ishga tushirish: python calibrate_vision.py
"""

import time
import yaml
import numpy as np
import cv2

from joint_controller import JointController
from camera import Camera, detect_red_object

CALIBRATION_PATH = "config/vision_calibration.yaml"
POSES_PATH = "config/poses.yaml"
JOG_SPEED = 150

STEP_COARSE = 1.0
STEP_FINE = 0.2


def load_poses() -> dict:
    with open(POSES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def draw_overlay(frame, found, uv, num_points, sp, sl, msg=""):
    display = frame.copy()
    if found:
        cv2.circle(display, uv, 8, (0, 255, 0), -1)
        cv2.putText(display, f"{uv}", (uv[0] + 10, uv[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    else:
        cv2.putText(display, "PREDMET TOPILMADI", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    lines = [
        f"Nuqtalar: {num_points}   pan={sp:.1f}  lift={sl:.1f}",
        "A/D=pan  W/S=lift  (Shift=nozik)  C=capture  F=fit  Q=chiqish",
        msg,
    ]
    for i, line in enumerate(lines):
        cv2.putText(display, line, (10, 30 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return display


def main():
    poses = load_poses()
    if "pick" not in poses or "approach_pick" not in poses:
        print("XATO: avval 'pick' va 'approach_pick' pozitsiyalarini record_pose.py orqali yozing.")
        return

    controller = JointController()
    controller.connect()
    camera = Camera()

    print("'pick' pozitsiyasiga o'tilmoqda...")
    for name, deg in poses["pick"].items():
        controller.set_position_deg(name, deg, speed=JOG_SPEED)
        time.sleep(0.15)
    time.sleep(1.0)

    collected_points = []
    msg = "Tayyor. Kamera oynasini bosing (fokus), so'ng tugmalarni ishlating."

    cv2.namedWindow("RoboLab AI - Kalibrlash", cv2.WINDOW_NORMAL)

    try:
        while True:
            frame = camera.get_frame()
            found, uv, mask = detect_red_object(frame)
            sp = controller.get_position_deg("shoulder_pan")
            sl = controller.get_position_deg("shoulder_lift")

            display = draw_overlay(frame, found, uv, len(collected_points), sp, sl, msg)
            cv2.imshow("RoboLab AI - Kalibrlash", display)

            key = cv2.waitKey(30) & 0xFF
            msg = ""

            if key == 255:  # tugma bosilmadi
                continue
            elif key in (ord('q'), ord('Q'), 27):  # ESC
                break
            elif key in (ord('c'), ord('C')):
                if not found:
                    msg = "Predmet topilmadi - capture bekor qilindi."
                else:
                    collected_points.append((uv[0], uv[1], sp, sl))
                    msg = f"Yozildi: piksel={uv}, pan={sp:.2f}, lift={sl:.2f}"
            elif key in (ord('f'), ord('F')):
                if len(collected_points) < 3:
                    msg = f"Kamida 3 nuqta kerak (hozir {len(collected_points)})."
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

                    calibration = {
                        "pan_coef": [float(x) for x in coef_pan],
                        "lift_coef": [float(x) for x in coef_lift],
                        "num_points": len(collected_points),
                    }
                    with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
                        yaml.dump(calibration, f)
                    msg = f"SAQLANDI. Xato: pan={err_pan:.2f} lift={err_lift:.2f} grad"
                    print(msg)
            elif key in (ord('d'), ord('a'), ord('w'), ord('s')):
                # kichik harf = coarse, katta harf (Shift) = fine
                delta = STEP_COARSE
                sign_map = {'d': 1, 'a': -1, 'w': 1, 's': -1}
                ch = chr(key)
                joint = "shoulder_pan" if ch in ('d', 'a') else "shoulder_lift"
                new_val = (sp if joint == "shoulder_pan" else sl) + sign_map[ch] * delta
                controller.set_position_deg(joint, new_val, speed=JOG_SPEED)
            elif key in (ord('D'), ord('A'), ord('W'), ord('S')):
                delta = STEP_FINE
                sign_map = {'D': 1, 'A': -1, 'W': 1, 'S': -1}
                ch = chr(key)
                joint = "shoulder_pan" if ch in ('D', 'A') else "shoulder_lift"
                new_val = (sp if joint == "shoulder_pan" else sl) + sign_map[ch] * delta
                controller.set_position_deg(joint, new_val, speed=JOG_SPEED)

    finally:
        cv2.destroyAllWindows()
        camera.release()
        controller.disconnect()
        print("Yakunlandi.")


if __name__ == "__main__":
    main()
