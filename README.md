# RoboLab AI

**AI-Powered Intelligent Laboratory Robotics Platform**

Laboratoriyalarda takroriy va ko'p vaqt talab qiladigan qo'l ishlarini (namunalarni aniqlash, ushlash, joylashtirish) sun'iy intellekt asosidagi robot-manipulyator yordamida avtomatlashtiruvchi DeepTech platforma.

---

## Muammo

Laboratoriya xodimlari kunlik ish vaqtining sezilarli qismini namunalarni qo'lda tashish, saralash va joylashtirishga sarflaydi — bu ham vaqt yo'qotish, ham inson xatosi ehtimolini oshiradi.

## Yechim

RoboLab AI depth (chuqurlik) kamerasi orqali stol yuzasidagi obyektni real vaqtda **uch o'lchamda** (piksel + masofa) aniqlaydi, uning koordinatasini robot burchaklariga aylantiradi, xavfsiz trayektoriya bilan yaqinlashib uni ushlaydi va belgilangan joyga ko'chiradi — bularning barchasi inson aralashuvisiz, avtonom tarzda.

---

## MVP demo sinariysi

```
Operator
  |
START
  |
Camera detects object (RGB + depth)
  |
Robot plans motion
  |
Pick
  |
Place
  |
Dashboard shows Completed
```

---

## Arxitektura

```
┌──────────────────────────────────────────────┐
│  Task Layer (vision_pick_and_place_3d.py)     │
│  Kamera -> 3D koordinata -> pick & place      │
├──────────────────────────────────────────────┤
│  Calibration Layer                            │
│  (piksel u,v + chuqurlik z) -> robot burchagi │
│  Avtomatik grid YOKI interaktiv (sichqoncha   │
│  bilan hudud belgilash) rejimi                │
├──────────────────────────────────────────────┤
│  Depth Layer (depth_camera.py)                │
│  OAK-D Lite: RGB + Stereo Depth (mm)          │
│  depthai_sdk (v2 API) orqali                  │
├──────────────────────────────────────────────┤
│  Vision Layer (camera.py)                     │
│  Obyekt aniqlash (HSV rang segmentatsiyasi)   │
├──────────────────────────────────────────────┤
│  Pose Library (poses.yaml)                    │
│  Nomlangan joint-space holatlar               │
│  ("teach-by-demonstration")                   │
├──────────────────────────────────────────────┤
│  Gripper Controller (gripper.py)              │
│  open() / close() / is_holding()              │
│  Force-sensorsiz grasp aniqlash               │
│  (servo "Present Load" registri orqali)       │
├──────────────────────────────────────────────┤
│  Joint Controller (joint_controller.py)       │
│  Gradus <-> tick konversiya, xavfsizlik       │
│  limitlar, torque limit, harakat-tugash       │
│  kutish (wait_until_stopped)                  │
├──────────────────────────────────────────────┤
│  Servo Driver (servo_driver.py)               │
│  Feetech STS-3215 past darajadagi SDK         │
└──────────────────────────────────────────────┘
```

Har bir qatlam alohida - kelajakda harakat rejalashtirish ROS 2 / MoveIt 2 ga
almashtirilganda, yuqori qatlamlar o'zgarishsiz qoladi.

---

## Hardware

| Komponent | Model |
|---|---|
| Manipulyator | SO-ARM101 (6 DOF) |
| Servolar | STS-3215 C018 |
| Boshqaruv kompyuteri | Acer Aspire A515-58P (vaqtincha) |
| Kamera | OAK-D Lite (RGB + Stereo Depth, Luxonis) |

## Dasturiy stack

Python 3.11, OpenCV, NumPy, PyYAML, Feetech Servo SDK (`feetech-servo-sdk`),
`depthai-sdk` 1.14.0 + `depthai` 2.29.0.0 (OAK-D Lite uchun)

Kelajakda: ROS 2 Jazzy, MoveIt 2, FastAPI, React, PostgreSQL, Docker (to'liq
stack loyihaning texnik hujjatida keltirilgan).

---

## O'rnatish

```powershell
pip install -r requirements.txt
pip install --force-reinstall depthai==2.29.0.0
```

Ikkinchi buyruq **alohida, birinchisidan keyin** ishga tushirilishi shart —
`depthai-sdk` o'z ehtiyojiga ko'ra `depthai`ni boshqa versiyaga ko'tarib
qo'yishi mumkin.

