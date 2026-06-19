# Multi-Factor Biometric Attendance System

A real-time attendance system that authenticates users through **face recognition + voice verification** before logging attendance — with a password-based fallback if biometrics fail.

Built with Python, OpenCV, Picovoice Eagle, and MySQL.

---

## How It Works

```
Webcam detects a face
        │
        ▼  (consistent match over ~11 frames)
Voice verification window opens (5 seconds)
        │
   ┌────┴────┐
   │         │
 Match    No match
   │         │
   ▼         ▼
Attendance   Password fallback
logged       (name + password)
```

The system requires **both face and voice** to match before logging attendance — making it resistant to photo spoofing. If face recognition fails entirely, users can fall back to name + password.

---

## Features

- **Dual-biometric verification** — face detection locks onto a person, then voice recognition cross-checks identity before any record is written
- **Anti-spoofing** — a photo of someone's face is not enough; their voice must also match within a 5-second window
- **Password fallback** — gracefully handles cases where biometrics fail (glasses, masks, background noise)
- **24-hour cooldown via MySQL trigger** — duplicate attendance is rejected at the database level, not the application level
- **Admin enrollment CLI** — live webcam capture and guided voice profiling for adding new users
- **Secure storage** — passwords hashed with bcrypt, all queries parameterized against SQL injection, secrets loaded from environment variables

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Face detection & recognition | OpenCV + `face_recognition` (dlib 128-point encodings) |
| Speaker verification | Picovoice Eagle — on-device, no audio sent to the cloud |
| Database | MySQL / MariaDB — triggers, foreign keys, and a reporting view |
| Backend | Python 3.10+ |
| Security | bcrypt password hashing, parameterized SQL queries, `.env` secrets |

---

## Project Structure

```
├── main.py             # Entry point — menu to launch monitor or enrollment
├── monitor.py          # Real-time attendance monitor: webcam + microphone loop
├── enroll.py           # Admin CLI: add, modify, remove users
├── user.py             # Data access layer: all DB reads and writes
├── attendance_db.sql   # Schema: tables, trigger, attendance view
├── .env.example        # Environment variable template
└── requirements.txt
```

---

## Database Design

```
user_tbl                    attendance_tbl
────────────────────        ──────────────────────
user_id      INT (PK)  ◄─── user_id      INT (FK)
name         VARCHAR        record_id    INT (PK)
password     VARCHAR(60)    set_at       DATETIME
face_features LONGTEXT
audio_profile LONGBLOB
isActive     ENUM
```

**Trigger — `attendance_tbl_before_insert`**  
Before every insert, the trigger checks whether this user already has a record within the last 24 hours. If so, it raises `SQLSTATE '45000'` and rejects the insert. No application code is needed to guard against duplicate check-ins.

**View — `attendance_view`**  
Joins both tables so attendance records can be queried by name rather than by ID.

---

## Setup

### Prerequisites

- Python 3.10+
- MySQL 8.0 or MariaDB (XAMPP includes MariaDB)
- A webcam and microphone
- A [Picovoice](https://picovoice.ai/) account with an Eagle access key (registration required)

### 1. Clone and install

```bash
git clone https://github.com/hopeful-programmer/Multi-Factor-Attendance-System
cd Multi-Factor-Attendance-System
pip install -r requirements.txt
```

> **Note:** `face_recognition` requires `dlib`, which in turn requires CMake and a C++ compiler. On Windows, install [CMake](https://cmake.org/) and [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) first.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your Picovoice access key and database credentials
```

To find your microphone device index:
```bash
python -c "from pvrecorder import PvRecorder; print(PvRecorder.get_available_devices())"
```

### 3. Set up the database

```bash
# Linux / macOS / Git Bash
mysql -u root -p < attendance_db.sql

# Windows PowerShell (XAMPP)
Get-Content attendance_db.sql | C:\xampp\mysql\bin\mysql.exe -u root
```

### 4. Run the app

```bash
python main.py
```

A menu lets you choose between the attendance monitor and the admin enrollment panel. Enroll at least one user before starting the monitor.

---

## Security Notes

| Concern | How it's handled |
|---------|-----------------|
| Plaintext passwords | Stored as **bcrypt** hashes — never reversible |
| SQL injection | All queries use **parameterized statements** (`%s` placeholders) |
| Hardcoded secrets | API keys and DB credentials loaded from **`.env`** — never in source |
| Cloud audio exposure | Picovoice Eagle runs **fully on-device** — no audio leaves the machine |
| Duplicate attendance | Rejected by a **database-level trigger**, not application logic |
