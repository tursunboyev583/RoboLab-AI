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

    def close(self, timeout_s: float = 3.0) -> bool:
        """
        Gripperni yopadi va HARAKAT TO'LIQ TO'XTAGUNICHA kutadi (predmetni
        ushlaganda to'liq yopiq holatga yetib bormasligi mumkin - shuning
        uchun "maqsadga yetish" emas, "harakat to'xtashi" kutiladi).

        MUHIM: to'xtagandan keyin servo hali ham asl maqsadga (to'liq yopiq
        holat) qarab kuch ishlatishda davom etadi, garchi pozitsiya
        o'zgarmasa ham - bu predmetni keraksiz ezadi va servoni behuda
        qizdiradi ("g'ichirlash"). Shuning uchun to'xtagandan so'ng JORIY
        pozitsiyani yangi maqsad qilib qayta yuboramiz - bu servoga
        zo'riqishni to'xtatib, shu yerda "tinch turishni" buyuradi.
        """
        logger.info("Gripper yopilmoqda")
        self.controller.set_position_deg(GRIPPER_JOINT, self.joint.min_deg, speed=CLOSE_SPEED)
        time.sleep(0.2)  # servo harakatni boshlashi uchun minimal boshlang'ich pauza
        self.controller.wait_until_stopped(GRIPPER_JOINT, timeout_s=timeout_s)

        # Zo'riqishni to'xtatish: joriy pozitsiyani yangi maqsad qilib beramiz
        actual_deg = self.controller.get_position_deg(GRIPPER_JOINT)
        self.controller.set_position_deg(GRIPPER_JOINT, actual_deg, speed=CLOSE_SPEED)
        logger.info("Gripper zo'riqishi to'xtatildi (joriy pozitsiyada ushlab turibdi)")

        time.sleep(0.2)  # yuklama qiymati barqarorlashishi uchun
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
