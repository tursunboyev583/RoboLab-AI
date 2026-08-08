"""
RoboLab AI - Camera Layer
----------------------------
USB webcam orqali kadr olish va rang bo'yicha predmetni aniqlash.

MVP bosqichida oddiy HSV rang chegarasi ishlatiladi (YOLO hali yo'q -
bu roadmapda alohida, murakkabroq predmetlar uchun keyingi bosqich).

Talab: pip install opencv-python numpy
"""

import os
import cv2
import numpy as np
import yaml

CAMERA_CONFIG_PATH = "config/camera_config.yaml"


def _default_camera_index() -> int:
    """find_camera.py orqali saqlangan indexni o'qiydi, topilmasa 0 qaytaradi."""
    if os.path.exists(CAMERA_CONFIG_PATH):
        with open(CAMERA_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            return cfg.get("camera_index", 0)
    return 0


class Camera:
    def __init__(self, index: int = None, width: int = 640, height: int = 480):
        if index is None:
            index = _default_camera_index()
        self.index = index
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # Windows uchun DSHOW tezroq ochiladi
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Kamera (index={index}) ochilmadi - USB ulanishini tekshiring, "
                f"yoki 'python find_camera.py' orqali to'g'ri indexni qayta toping."
            )

    def get_frame(self):
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Kameradan kadr olib bo'lmadi")
        return frame

    def release(self):
        self.cap.release()


# Qizil rang uchun ikkita HSV oralig'i (qizil rang HSV doirasining ham
# boshida, ham oxirida joylashadi, shuning uchun ikkita diapazon kerak)
RED_HSV_LOWER_1 = np.array([0, 120, 70])
RED_HSV_UPPER_1 = np.array([10, 255, 255])
RED_HSV_LOWER_2 = np.array([170, 120, 70])
RED_HSV_UPPER_2 = np.array([180, 255, 255])

MIN_CONTOUR_AREA = 300  # piksel - bundan kichik dog'lar shovqin deb hisoblanadi


def detect_red_object(frame):
    """
    Kadrdan eng katta qizil predmetni topadi.
    Qaytaradi: (topildimi: bool, (u, v): markaz piksel koordinatasi, mask: vizualizatsiya uchun)
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, RED_HSV_LOWER_1, RED_HSV_UPPER_1)
    mask2 = cv2.inRange(hsv, RED_HSV_LOWER_2, RED_HSV_UPPER_2)
    mask = cv2.bitwise_or(mask1, mask2)

    # Kichik shovqinlarni tozalash
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, None, mask

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < MIN_CONTOUR_AREA:
        return False, None, mask

    M = cv2.moments(largest)
    if M["m00"] == 0:
        return False, None, mask

    u = int(M["m10"] / M["m00"])
    v = int(M["m01"] / M["m00"])
    return True, (u, v), mask
