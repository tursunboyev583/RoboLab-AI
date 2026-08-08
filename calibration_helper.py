"""
RoboLab AI - Calibration Helper
----------------------------------
Servo ID'larini aniqlash va har bir joint uchun haqiqiy
mexanik min/max burchakni qo'lda topish uchun interaktiv skript.

Torque O'CHIRILADI - qo'l bilan jointni erkin aylantirib,
haqiqiy limitlarni terminalda ko'rish mumkin.

Ishga tushirish: python calibration_helper.py
"""

import time

from joint_controller import JointController


def scan_ids(driver, id_range=range(1, 10)):
    """Portga ulangan barcha servo ID'larini topadi."""
    print("Servo ID'lar qidirilmoqda...")
    found = []
    for sid in id_range:
        if driver.ping(sid):
            print(f"  -> Topildi: ID {sid}")
            found.append(sid)
    if not found:
        print("  Hech qanday servo topilmadi. Port va ulanishni tekshiring.")
    return found


def live_monitor(controller: JointController, name: str, duration_s: int = 20):
    """
    Torque'ni o'chiradi, jointni qo'lda aylantirish imkonini beradi
    va real vaqtda burchakni chiqaradi - shu orqali min/max ni yozib oling.
    """
    joint = controller.joints[name]
    controller.driver.torque_enable(joint.id, False)
    print(f"\n'{name}' uchun torque o'chirildi. Qo'lda aylantiring.")
    print("Min va max burchaklarni qo'lda yozib boring (Ctrl+C to'xtatish uchun).\n")

    start = time.time()
    try:
        while time.time() - start < duration_s:
            deg = controller.get_position_deg(name)
            print(f"\r{name}: {deg:6.1f} grad", end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        controller.driver.torque_enable(joint.id, True)


if __name__ == "__main__":
    controller = JointController()
    controller.driver.connect()

    scan_ids(controller.driver)

    print("\nQaysi joint uchun kalibrlash qilamiz?")
    for i, name in enumerate(controller.joints):
        print(f"  {i}: {name}")

    idx = int(input("Raqam kiriting: "))
    joint_name = list(controller.joints.keys())[idx]
    live_monitor(controller, joint_name)

    controller.disconnect()
