"""
RoboLab AI - ID2 (shoulder_lift) diagnostika skripti
--------------------------------------------------------
shoulder_lift servosi bilan 10 marta ketma-ket ping+read qiladi,
muammo barqarormi yoki tasodifiymi ekanini ko'rsatish uchun.

Ishga tushirish: python diagnose_id2.py
"""

import time
from servo_driver import ServoDriver
from joint_controller import JointController

controller = JointController()
controller.driver.connect()

SERVO_ID = 2
SUCCESS = 0
FAIL = 0

print(f"ID{SERVO_ID} bilan 10 marta ping+read sinovi...\n")

for i in range(1, 11):
    ok_ping = controller.driver.ping(SERVO_ID)
    try:
        pos = controller.driver.read_position_tick(SERVO_ID)
        ok_read = True
    except Exception as e:
        pos = None
        ok_read = False

    status = "OK" if (ok_ping and ok_read) else "XATO"
    if status == "OK":
        SUCCESS += 1
    else:
        FAIL += 1

    print(f"  [{i:2d}] ping={ok_ping}  read={ok_read}  pos={pos}  -> {status}")
    time.sleep(0.3)

print(f"\nNatija: {SUCCESS}/10 muvaffaqiyatli, {FAIL}/10 xato")

if FAIL == 0:
    print("Barqaror ishlayapti -> muammo faqat harakatdan keyingi holatda bo'lishi mumkin (yuk/tok sababli).")
elif FAIL == 10:
    print("Doimiy xato -> ehtimol kabel yoki ID2 servosining o'zida muammo bor.")
else:
    print("Tasodifiy xato -> ehtimol quvvat manbai yoki shovqin (elektr) muammosi.")

controller.driver.disconnect()