`config/joint_limits.yaml` faylida to'g'ri COM portni ko'rsating (Device
Manager orqali aniqlash mumkin).

---

## Ishga tushirish

### 1. Kamerani tekshirish

```powershell
python test_oak_camera.py     # OAK-D Lite: RGB + chap + o'ng + depth oynalari
```

### 2. Asosiy harakat testi

```powershell
python home_position.py       # Manipulyatorni xavfsiz boshlang'ich holatga qaytaradi
python motion_test.py         # Har bir joint uchun smoke test
python test_gripper.py        # Gripperni ochish/yopish/ushlash sinovi
```

### 3. Qo'lda boshqarish (klaviatura)

```powershell
python teleop_keyboard.py     # Barcha jointlarni klaviatura orqali sinash
```

### 4. Pozitsiyalarni "o'rgatish" (teach-by-demonstration)

```powershell
python record_pose.py         # Torque o'chirilgan holda qo'lda pozitsiya yozish
python jog_pose.py            # Torque yoqilgan holda nozik moslashtirish
```

### 5. Statik Pick & Place (qo'lda yozilgan pozitsiyalar bilan)

```powershell
python pick_and_place.py
```

### 6. Kamera bilan avtonom 3D Pick & Place

```powershell
python calibrate_vision_auto_3d.py        # Belgilangan diapazonda avtomatik grid kalibrlash
# YOKI
python calibrate_vision_interactive.py    # Kamera oynasida sichqoncha bilan
                                            # hudud belgilab, o'sha hududda kalibrlash

python vision_pick_and_place_3d.py        # To'liq avtonom: 3D (piksel+chuqurlik)
                                            # asosida topib, ushlab, qo'yadi
```

### Yordamchi vositalar

```powershell
python debug_camera.py        # HSV rang chegaralarini sozlash uchun
python diagnose_id2.py        # Bitta servo bilan aloqa barqarorligini tekshirish
```

---

## Xavfsizlik va ishonchlilik

- Har bir servo uchun dasturiy torque limit va burchak chegaralari
- Harakatdan oldin harorat tekshiruvi (`check_health`)
- Force-sensorsiz grasp aniqlash (Present Load registri)
- Ekstrapolyatsiya himoyasi - kalibrlash diapazonidan tashqari nuqtalarga ishonchsiz harakat qilinmaydi
- Harakat buyrug'i haqiqatan bajarilib (servo to'xtab) bo'lgunicha kutiladi
  (`wait_until_stopped`) - navbatdagi buyruq yoki uzilish muddatidan oldin
  yubormaydi
- Gripper yopilish vaqti to'liq masofani bosib o'tishga yetarli (o'lchangan
  tezlik asosida hisoblangan timeout) - vaqtidan oldin "muzlab qolish"ning
  oldi olingan
- **Texnik eslatma:** OAK-D Lite'ning ba'zi kamera kombinatsiyalarida xom
  DepthAI pipeline API'si beqaror ishlashi aniqlangan; shu sabab loyiha
  yuqori darajadagi `depthai_sdk` kutubxonasiga o'tkazildi, bu barqarorlikni
  to'liq tikladi

---

## Roadmap

- [x] Servo konfiguratsiyasi va xavfsiz harakat qatlami
- [x] Teach-by-demonstration pozitsiya kutubxonasi
- [x] Statik Pick & Place
- [x] Rang bo'yicha obyekt aniqlash va avtonom hand-eye kalibrlash
- [x] Avtonom Vision Pick & Place (MVP)
- [x] Depth kamera (OAK-D Lite) integratsiyasi va 3D (piksel + chuqurlik)
      asosidagi kalibratsiya
- [x] Interaktiv (sichqoncha bilan hudud belgilash) kalibratsiya vositasi
- [ ] YOLO asosida murakkab obyektlarni aniqlash
- [ ] To'liq 3D Inverse Kinematics (hozir chiziqli pan/lift regressiya
      ishlatiladi, to'liq erkin 6D IK emas)
- [ ] ROS 2 / MoveIt 2 integratsiyasi
- [ ] Ovozli buyruqlar (Whisper, o'zbek tili)
- [ ] AI Agent arxitekturasi (Executive, Vision, Planning, Safety, Memory agentlari)

---

## Biznes modeli

Robot sotish · Robotics as a Service (RaaS) · AI Subscription · LIMS/ERP
integratsiyasi · Maintenance · Training · Custom AI Development

---

## Litsenziya

TBD
