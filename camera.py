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


# Qizil rang - GRIPPER BELGISI uchun (kalibrlashda ishlatiladi)
RED_HSV_LOWER_1 = np.array([0, 120, 70])
RED_HSV_UPPER_1 = np.array([10, 255, 255])
RED_HSV_LOWER_2 = np.array([170, 120, 70])
RED_HSV_UPPER_2 = np.array([180, 255, 255])

# Ko'k rang - USHLANADIGAN PREDMET uchun (pick&place'da ishlatiladi)
# MUHIM: gripper belgisi bilan bir xil rang ISHLATMANG - ikkalasi bir vaqtda
# kadrda bo'lganda dastur qaysi biri "nishon" ekanini adashtirib qo'yishi mumkin.
BLUE_HSV_LOWER = np.array([100, 120, 70])
BLUE_HSV_UPPER = np.array([130, 255, 255])

MIN_CONTOUR_AREA = 300  # piksel - bundan kichik dog'lar shovqin deb hisoblanadi


def _detect_color(frame, lower_ranges):
    """Berilgan HSV oralig'(lar)i bo'yicha eng katta dog'ni topadi."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = None
    for lower, upper in lower_ranges:
        m = cv2.inRange(hsv, lower, upper)
        mask = m if mask is None else cv2.bitwise_or(mask, m)

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


def detect_red_object(frame):
    """GRIPPER belgisini (qizil) topadi - kalibrlash uchun."""
    return _detect_color(frame, [(RED_HSV_LOWER_1, RED_HSV_UPPER_1), (RED_HSV_LOWER_2, RED_HSV_UPPER_2)])


def detect_blue_object(frame):
    """USHLANADIGAN PREDMETNI (ko'k) topadi - pick&place uchun."""
    return _detect_color(frame, [(BLUE_HSV_LOWER, BLUE_HSV_UPPER)])
