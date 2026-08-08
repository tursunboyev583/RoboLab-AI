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

    def disconnect(self) -> None:
        if not self.driver._connected:
            return
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

    def check_health(self, name: str, max_temp_c: int = 65) -> bool:
        """Harakatdan oldin/keyin xavfsizlik tekshiruvi (Safety Agent'ning boshlang'ich shakli)."""
        joint = self.joints[name]
        temp = self.driver.read_temperature(joint.id)
        if temp >= max_temp_c:
            logger.error("%s: harorat xavfli darajada (%d°C)", name, temp)
            return False
        return True
