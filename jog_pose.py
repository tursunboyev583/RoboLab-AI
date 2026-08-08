"""
RoboLab AI - Pose Jogger (Nozik Moslashtirish)
---------------------------------------------------
Mavjud pozitsiyani yuklab, TORQUE YOQILGAN holda kichik qadamlar bilan
(masalan har buyruqda 1-5 grad) aniq moslashtirish uchun.

record_pose.py'dan farqi: u yerda torque O'CHIRILADI (qo'l bilan erkin
harakatlantirish), bu yerda torque YOQILGAN qoladi (aniq, boshqariladigan
kichik siljishlar - masalan gripperni predmet ustiga millimetrli
aniqlik bilan to'g'rilash uchun).

Ishga tushirish: python jog_pose.py
"""

import os
import time
import yaml

from joint_controller import JointController

POSES_PATH = "config/poses.yaml"

# Qisqa kodlar - tezkor kiritish uchun
JOINT_CODES = {
    "sp": "shoulder_pan",
    "sl": "shoulder_lift",
    "ef": "elbow_flex",
    "wf": "wrist_flex",
    "wr": "wrist_roll",
    "gr": "gripper",
}

JOG_SPEED = 150


def load_poses() -> dict:
    if os.path.exists(POSES_PATH):
        with open(POSES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {}
    return {}


def save_poses(poses: dict) -> None:
    with open(POSES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(poses, f, allow_unicode=True, sort_keys=False)


def print_current(controller: JointController) -> None:
    print("\nJoriy holat:")
    for code, name in JOINT_CODES.items():
        deg = controller.get_position_deg(name)
        print(f"  [{code}] {name:15s} {deg:7.2f} grad")
    print()


def print_help() -> None:
    print("Buyruqlar:")
    print("  sp +2      -> shoulder_pan'ni +2 gradga siljitish")
    print("  sl -1.5    -> shoulder_lift'ni -1.5 gradga siljitish")
    print("  gr open    -> gripperni to'liq ochish")
    print("  gr close   -> gripperni to'liq yopish")
    print("  show       -> joriy holatni qayta ko'rsatish")
    print("  save <nom> -> joriy holatni shu nom bilan saqlash")
    print("  quit       -> chiqish\n")


def main():
    controller = JointController()
    controller.connect()  # torque YOQILGAN holda ulanadi

    poses = load_poses()

    pose_name = input("Qaysi pose'ni yuklaymiz? (masalan 'pick', bo'sh - nol holatdan boshlash): ").strip()
    if pose_name and pose_name in poses:
        print(f"'{pose_name}' yuklanmoqda...")
        for joint_name, deg in poses[pose_name].items():
            controller.set_position_deg(joint_name, deg, speed=JOG_SPEED)
            time.sleep(0.15)
        time.sleep(1.0)
    elif pose_name:
        print(f"'{pose_name}' topilmadi, joriy holatdan boshlanadi.")

    print_help()
    print_current(controller)

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue

            parts = cmd.split()

            if parts[0] == "quit":
                break
            elif parts[0] == "show":
                print_current(controller)
            elif parts[0] == "save":
                if len(parts) < 2:
                    print("Nom kiriting: save <nom>")
                    continue
                name = parts[1]
                pose = {name2: round(controller.get_position_deg(name2), 2) for name2 in JOINT_CODES.values()}
                poses[name] = pose
                save_poses(poses)
                print(f"'{name}' saqlandi -> {POSES_PATH}")
            elif parts[0] in JOINT_CODES:
                joint_name = JOINT_CODES[parts[0]]
                if len(parts) < 2:
                    print("Qiymat kiriting: masalan 'sp +2' yoki 'gr open'")
                    continue
                if parts[0] == "gr" and parts[1] in ("open", "close"):
                    joint = controller.joints[joint_name]
                    target = joint.max_deg if parts[1] == "open" else joint.min_deg
                    controller.set_position_deg(joint_name, target, speed=JOG_SPEED)
                else:
                    try:
                        delta = float(parts[1])
                    except ValueError:
                        print("Noto'g'ri qiymat")
                        continue
                    current = controller.get_position_deg(joint_name)
                    controller.set_position_deg(joint_name, current + delta, speed=JOG_SPEED)
                time.sleep(0.5)
                print_current(controller)
            else:
                print("Noma'lum buyruq. Yordam uchun: sp/sl/ef/wf/wr/gr, show, save, quit")

    finally:
        controller.disconnect()
        print("Yakunlandi.")


if __name__ == "__main__":
    main()
