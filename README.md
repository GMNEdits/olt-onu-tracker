# OLT ONU Tracker

A free, local, LAN-based web application for small retail ISPs to manage and track ONU (Optical Network Unit) devices across multiple Syrotech OLTs. Replaces manual Excel tracking with automatic OLT sync and a searchable web interface.

## Features

- **Auto-sync** from Syrotech GPON and EPON OLTs via HTTPS web UI scraping
- **Searchable registry** — find any ONU by MAC/SN or customer name instantly
- **Auto-detects** GPON vs EPON OLTs, no manual configuration needed
- **Change tracking** — records added, removed, and moved ONUs with timestamps
- **Dark-themed web UI** — clean, responsive, works on any device with a browser
- **Zero cost** — runs on any office PC, no internet required, all open-source

## Tech Stack

- **Backend:** Python 3 + FastAPI + SQLite
- **Frontend:** Single HTML file (vanilla JS, no frameworks)
- **Sync:** HTTPS web scraping of Syrotech OLT web UI (read-only, no CLI/telnet)

## Requirements

| Requirement | Details |
|---|---|
| **Python** | 3.8 or newer |
| **pip** | Included with Python 3.8+ |
| **OS** | Linux, Windows, or macOS |
| **Network** | LAN access to your OLTs (no internet required) |
| **Browser** | Any modern browser to access the web UI |

### Python Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.0 | Web framework for the API |
| `uvicorn` | 0.30.0 | ASGI server to run FastAPI |

---

## OS-Specific Setup

### Linux (Ubuntu/Debian)

**Install Python and pip:**
```bash
sudo apt update
sudo apt install python3 python3-pip -y
```

**Clone and install dependencies:**
```bash
git clone https://github.com/GMNEdits/olt-onu-tracker.git
cd olt-onu-tracker
pip3 install -r requirements.txt
```

**Run the server:**
```bash
python3 main.py
```

**Helper script:**
```bash
chmod +x server.sh
./server.sh start
./server.sh stop
./server.sh restart
./server.sh status
```

**Auto-start on boot (systemd):**
```bash
sudo tee /etc/systemd/system/olt-tracker.service > /dev/null << 'EOF'
[Unit]
Description=OLT Tracker Server
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Environment=HOME=/home/YOUR_USERNAME
WorkingDirectory=/path/to/olt-onu-tracker
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable olt-tracker
sudo systemctl start olt-tracker
```

Manage with:
```bash
sudo systemctl status olt-tracker
sudo systemctl stop olt-tracker
sudo systemctl start olt-tracker
```

---

### Windows

**Install Python:**
1. Download Python 3.8+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Check "Add Python to PATH"** during installation
4. Verify in Command Prompt:
```
python --version
pip --version
```

**Clone and install dependencies:**
```
git clone https://github.com/GMNEdits/olt-onu-tracker.git
cd olt-onu-tracker
pip install -r requirements.txt
```

**Run the server:**
```
python main.py
```

**Helper script:**
```
server.bat start
server.bat stop
server.bat restart
server.bat status
```

**Auto-start on boot (Task Scheduler):**
1. Open **Task Scheduler** (`taskschd.msc`)
2. Click **Create Basic Task**
3. Name: `OLT Tracker Server`, Trigger: **When the computer starts**
4. Action: **Start a program**
5. Program: `python`, Arguments: `C:\path\to\olt-onu-tracker\main.py`
6. Finish, then right-click the task > **Properties** > Check **Run with highest privileges**
7. On the **Conditions** tab, uncheck **Start only if the computer is on AC power**

Alternatively, create a shortcut to `python main.py` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` for per-user auto-start.

---

### macOS

**Install Python (via Homebrew):**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
```

