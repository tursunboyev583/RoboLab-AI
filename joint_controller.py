"""
RoboLab AI - Joint Controller (Servo Abstraction Layer)
--------------------------------------------------------
Bu qatlam ilova kodini "raw tick"lardan butunlay ajratadi.
Motion Layer va Application Layer faqat gradus bilan ishlaydi.

MUHIM (2-avgust yangilanishi): konfiguratsiya endi TICK qiymatlariga
asoslanadi (kalibrlashning haqiqiy manbai - FT SCServo Debug'dan olingan
min_tick/max_tick/home_tick), gradus esa shulardan avtomatik hisoblanadi.

Har bir joint uchun: 0 gradus = min_tick (kalibrlangan quyi chegara),
max_deg = min_tick'dan max_tick'gacha bo'lgan haqiqiy masofa (gradusda).
Bu yondashuv "aylanish chegarasidan o'tish" (tick 4095 -> 0 ga wraparound)
holatini ham AVTOMATIK va to'g'ri hisoblaydi - masalan shoulder_lift kabi
jointlarda, qachonki haqiqiy mexanik diapazon tick-hisoblagichning
0/4095 chegarasidan "aylanib o'tsa" (masalan min=2046, max wrap qilib 315
ni ko'rsatsa - demak haqiqiy max_tick = 4096+315 = 4411).
"""

import logging
import time
import yaml

from servo_driver import ServoDriver, TICKS_PER_REV, ServoDriverError

logger = logging.getLogger("robolab.joint_controller")


class Joint:
    """Bitta joint uchun konfiguratsiya va tick<->gradus konversiyasi."""

    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.id = cfg["id"]
        self.min_tick = cfg["min_tick"]
        self.max_tick = cfg["max_tick"]     # min_tick'dan katta bo'lishi shart emas -
                                              # wraparound bo'lsa 4096+X ko'rinishida beriladi
        self.home_tick = cfg["home_tick"]
        self.direction = cfg.get("direction", 1)

        # Gradus chegaralari min_tick'ga nisbatan hisoblanadi: 0 = min_tick.
        # modulo (%) operatori tick-hisoblagich aylanishidan (0/4095 chegarasi)
        # "wraparound" bo'lgan holatlarni ham avtomatik to'g'ri hisoblaydi.
        self.min_deg = 0.0
        self.max_deg = round(((self.max_tick - self.min_tick) % TICKS_PER_REV) * 360 / TICKS_PER_REV, 2)
        self.home_deg = round(((self.home_tick - self.min_tick) % TICKS_PER_REV) * 360 / TICKS_PER_REV, 2)

    def deg_to_tick(self, deg: float) -> int:
        deg = deg * self.direction
        steps = round(deg / 360 * TICKS_PER_REV)
        return (self.min_tick + steps) % TICKS_PER_REV

    def tick_to_deg(self, tick: int) -> float:
        diff = (tick - self.min_tick) % TICKS_PER_REV
        return (diff * 360 / TICKS_PER_REV) * self.direction

    def clamp(self, deg: float) -> float:
        """Xavfsizlik limitidan tashqariga chiqishga yo'l qo'ymaydi."""
        if deg < self.min_deg or deg > self.max_deg:
            logger.warning(
                "%s: %.1f grad limitdan tashqarida [%.1f, %.1f] -> cheklandi",
                self.name, deg, self.min_deg, self.max_deg,
            )
        return max(self.min_deg, min(self.max_deg, deg))


