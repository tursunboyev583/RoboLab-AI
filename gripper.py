"""
RoboLab AI - Gripper Controller
---------------------------------
Gripper uchun yuqori darajadagi interfeys: open(), close(), is_holding().

MUHIM: hozircha maxsus Force Sensor yo'q (kelajakdagi hardware roadmapda
bor). Shuning uchun "narsa ushlanganini" aniqlash uchun STS-3215'ning
o'zidagi "Present Load" registridan foydalanamiz - agar gripper yopilayotganda
kutilgandan ko'proq moment (load) sezilsa, demak yo'lda biror narsa bor
(objekt ushlangan yoki gripper to'liq yopila olmagan). Bu - qo'shimcha
xarajatsiz, dasturiy "soft force sensing" yechimi. Force Sensor
o'rnatilgach, bu klass shu interfeysni saqlab, faqat ichki
implementatsiyasi yangilanadi (Task/Motion qatlamlariga ta'sir qilmaydi).
"""

import logging
import time

from joint_controller import JointController

logger = logging.getLogger("robolab.gripper")

GRIPPER_JOINT = "gripper"
LOAD_HOLDING_THRESHOLD_PERCENT = 15.0   # shu qiymatdan yuqori load = narsa ushlangan deb hisoblanadi
CLOSE_SPEED = 150                        # sekin yopish - narsani ezib yubormaslik uchun
OPEN_SPEED = 300


class Gripper:
    """Gripper uchun yuqori darajadagi, force-sensing-ready interfeys."""

    def __init__(self, controller: JointController):
        self.controller = controller
        self.joint = controller.joints[GRIPPER_JOINT]

    def open(self) -> None:
        logger.info("Gripper ochilmoqda")
        self.controller.set_position_deg(GRIPPER_JOINT, self.joint.max_deg, speed=OPEN_SPEED)
        time.sleep(0.8)

    def close(self, settle_s: float = 1.0) -> bool:
        """
        Gripperni yopadi va yopilgandan keyin yuklamani tekshirib,
        biror narsa ushlanganini (yoki yo'qligini) aniqlaydi.
        Qaytaradi: True - narsa ushlangan (deb taxmin qilinadi), False - bo'sh yopildi.
        """
        logger.info("Gripper yopilmoqda")
        self.controller.set_position_deg(GRIPPER_JOINT, self.joint.min_deg, speed=CLOSE_SPEED)
        time.sleep(settle_s)
        return self.is_holding()

    def is_holding(self) -> bool:
        """
        Present Load orqali narsa ushlanganini taxmin qiladi.
        ESLATMA: bu aniq force-sensor emas, taxminiy signal - Production
        bosqichida haqiqiy Force Sensor bilan almashtiriladi.
        """
        try:
            load = self.controller.get_load_percent(GRIPPER_JOINT)
        except Exception as exc:
            logger.warning("Gripper load o'qib bo'lmadi: %s", exc)
            return False

        holding = load >= LOAD_HOLDING_THRESHOLD_PERCENT
        logger.info(
            "Gripper load=%.1f%% -> %s",
            load, "USHLANGAN" if holding else "bo'sh"
        )
        return holding
