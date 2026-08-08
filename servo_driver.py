"""
RoboLab AI - Servo Driver Layer
--------------------------------
STS-3215 servolar bilan seriya port orqali past darajadagi muloqot.
Bu qatlam faqat "raw tick" bilan ishlaydi - gradus konversiyasi yo'q.

MUHIM #1: pip'dagi "feetech-servo-sdk" paketi (Adam-Software porti) yuqori
darajali "sms_sts" klassini o'z ichiga OLMAYDI - faqat Dynamixel SDK
uslubidagi past darajadagi PortHandler + PacketHandler(protocol_end)
interfeysini beradi. Shuning uchun har bir o'qish/yozish chaqiruvida
port_handler alohida argument sifatida uzatiladi.

MUHIM #2 (BUG FIX): shu paketning port_handler.py faylida clearPort()
metodi noto'g'ri implement qilingan - u faqat self.ser.flush() chaqiradi,
bu pyserial'da FAQAT yozish buferini tozalaydi, o'qish buferini emas.
Natijada bitta aloqa xatosi yuz berganda, eski/chala javob baytlari
portda qolib ketadi va keyingi BARCHA buyruqlarning paket sinxronizatsiyasini
buzadi (kaskadli xatolar). Bu klass shu metodni runtime'da to'g'ri versiya
(reset_input_buffer) bilan "patch" qiladi, hamda vaqtinchalik aloqa
uzilishlariga qarshi retry mexanizmini qo'shadi.

Talab: pip install feetech-servo-sdk
"""

import logging
import time

try:
    import scservo_sdk as scs
except ImportError:
    scs = None

logger = logging.getLogger("robolab.servo_driver")

# STS-3215 protokol registrlari (Feetech control table, EEPROM/SRAM addr)
ADDR_TORQUE_ENABLE = 40
ADDR_ACCELERATION = 41
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED = 46
ADDR_TORQUE_LIMIT = 48      # 2 bayt, 0-1000 (0.1% aniqlik) - haqiqiy cho'qqi tok/moment cheklovi
ADDR_PRESENT_POSITION = 56
ADDR_PRESENT_LOAD = 60      # 2 bayt, bit15=yo'nalish, qolgani 0-1000 (0.1%) - joriy moment yuklamasi
                              # Force Sensor o'rnatilgunga qadar "narsa ushlanganini" aniqlash uchun ishlatiladi
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMPERATURE = 63

TICKS_PER_REV = 4096       # STS-3215: 0-4095 tick = 0-360 gradus
PROTOCOL_END = 0            # Feetech STS/SCS seriyasi uchun standart qiymat

MAX_RETRIES = 4               # Vaqtinchalik aloqa xatosida necha marta qayta urinish
RETRY_DELAY_BASE_S = 0.08      # Har urinishda 2x oshib boradigan pauza (0.08, 0.16, 0.32...)


class ServoDriverError(Exception):
    """Servo bilan aloqa xatoligi."""
    pass


def _patch_clear_port(port_handler) -> None:
    """
    BUG FIX: SDK'ning clearPort() metodi faqat ser.flush() chaqiradi,
    bu o'qish buferini TOZALAMAYDI. To'g'ri versiya bilan almashtiramiz.
    """
    def _correct_clear_port():
        if port_handler.ser is not None and port_handler.ser.is_open:
            port_handler.ser.reset_input_buffer()
            port_handler.ser.reset_output_buffer()

    port_handler.clearPort = _correct_clear_port


