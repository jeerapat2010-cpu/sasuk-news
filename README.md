# ข่าวแพทย์แผนไทย/แผนจีน/สมุนไพร/เวลเนส — Auto-updated

เว็บข่าวที่ดึงข้อมูลอัตโนมัติจาก Hfocus.org และ Google News RSS
(ครอบคลุมทั้งข่าวในและต่างประเทศเกี่ยวกับแพทย์แผนไทย แผนจีน การแพทย์ทางเลือก
สมุนไพร เทคโนโลยีทางการแพทย์ เวลเนส และสปา) แล้วแสดงผลผ่าน GitHub Pages
โดยอัปเดตอัตโนมัติทุก 4 ชั่วโมงผ่าน GitHub Actions

## โครงสร้างไฟล์

```
sasuk-news/
├── .github/workflows/update-news.yml   <- ตัวรันอัตโนมัติ
├── scraper.py                          <- สคริปต์ดึงข่าว
├── requirements.txt                    <- library ที่ต้องใช้
├── news.json                           <- ข้อมูลข่าว (ถูกอัปเดตอัตโนมัติ)
├── index.html                          <- หน้าเว็บแสดงผล
└── README.md                           <- ไฟล์นี้
```

## วิธีอัปโหลดขึ้น GitHub (ทำครั้งเดียว)

### ขั้นตอนที่ 1 — สร้าง repository ใหม่

1. เข้า https://github.com/new
2. ตั้งชื่อ repo เช่น `sasuk-news`
3. เลือก **Public** (จำเป็น ถ้าจะใช้ GitHub Pages ฟรี)
4. **ไม่ต้อง** ติ๊ก "Add a README file" (เรามีไฟล์ README มาแล้ว)
5. กด **Create repository**

### ขั้นตอนที่ 2 — อัปโหลดไฟล์ทั้งหมด

1. ในหน้า repo ที่สร้างใหม่ จะมีลิงก์ "uploading an existing file" — กดตรงนั้น
   (หรือกดปุ่ม **Add file → Upload files**)
2. ลากไฟล์ทั้งหมดในโฟลเดอร์ `sasuk-news` ที่ได้รับไปวาง
   **สำคัญ**: ต้องรักษาโครงสร้างโฟลเดอร์ `.github/workflows/update-news.yml` ไว้
   ถ้าลากทั้งโฟลเดอร์ไม่ได้ ให้สร้างไฟล์ `update-news.yml` ทีละไฟล์ผ่านปุ่ม
   "Add file → Create new file" แล้วพิมพ์ path เป็น `.github/workflows/update-news.yml`
   ระบบจะสร้างโฟลเดอร์ให้อัตโนมัติ
3. เลื่อนลงล่าง ใส่ commit message เช่น "initial commit"
4. กด **Commit changes**

### ขั้นตอนที่ 3 — เปิดสิทธิ์ให้ GitHub Actions เขียนไฟล์ได้

1. ไปที่ **Settings** ของ repo
2. เมนูซ้าย เลือก **Actions → General**
3. เลื่อนลงหา **Workflow permissions**
4. เลือก **Read and write permissions**
5. กด **Save**

(ขั้นตอนนี้จำเป็น ไม่งั้น Action จะ push ไฟล์ news.json ที่อัปเดตแล้วกลับเข้า repo ไม่ได้)

### ขั้นตอนที่ 4 — เปิด GitHub Pages

1. ไปที่ **Settings → Pages**
2. หัวข้อ **Build and deployment → Source** เลือก **Deploy from a branch**
3. **Branch** เลือก `main` และโฟลเดอร์ `/ (root)`
4. กด **Save**
5. รอ 1-2 นาที จะมีลิงก์เว็บของพี่จีขึ้นมา เช่น
   `https://ชื่อผู้ใช้.github.io/sasuk-news/`

### ขั้นตอนที่ 5 — รัน workflow ครั้งแรกด้วยตัวเอง (ไม่ต้องรอ 4 ชม.)

1. ไปที่แท็บ **Actions** ของ repo
2. เลือก workflow ชื่อ **Update TTM/Wellness News** ทางซ้าย
3. กด **Run workflow** (มุมขวา) → กด **Run workflow** อีกครั้งเพื่อยืนยัน
4. รอสักครู่ (1-2 นาที) แล้วรีเฟรชหน้าเว็บของพี่จี ข่าวจะขึ้นแล้ว

## หลังจากนี้

ไม่ต้องทำอะไรอีกค่ะ ระบบจะดึงข่าวใหม่ให้อัตโนมัติทุก 4 ชั่วโมง
ถ้าอยากปรับความถี่ ให้แก้บรรทัด `cron` ในไฟล์
`.github/workflows/update-news.yml`

## ถ้าอยากปรับ keyword ที่กรอง

แก้ได้ที่ไฟล์ `scraper.py` ในส่วน:
- `KEYWORDS_TH` — คำที่ใช้กรองข่าวจาก Hfocus
- `GOOGLE_NEWS_QUERIES` — คำค้นสำหรับข่าวจาก Google News (ทั้งไทย/เทศ)

## ถ้า Hfocus ไม่ขึ้นข่าวเลย (แต่ Google News ขึ้นปกติ)

แปลว่าโครงสร้างหน้าเว็บ Hfocus อาจเปลี่ยนไป ให้เปิด
**Actions → เลือก run ล่าสุด → เปิด log ของ step "Run scraper"**
ดูว่าฝั่ง `[hfocus]` เจอข่าวกี่รายการ ถ้าเป็น 0 ให้แจ้งมายด์
พร้อมบอกว่า log ขึ้นว่าอย่างไร มายด์จะช่วยปรับ selector ให้ค่ะ

## หมายเหตุเรื่องลิขสิทธิ์

หน้าเว็บนี้แสดงเฉพาะ หัวข้อข่าว รูปปก และลิงก์กลับไปต้นทาง
ไม่ได้คัดลอกเนื้อหาบทความมาแสดงเต็ม เพื่อเคารพลิขสิทธิ์ของสำนักข่าวต้นทาง
