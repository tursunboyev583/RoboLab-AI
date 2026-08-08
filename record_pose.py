"""
RoboLab AI - Pose Recorder (Teach Pendant)
---------------------------------------------
Sanoat robotlaridagi "teach mode" tamoyili: torque o'chiriladi, siz
robotni QO'LDA kerakli holatga olib borasiz, so'ng shu pozitsiya
nomlanib config/poses.yaml fayliga saqlanadi.

Ertaga (Kamera integratsiyasi kunida) bu fayldagi qo'lda yozilgan
pozitsiyalar Vision Agent tomonidan avtomatik hisoblangan
koordinatalar bilan almashtiriladi - Task Layer o'zgarmaydi.

Ishga tushirish: python record_pose.py
"""

import os
import yaml

from joint_controller import JointController

POSES_PATH = "config/poses.yaml"


def load_poses() -> dict:
    if os.path.exists(POSES_PATH):
        with open(POSES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {}
    return {}


def save_poses(poses: dict) -> None:
    with open(POSES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(poses, f, allow_unicode=True, sort_keys=False)


def main():
    controller = JointController()
    controller.driver.connect()

    print("\n=== RoboLab AI - Pose Recorder ===")
    print("Barcha jointlar uchun torque o'chiriladi - robotni qo'lda")
    print("kerakli holatga olib boring, so'ng Enter bosing.\n")

    # Torque'ni barcha jointlar uchun o'chiramiz - qo'lda harakatlantirish uchun
    for joint in controller.joints.values():
        controller.driver.torque_enable(joint.id, False)

    poses = load_poses()

    while True:
        name = input("Pose nomini kiriting (chiqish uchun bo'sh qoldiring): ").strip()
        if not name:
            break

        input(f"Robotni '{name}' holatiga olib boring, so'ng Enter bosing...")

        pose = {}
        for joint_name, joint in controller.joints.items():
            tick = controller.driver.read_position_tick(joint.id)
            deg = joint.tick_to_deg(tick)
            pose[joint_name] = round(deg, 2)
            print(f"  {joint_name}: {deg:.1f} grad")

        poses[name] = pose
        save_poses(poses)
        print(f"'{name}' saqlandi -> {POSES_PATH}\n")

    # Chiqishdan oldin torque'ni qayta yoqamiz (xavfsizlik)
    for joint in controller.joints.values():
        controller.driver.torque_enable(joint.id, True)

    controller.driver.disconnect()
    print("Yakunlandi.")


if __name__ == "__main__":
    main()
