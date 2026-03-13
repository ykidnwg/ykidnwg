# 🤖 Terabox Automation Bot

A full-stack Python automation bot that runs 24/7 on a Linux VPS.  
It receives Terabox share links (via Telegram, a text file, or a command-line argument), saves the files to your own Terabox cloud, generates a new public share link, and notifies a Telegram channel.

---

## 📋 Table of Contents

1. [Features](#features)
2. [System Architecture](#system-architecture)
3. [Workflow Flowchart](#workflow-flowchart)
4. [Project Structure](#project-structure)
5. [Requirements](#requirements)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Running the Bot](#running-the-bot)
9. [VPS Deployment (Ubuntu 22)](#vps-deployment-ubuntu-22)
10. [Dashboard](#dashboard)
11. [Usage Examples](#usage-examples)
12. [Bonus Features](#bonus-features)

---

## ✨ Features

| Feature | Details |
|---|---|
| **Link Sources** | Telegram bot, `links.txt` file, CLI argument |
| **Link Validation** | Whitelist: `terabox.com`, `1024terabox.com`, `teraboxapp.com` |
| **Scraper** | Headless Playwright + HTTP API fallback |
| **Authentication** | Email/password login; session cookies persisted |
| **Save to Cloud** | `share/transfer` API + UI fallback |
| **Share Link** | Automatically generated via `share/set` API |
| **Telegram Notify** | Formatted message sent to configured channel |
| **Queue** | Redis (preferred) with SQLite fallback |
| **Parallel Workers** | Configurable (default 3) |
| **Duplicate Detection** | Skip or rename based on DB history |
| **Auto-categorise** | `/Movies`, `/Anime`, `/Software`, `/Apps`, `/Music`, … |
| **Retry Logic** | 3 attempts with configurable delay |
| **Logging** | Structured rotating log via `loguru` |
| **Dashboard** | FastAPI web UI at `http://localhost:8080` |
| **VPS Deployment** | systemd service included |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                        │
│  Telegram Bot ──┐                                           │
│  links.txt   ──►│──► Queue Manager (Redis / SQLite)         │
│  CLI arg     ──┘                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      QUEUE WORKER                           │
│   ThreadPoolExecutor (MAX_WORKERS threads)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │  job per thread
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     JOB MANAGER                             │
│                                                             │
│  1. Validate Link       (utils/validator.py)                │
│  2. Check Duplicate     (database/models.py)                │
│  3. Scrape Metadata     (modules/terabox_scraper.py)        │
│  4. Login / Session     (modules/terabox_auth.py)           │
│  5. Save to Cloud       (modules/terabox_save.py)           │
│  6. Generate Share Link (modules/terabox_share.py)          │
│  7. Notify Telegram     (bot/telegram_bot.py)               │
│  8. Log Result          (utils/logger.py)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow Flowchart

```
        ┌─────────────────┐
        │  Receive Link   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Validate Link   │──── INVALID ──► Log & Skip
        └────────┬────────┘
                 │ VALID
        ┌────────▼────────┐
        │ Duplicate Check │──── DUPLICATE ──► Skip / Log
        └────────┬────────┘
                 │ NEW
        ┌────────▼────────┐
        │ Scrape Terabox  │──── FAIL ──► Retry (×3) ──► Mark FAILED
        │ Get Metadata    │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Login Terabox  │
        │ (reuse session) │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Save to Cloud  │──── FAIL ──► Retry (×3) ──► Mark FAILED
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Wait / Verify  │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Generate Share  │──── FAIL ──► Retry (×3) ──► Mark FAILED
        │      Link       │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Send Telegram   │
        │  Notification   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Log SUCCESS    │
        └─────────────────┘
```

---

## 📁 Project Structure

```
terabox-automation-bot/
├── main.py                  # Entry point
├── config.py                # Centralised config (loaded from .env)
├── dashboard.py             # FastAPI monitoring dashboard
├── requirements.txt
├── .env.example             # Template – copy to .env and fill in
├── terabox-bot.service      # systemd unit file
├── README.md
│
├── bot/
│   ├── __init__.py
│   ├── telegram_bot.py      # Telegram bot + channel notifications
│   └── queue_worker.py      # Background worker dispatcher
│
├── modules/
│   ├── __init__.py
│   ├── terabox_auth.py      # Login & session management
│   ├── terabox_scraper.py   # Public share page scraper
│   ├── terabox_save.py      # Save file to user cloud
│   └── terabox_share.py     # Generate share links
│
├── services/
│   ├── __init__.py
│   ├── queue_manager.py     # Redis / SQLite queue abstraction
│   └── job_manager.py       # Full pipeline orchestration
│
├── utils/
│   ├── __init__.py
│   ├── logger.py            # loguru setup
│   ├── validator.py         # Link validation & file reader
│   └── helpers.py           # Format helpers, categoriser
│
├── database/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy models & DB init
│   └── db.sqlite            # Auto-created on first run
│
└── logs/
    └── bot.log              # Rotating log file
```

---

## 📦 Requirements

- Python 3.10+
- Redis (optional – bot falls back to SQLite queue automatically)
- Chromium (installed by Playwright)

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/ykidnwg/ykidnwg.git terabox-automation-bot
cd terabox-automation-bot
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

```bash
playwright install chromium
playwright install-deps chromium
```

### 5. Configure environment variables

```bash
cp .env.example .env
nano .env   # fill in your credentials
```

---

## ⚙️ Configuration

Edit `.env`:

```env
# Terabox Credentials
TERABOX_EMAIL=your_email@example.com
TERABOX_PASSWORD=your_password

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHANNEL_ID=@your_channel   # or numeric chat id

# Redis (optional)
REDIS_HOST=localhost
REDIS_PORT=6379

# Workers
MAX_WORKERS=3
RETRY_COUNT=3
RETRY_DELAY=10

# Features
ENABLE_AUTO_CATEGORIZE=true
DUPLICATE_ACTION=skip

# Dashboard
DASHBOARD_ENABLED=true
DASHBOARD_PORT=8080
```

---

## ▶️ Running the Bot

### Start everything (worker + Telegram bot)

```bash
python main.py
```

### Worker only (no Telegram bot)

```bash
python main.py --worker-only
```

### Telegram bot only (no worker)

```bash
python main.py --bot-only
```

### Enqueue links from a file

```bash
python main.py --file links.txt
```

### Enqueue a single link

```bash
python main.py --link "https://terabox.com/s/xxxxxxxx"
```

### Start the dashboard separately

```bash
uvicorn dashboard:app --host 0.0.0.0 --port 8080
```

---

## 🖥️ VPS Deployment (Ubuntu 22)

### Step 1 – System setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip redis-server git
sudo systemctl enable --now redis-server
```

### Step 2 – Deploy the bot

```bash
sudo mkdir /opt/terabox-automation-bot
sudo chown ubuntu:ubuntu /opt/terabox-automation-bot
cd /opt/terabox-automation-bot

git clone https://github.com/ykidnwg/ykidnwg.git .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium

cp .env.example .env
nano .env   # fill in credentials
```

### Step 3 – Install the systemd service

```bash
sudo cp terabox-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable terabox-bot
sudo systemctl start terabox-bot
sudo systemctl status terabox-bot
```

### Step 4 – View logs

```bash
journalctl -u terabox-bot -f
# or
tail -f /opt/terabox-automation-bot/logs/bot.log
```

---

## 📊 Dashboard

Open `http://<your-vps-ip>:8080` in your browser.

The dashboard shows:

- Total / Pending / Running / Success / Failed / Duplicate job counts
- Live table of the 20 most recent jobs (auto-refreshes every 30 s)
- REST API at `/api/stats` and `/api/jobs`

---

## 💬 Usage Examples

### Telegram Bot

1. Start a chat with your bot.
2. Send:
   ```
   https://terabox.com/s/xxxxxxxx
   ```
3. The bot confirms the link is queued.
4. When done, the result appears in your Telegram channel:
   ```
   📂 FILE BERHASIL DISIMPAN
   
   📄 File
   
   📄 Nama   : Movie.Name.2024.mkv
   📦 Size   : 1.45 GB
   📁 Jumlah : 1 file(s)
   🔗 Download : https://terabox.com/s/newlink
   ```

### links.txt

```
# One link per line, blank lines and # comments are ignored
https://terabox.com/s/aaa
https://terabox.com/s/bbb
https://1024terabox.com/s/ccc
```

```bash
python main.py --file links.txt
```

---

## 🌟 Bonus Features

| Feature | How to enable |
|---|---|
| **Auto-categorisation** | `ENABLE_AUTO_CATEGORIZE=true` in `.env` |
| **Parallel workers** | Set `MAX_WORKERS=5` (or more) in `.env` |
| **Dashboard** | `DASHBOARD_ENABLED=true` then `uvicorn dashboard:app` |
| **Duplicate skip** | `DUPLICATE_ACTION=skip` (default) |

---

## 📜 Log Format

```
2024-01-15 10:23:45 | INFO     | services.job_manager:45 – Processing link: https://terabox.com/s/xxx
2024-01-15 10:23:48 | INFO     | modules.terabox_scraper:60 – Scraped: name='movie.mkv', size=1548576000, folder=False
2024-01-15 10:24:10 | INFO     | modules.terabox_save:55 – File saved successfully to /Movies
2024-01-15 10:24:15 | INFO     | modules.terabox_share:44 – Share link created: https://terabox.com/s/newlink
2024-01-15 10:24:16 | INFO     | bot.queue_worker:65 – Job finished – status=SUCCESS
```

---

## 🔒 Security Notes

- Credentials are stored only in `.env` (excluded from git via `.gitignore`).
- Browser session cookies are saved locally in `database/terabox_cookies.json` (also gitignored).
- The systemd service runs as the `ubuntu` user (non-root) with `NoNewPrivileges=true`.