class ServoDriver:
    """Feetech STS-3215 servolar uchun past darajadagi driver."""

    def __init__(self, port: str, baudrate: int = 1000000):
        if scs is None:
            raise ServoDriverError(
                "feetech-servo-sdk o'rnatilmagan. "
                "Ishga tushirish uchun: pip install feetech-servo-sdk"
            )
        self.baudrate = baudrate
        self.port_handler = scs.PortHandler(port)
        self.packet_handler = scs.PacketHandler(PROTOCOL_END)
        self._connected = False

    def connect(self) -> None:
        if not self.port_handler.openPort():
            raise ServoDriverError(f"Portni ochib bo'lmadi: {self.port_handler.port_name}")
        if not self.port_handler.setBaudRate(self.baudrate):
            raise ServoDriverError("Baudrate o'rnatib bo'lmadi")
        _patch_clear_port(self.port_handler)   # <-- bug fix shu yerda qo'llanadi
        self._connected = True
        logger.info("Servo driver ulandi: %s", self.port_handler.port_name)

    def disconnect(self) -> None:
        if self._connected:
            self.port_handler.closePort()
            self._connected = False
            logger.info("Servo driver uzildi")

    def _with_retry(self, fn, description: str):
        """Vaqtinchalik aloqa xatolarida bir necha marta, ortib boruvchi pauza bilan qayta urinadi."""
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return fn()
            except ServoDriverError as exc:
                last_exc = exc
                delay = RETRY_DELAY_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "%s: urinish %d/%d muvaffaqiyatsiz (%s) - %.2fs kutish",
                    description, attempt, MAX_RETRIES, exc, delay
                )
                # Keyingi urinishdan oldin portni tozalab olamiz
                if self.port_handler.ser is not None and self.port_handler.ser.is_open:
                    self.port_handler.ser.reset_input_buffer()
                time.sleep(delay)
        raise last_exc

    def ping(self, servo_id: int) -> bool:
        """Servo javob berayotganini tekshiradi."""
        model_number, comm_result, error = self.packet_handler.ping(self.port_handler, servo_id)
        return comm_result == scs.COMM_SUCCESS

    def read_position_tick(self, servo_id: int) -> int:
        def _do():
            pos, comm_result, error = self.packet_handler.read2ByteTxRx(
                self.port_handler, servo_id, ADDR_PRESENT_POSITION
            )
            if comm_result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: pozitsiyani o'qib bo'lmadi")
            return pos
        return self._with_retry(_do, f"read_position_tick(id={servo_id})")

    def write_position_tick(self, servo_id: int, tick: int, speed: int = 1000, acc: int = 50) -> None:
        tick = max(0, min(TICKS_PER_REV - 1, tick))

        def _do():
            # Avval acceleration (1 bayt) va speed (2 bayt) o'rnatiladi,
            # so'ng goal position (2 bayt) yuboriladi - servo shu tezlikda harakatlanadi.
            result, error = self.packet_handler.write1ByteTxRx(
                self.port_handler, servo_id, ADDR_ACCELERATION, acc
            )
            if result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: acceleration yozib bo'lmadi")

            result, error = self.packet_handler.write2ByteTxRx(
                self.port_handler, servo_id, ADDR_GOAL_SPEED, speed
            )
            if result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: speed yozib bo'lmadi")

            result, error = self.packet_handler.write2ByteTxRx(
                self.port_handler, servo_id, ADDR_GOAL_POSITION, tick
            )
            if result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: pozitsiya yozib bo'lmadi")

        self._with_retry(_do, f"write_position_tick(id={servo_id})")

    def read_temperature(self, servo_id: int) -> int:
        def _do():
            temp, comm_result, error = self.packet_handler.read1ByteTxRx(
                self.port_handler, servo_id, ADDR_PRESENT_TEMPERATURE
            )
            if comm_result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: haroratni o'qib bo'lmadi")
            return temp
        return self._with_retry(_do, f"read_temperature(id={servo_id})")

    def read_load_percent(self, servo_id: int) -> float:
        """Joriy moment yuklamasini foizda qaytaradi (0-100%).
        Bit15 yo'nalishni bildiradi, shuning uchun magnitudani ajratib olamiz."""
        def _do():
            raw, comm_result, error = self.packet_handler.read2ByteTxRx(
                self.port_handler, servo_id, ADDR_PRESENT_LOAD
            )
            if comm_result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: yuklamani o'qib bo'lmadi")
            magnitude = raw & 0x03FF  # pastki 10 bit - magnitude (0-1000)
            return magnitude / 10.0
        return self._with_retry(_do, f"read_load_percent(id={servo_id})")

    def torque_enable(self, servo_id: int, enable: bool = True) -> None:
        def _do():
            result, error = self.packet_handler.write1ByteTxRx(
                self.port_handler, servo_id, ADDR_TORQUE_ENABLE, 1 if enable else 0
            )
            if result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: torque holatini o'zgartirib bo'lmadi")
        self._with_retry(_do, f"torque_enable(id={servo_id})")

    def set_torque_limit(self, servo_id: int, percent: float) -> None:
        """Haqiqiy cho'qqi moment/tok cheklovini o'rnatadi (0-100%).
        Bu quvvat manbai cheklangan sharoitda cho'qqi tok talabini
        real ravishda kamaytiradi (shunchaki hujjat emas)."""
        percent = max(0.0, min(100.0, percent))
        value = int(round(percent / 100.0 * 1000))

        def _do():
            result, error = self.packet_handler.write2ByteTxRx(
                self.port_handler, servo_id, ADDR_TORQUE_LIMIT, value
            )
            if result != scs.COMM_SUCCESS:
                raise ServoDriverError(f"Servo {servo_id}: torque limit yozib bo'lmadi")
        self._with_retry(_do, f"set_torque_limit(id={servo_id})")
