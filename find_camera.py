"""
RoboLab AI - Kamera Aniqlash Vositasi
------------------------------------------
Kompyuteringizga ulangan barcha kameralarni (index 0, 1, 2, 3) birma-bir
ochib ko'rsatadi - shu orqali TASHQI USB kameraning to'g'ri indexini
topib, config/camera_config.yaml ga saqlash mumkin.

Ishga tushirish: python find_camera.py
Tugmalar: N - keyingi kamerani ko'rish, S - joriy indexni saqlash, Q - chiqish
"""

import cv2
import yaml

CAMERA_CONFIG_PATH = "config/camera_config.yaml"
MAX_INDEX_TO_CHECK = 5


def main():
    print("Kameralar tekshirilmoqda...\n")

    index = 0
    while index <= MAX_INDEX_TO_CHECK:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"[{index}] Kamera topilmadi yoki band.")
            cap.release()
            index += 1
            continue

        print(f"[{index}] Kamera ochildi. Oynani ko'ring:")
        print("       N - keyingi kamerani sinash")
        print("       S - SHU indexni saqlash va chiqish")
        print("       Q - saqlamasdan chiqish\n")

        while True:
            ok, frame = cap.read()
            if not ok:
                print(f"[{index}] Kadr o'qib bo'lmadi.")
                break

            display = frame.copy()
            cv2.putText(display, f"Kamera index: {index}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(display, "N=keyingi  S=saqlash  Q=chiqish", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow("RoboLab AI - Kamera Aniqlash", display)

            key = cv2.waitKey(30) & 0xFF
            if key in (ord('n'), ord('N')):
                break
            elif key in (ord('s'), ord('S')):
                with open(CAMERA_CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.dump({"camera_index": index}, f)
                print(f"\nSaqlandi: camera_index={index} -> {CAMERA_CONFIG_PATH}")
                cap.release()
                cv2.destroyAllWindows()
                return
            elif key in (ord('q'), ord('Q'), 27):
                cap.release()
                cv2.destroyAllWindows()
                print("Saqlamasdan chiqildi.")
                return

        cap.release()
        index += 1

    cv2.destroyAllWindows()
    print("\nBoshqa kamera topilmadi.")


if __name__ == "__main__":
    main()
