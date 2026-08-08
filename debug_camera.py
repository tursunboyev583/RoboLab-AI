"""
RoboLab AI - Kamera Diagnostika Vositasi
--------------------------------------------
Kamera nimani ko'rayotganini va aniqlash maskasini ko'rsatadi.
Sichqoncha bilan istalgan nuqtani bossangiz, o'sha nuqtaning HSV
qiymati konsolga chiqadi - shu orqali qizil belgingizning haqiqiy
HSV oralig'ini topib, camera.py dagi chegaralarni to'g'rilash mumkin.

Ishga tushirish: python debug_camera.py
Tugmalar: Q yoki ESC - chiqish
"""

import cv2
import numpy as np

from camera import Camera, detect_red_object, RED_HSV_LOWER_1, RED_HSV_UPPER_1, RED_HSV_LOWER_2, RED_HSV_UPPER_2

clicked_hsv = None


def on_mouse(event, x, y, flags, param):
    global clicked_hsv
    if event == cv2.EVENT_LBUTTONDOWN:
        hsv_frame = param
        h, s, v = hsv_frame[y, x]
        clicked_hsv = (int(h), int(s), int(v))
        print(f"Bosilgan nuqta HSV: H={h} S={s} V={v}  (piksel: {x},{y})")


def main():
    camera = Camera()
    cv2.namedWindow("Original (bosing - HSV ko'rish uchun)")
    cv2.namedWindow("Mask (nima 'qizil' deb topilmoqda)")

    print("Kamera oynasi ochildi.")
    print("Qizil belgingizga sichqoncha bilan bosing - HSV qiymati shu yerda chiqadi.")
    print("Q yoki ESC - chiqish\n")

    try:
        while True:
            frame = camera.get_frame()
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            cv2.setMouseCallback("Original (bosing - HSV ko'rish uchun)", on_mouse, hsv)

            found, uv, mask = detect_red_object(frame)

            display = frame.copy()
            if found:
                cv2.circle(display, uv, 10, (0, 255, 0), 2)
                cv2.putText(display, "TOPILDI", (uv[0] + 12, uv[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(display, "TOPILMADI", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            if clicked_hsv:
                cv2.putText(display, f"Oxirgi bosilgan HSV: {clicked_hsv}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            cv2.imshow("Original (bosing - HSV ko'rish uchun)", display)
            cv2.imshow("Mask (nima 'qizil' deb topilmoqda)", mask)

            key = cv2.waitKey(30) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                break
    finally:
        cv2.destroyAllWindows()
        camera.release()


if __name__ == "__main__":
    main()
