# RoboLab AI — Kun 1: Servo Konfiguratsiyasi, Home Position, Motion Test
## (Windows uchun yo'riqnoma)

## O'rnatish (PowerShell)

```powershell
pip install feetech-servo-sdk pyyaml
```

## Fayllar tuzilishi

```
robolab_day1\
├── config\
│   └── joint_limits.yaml     # Har bir joint uchun ID, limit, home holat, COM port
├── servo_driver.py           # Driver Layer - Feetech SDK wrapper
├── joint_controller.py       # Abstraction Layer - gradus/tick konversiya, limitlar
├── home_position.py          # Home holatga qaytarish
├── motion_test.py            # Har bir joint uchun smoke test
├── calibration_helper.py     # ID skanerlash va qo'lda limit topish
└── motion.log                # Avtomatik yaratiladigan jurnal fayli
```

## Ishga tushirish tartibi

### 1-qadam: Papkaga o'tish
```powershell
cd $HOME\Downloads\robolab_day1
```
(Agar boshqa joyga saqlagan bo'lsangiz, o'sha to'liq yo'lni yozing, masalan `cd C:\Users\Foydalanuvchi\Desktop\robolab_day1`)

### 2-qadam: COM portni tekshirish
```powershell
[System.IO.Ports.SerialPort]::getportnames()
```
Yoki Device Manager → "Ports (COM & LPT)" orqali.
Hozircha `config\joint_limits.yaml` faylida `port: "COM5"` deb o'rnatilgan —
agar sizning portingiz boshqacha bo'lsa, shu faylni oching va o'zgartiring.

### 3-qadam: ID va limitlarni kalibrlash (birinchi marta)
```powershell
python calibration_helper.py
```
Bu skript avval barcha ulangan servo ID'larini topadi, so'ng tanlangan
joint uchun torque'ni o'chirib, qo'lda aylantirish orqali haqiqiy
min/max burchaklarni terminaldan kuzatish imkonini beradi.
Topilgan qiymatlarni `config\joint_limits.yaml` ga yozib qo'ying.

### 4-qadam: Home Position
```powershell
python home_position.py
```
Barcha jointlar xavfsiz, sekin tezlikda 0 (home) holatga qaytadi.

### 5-qadam: Motion Test
```powershell
python motion_test.py
```
Har bir joint navbat bilan +15 gradus siljiydi, so'ng home'ga qaytadi.
Natija konsolda va `motion.log` faylida ko'rinadi.

## Windows uchun eslatmalar

- Agar `python` buyrug'i "not recognized" desa, `py` dan foydalaning:
  ```powershell
  py calibration_helper.py
  ```
- Agar portni ochishda "Access is denied" xatosi chiqsa — boshqa dastur
  (Arduino IDE, boshqa terminal) shu COM portni band qilib turgan bo'lishi
  mumkin. Barcha boshqa portga ulanuvchi dasturlarni yoping.
- Windows Defender/Antivirus ba'zan yangi `.py` skriptlarni birinchi marta
  ishga tushirishda sekinlashtirishi mumkin — bu normal holat.

## Muvaffaqiyat mezoni (bugungi kun uchun)

- [ ] Barcha 6 ta servo ID orqali javob beradi (`ping` muvaffaqiyatli)
- [ ] `joint_limits.yaml` haqiqiy mexanik limitlar bilan to'ldirilgan
- [ ] `home_position.py` xatosiz ishlaydi
- [ ] `motion_test.py` da barcha jointlar "OK" natija beradi
- [ ] `motion.log` faylida harakatlar tarixi yozilgan

## Ertangi kun (3-avgust) uchun poydevor

Bugun qurilgan `JointController` klassi ertaga Gripper va Pick&Place
logikasi uchun asosiy interfeys bo'ladi — yangi klass yozish shart emas,
faqat `motion_test.py` o'rniga `pick_and_place.py` yoziladi va xuddi
shu `set_position_deg()` metodidan foydalaniladi.

## Xavfsizlik eslatmasi

`torque_limit_percent: 50` — bu bosqichda ataylab past qo'yilgan.
Barcha jointlar ishonchli test qilingandan so'ng, Pick&Place
bosqichida (3-avgust) ehtiyotkorlik bilan oshiriladi.