class JointController:
    """Barcha jointlarni boshqaruvchi yuqori darajadagi interfeys."""

    def __init__(self, config_path: str = "config/joint_limits.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        self.joints: dict[str, Joint] = {
            name: Joint(name, jcfg) for name, jcfg in self.cfg["joints"].items()
        }
        self.driver = ServoDriver(self.cfg["port"], self.cfg["baudrate"])
        self.max_speed = self.cfg["safety"]["max_speed_deg_per_s"]
        self.torque_limit_percent = self.cfg["safety"]["torque_limit_percent"]

        for name, joint in self.joints.items():
            logger.info(
                "%s: diapazon [0, %.1f] grad, home=%.1f grad (min_tick=%d, max_tick=%d, home_tick=%d)",
                name, joint.max_deg, joint.home_deg, joint.min_tick, joint.max_tick, joint.home_tick,
            )

    def connect(self) -> None:
        self.driver.connect()
        for name, joint in self.joints.items():
            if not self.driver.ping(joint.id):
                raise ServoDriverError(f"Joint '{name}' (ID {joint.id}) javob bermayapti")
            self.driver.set_torque_limit(joint.id, self.torque_limit_percent)
            self.driver.torque_enable(joint.id, True)
        logger.info(
            "Barcha %d joint ulandi, torque yoqildi (limit=%.0f%%)",
            len(self.joints), self.torque_limit_percent,
        )

    def disconnect(self, release_torque: bool = True) -> None:
        """
        release_torque=True (default): barcha servolarning torque'ini
        o'chirib, keyin portni yopadi (odatiy, xavfsiz - masalan uzoq vaqt
        ishlatilmaydigan holatlar uchun).

        release_torque=False: torque YOQILGAN qoladi - robot joriy
        pozitsiyada (masalan home) qat'iy turadi, gravitatsiya ta'sirida
        "bo'shashib" sirg'alib ketmaydi. Demo/namoyish oxirida foydali.
        """
        if not self.driver._connected:
            return
        if release_torque:
            for joint in self.joints.values():
                try:
                    self.driver.torque_enable(joint.id, False)
                except ServoDriverError:
                    pass
        self.driver.disconnect()

    def get_position_deg(self, name: str) -> float:
        joint = self.joints[name]
        tick = self.driver.read_position_tick(joint.id)
        return joint.tick_to_deg(tick)

    def get_load_percent(self, name: str) -> float:
        joint = self.joints[name]
        return self.driver.read_load_percent(joint.id)

    def set_position_deg(self, name: str, deg: float, speed: int = 500) -> None:
        joint = self.joints[name]
        safe_deg = joint.clamp(deg)
        tick = joint.deg_to_tick(safe_deg)
        self.driver.write_position_tick(joint.id, tick, speed=speed)
        logger.info("%s -> %.1f grad (tick=%d)", name, safe_deg, tick)

    def wait_until_stopped(self, name: str, timeout_s: float = 3.0,
                            stable_reads_required: int = 3, movement_threshold_deg: float = 0.5) -> None:
        """
        Faqat joint HARAKATI to'xtaguncha kutadi - maqsadga aniq yetishni
        talab qilmaydi. Bu ayniqsa GRIPPER uchun muhim: predmetni ushlaganda
        u to'liq yopiq holatga (min_deg) yetib bormaydi, chunki predmetning
        o'zi to'sqinlik qiladi - servo shunchaki "to'xtab qoladi" (aynan shu
        ushlash signali). move_to() esa aniq maqsadga yetishni talab qilgani
        uchun bunday holatda hech qachon "tugadi" demaydi.
        """
        stable_count = 0
        last_pos = None
        start = time.time()
        while time.time() - start < timeout_s:
            actual = self.get_position_deg(name)
            if last_pos is not None and abs(actual - last_pos) <= movement_threshold_deg:
                stable_count += 1
            else:
                stable_count = 0
            last_pos = actual
            if stable_count >= stable_reads_required:
                logger.info("%s: harakat to'xtadi (%.1fs)", name, time.time() - start)
                return
            time.sleep(0.1)
        logger.warning("%s: TIMEOUT - %.1fs ichida harakat to'xtagani aniqlanmadi", name, timeout_s)

    def move_to(self, targets: dict, speed: int = 250, exclude: list = None,
                tolerance_deg: float = 3.0, timeout_s: float = 6.0,
                stable_reads_required: int = 3) -> None:
        """
        Bir nechta jointni bir vaqtda maqsadli pozitsiyaga yuboradi va
        HAQIQATAN TO'XTAGUNICHA kutadi.

        Shunchaki "maqsadga yaqin" bo'lish yetarli emas - servo inersiya
        bilan hali harakatlanayotib ham vaqtincha tolerantlik ichiga tushib
        qolishi mumkin. Shuning uchun bu yerda ikkita shart bir vaqtda
        tekshiriladi:
          1) joriy pozitsiya maqsaddan tolerance_deg ichida
          2) pozitsiya ketma-ket bir necha o'lchovda deyarli o'zgarmagan
             (haqiqatan to'xtagan, shunchaki "o'tib ketayotgan" emas)
        """
        exclude = exclude or []
        pending = {}
        for name, deg in targets.items():
            if name in exclude:
                continue
            if not self.check_health(name):
                raise RuntimeError(f"Safety check failed: {name}")
            joint = self.joints[name]
            safe_deg = joint.clamp(deg)
            self.set_position_deg(name, deg, speed=speed)
            pending[name] = safe_deg
            time.sleep(0.15)  # jointlar orasida qisqa pauza (buyruq yuborishda)

        stable_count = {name: 0 for name in pending}
        last_pos = {name: None for name in pending}

        start = time.time()
        while time.time() - start < timeout_s:
            all_stable = True
            for name, target_deg in pending.items():
                actual = self.get_position_deg(name)
                near_target = abs(actual - target_deg) <= tolerance_deg
                barely_moved = (
                    last_pos[name] is not None and abs(actual - last_pos[name]) <= 0.5
                )
                last_pos[name] = actual

                if near_target and barely_moved:
                    stable_count[name] += 1
                else:
                    stable_count[name] = 0

                if stable_count[name] < stable_reads_required:
                    all_stable = False

            if all_stable:
                logger.info("Barcha jointlar to'liq to'xtadi (%.1fs)", time.time() - start)
                return
            time.sleep(0.1)

        logger.warning(
            "TIMEOUT: %.1fs ichida barcha jointlar to'liq to'xtamadi - baribir davom etiladi",
            timeout_s
        )

    def check_health(self, name: str, max_temp_c: int = 65) -> bool:
        """Harakatdan oldin/keyin xavfsizlik tekshiruvi (Safety Agent'ning boshlang'ich shakli)."""
        joint = self.joints[name]
        temp = self.driver.read_temperature(joint.id)
        if temp >= max_temp_c:
            logger.error("%s: harorat xavfli darajada (%d°C)", name, temp)
            return False
        return True