Or download directly from [python.org](https://www.python.org/downloads/).

**Clone and install dependencies:**
```bash
git clone https://github.com/GMNEdits/olt-onu-tracker.git
cd olt-onu-tracker
pip3 install -r requirements.txt
```

**Run the server:**
```bash
python3 main.py
```

**Helper script (same as Linux):**
```bash
chmod +x server.sh
./server.sh start
./server.sh stop
./server.sh restart
./server.sh status
```

**Auto-start on boot (launchd):**
```bash
sudo tee /Library/LaunchDaemons/com.olt-tracker.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.olt-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/olt-onu-tracker</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
sudo launchctl load /Library/LaunchDaemons/com.olt-tracker.plist
```

Manage with:
```bash
sudo launchctl start com.olt-tracker
sudo launchctl stop com.olt-tracker
sudo launchctl unload /Library/LaunchDaemons/com.olt-tracker.plist
```

---

## Quick Reference (All OS)

| Task | Linux | Windows | macOS |
|---|---|---|---|
| Install Python | `sudo apt install python3` | Download from python.org | `brew install python` |
| Install deps | `pip3 install -r requirements.txt` | `pip install -r requirements.txt` | `pip3 install -r requirements.txt` |
| Run server | `python3 main.py` | `python main.py` | `python3 main.py` |
| Helper script | `./server.sh start` | `server.bat start` | `./server.sh start` |
| Auto-start | systemd | Task Scheduler / Startup folder | launchd |

## How It Works

### OLT Setup

1. Open the **OLTs & PONs** tab
2. Click **+ Add OLT** — enter name, IP, and web login credentials (username/password)
3. PON ports are auto-created when you first sync

### Syncing

1. Click **Sync OLTs** in the header
2. The app logs into each OLT's HTTPS web UI (read-only)
3. Scrapes all ONU data from each PON port
4. Detects what changed (added/removed/moved ONUs)
5. Updates the database and records changes

### OLT Web UI Requirements

For sync to work, the OLT must have:
- **HTTPS web UI** enabled (default on Syrotech OLTs)
- **Web login** enabled with a valid user
- The user must have **read access** to the ONU auth info page

### GPON vs EPON

| | GPON OLTs | EPON OLTs |
|---|---|---|
| Web login endpoint | `/action/main.html` | `/action/login.html` |
| ONU page | Fetches PON1-4 separately | Fetches all PONs with `?select=255` |
| Unique identifier | Serial Number (SN) | MAC Address |
| Detection | HTML contains "GPON" | HTML contains "EPON" |

Both are auto-detected — no manual configuration.

## Example OLT Configuration

```
Name:    OLT-1
IP:      192.168.1.10
User:    admin
Pass:    your_password
```

## Project Structure

```
olt-onu-tracker/
├── main.py            # FastAPI backend (API + web server)
├── sync.py            # OLT web scraper (GPON + EPON)
├── database.py        # SQLite database layer
├── requirements.txt   # Python dependencies
├── server.sh          # Helper script — Linux/macOS (start/stop/restart/status)
├── server.bat         # Helper script — Windows (start/stop/restart/status)
├── static/
│   └── index.html     # Web UI (single file)
└── olt_tracker.db     # SQLite database (auto-created)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/olts` | List all OLTs |
| POST | `/api/olts` | Add OLT |
| DELETE | `/api/olts/{id}` | Delete OLT |
| GET | `/api/olts/{id}/pons` | List PONs for OLT |
| POST | `/api/pons` | Add PON |
| GET | `/api/onus?q=` | Search ONUs (by MAC, name, customer) |
| POST | `/api/onus` | Add ONU |
| PUT | `/api/onus/{id}` | Update ONU |
| DELETE | `/api/onus/{id}` | Delete ONU |
| GET | `/api/stats` | Dashboard stats |
| POST | `/api/sync` | Sync all OLTs |

## Important Notes

- **Read-only** — the app never writes commands to OLTs, only reads data via the web UI
- **LAN only** — designed to run on your local network, no internet required
- **No user login** — the web UI is open to anyone on the LAN
- **Credentials stored in plain text** — the OLT web login is saved in the SQLite database. Keep the server secure on your LAN.

## License

MIT
