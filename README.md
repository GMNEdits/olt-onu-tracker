# OLT ONU Tracker

A free, local, LAN-based web application for small retail ISPs to manage and track ONU (Optical Network Unit) devices across multiple Syrotech OLTs. Replaces manual Excel tracking with automatic OLT sync and a searchable web interface.

![Dark UI](https://img.shields.io/badge/UI-Dark_Theme-1e293b) ![Python](https://img.shields.io/badge/Python-3.8+-3776ab) ![License](https://img.shields.io/badge/License-MIT-green)

## Demo

| PON View | New ONUs | OLTs & PONs | History |
|---|---|---|---|
| OLT & PON-wise grouped ONUs with status, Rx power, search, per-OLT sync | Unconfigured ONUs needing customer names | OLT cards with PON health badges | Change tracking with old → new values |

## Features

- **Auto-sync** from Syrotech GPON and EPON OLTs via HTTPS web UI scraping
- **PON View tab** — ONUs grouped by OLT → PON, with health badges, search, and per-OLT sync button
- **Per-OLT sync** — sync individual OLTs without syncing all, useful when working on specific fiber routes
- **Searchable registry** — find any ONU by MAC/SN or customer name instantly
- **Auto-detects** GPON vs EPON OLTs, no manual configuration needed
- **ONU tracking** — ONU ID, MAC/SN, customer name, online/offline status, OLT, PON
- **New ONUs tab** — shows unconfigured ONUs (no customer name yet)
- **PON health indicator** — colored badges show fiber cut status:
  - Green: less than 20% offline
  - Orange: 20-50% offline (warning)
  - Red: 50% or more offline (likely fiber cut)
- **Live Rx Power check** — click Rx button on any online ONU to fetch real-time optical receive power from the OLT
- **Change tracking** — records added, removed, moved, renamed, and MAC-replaced ONUs
- **History tab** — filterable log showing old → new values for every change
- **Dark-themed web UI** — clean, responsive, works on any device with a browser
- **Zero cost** — runs on any office PC, no internet required, all open-source

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3 + FastAPI + SQLite |
| Frontend | Single HTML file (vanilla JS, no frameworks) |
| Sync | HTTPS web scraping of Syrotech OLT web UI |

## Requirements

| Requirement | Details |
|---|---|
| Python | 3.8 or newer |
| pip | Included with Python 3.8+ |
| OS | Linux, Windows, or macOS |
| Network | LAN access to your OLTs (no internet required) |
| Browser | Any modern browser |

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.0 | Web framework for the API |
| `uvicorn` | 0.30.0 | ASGI server to run FastAPI |

---

## Quick Setup

### 1. Clone and install

```bash
git clone https://github.com/GMNEdits/olt-onu-tracker.git
cd olt-onu-tracker
pip install -r requirements.txt
```

### 2. Run

```bash
python main.py
```

### 3. Open browser

Go to `http://localhost:8000`

---

## OS-Specific Setup

### Linux (Ubuntu/Debian)

**Install Python:**
```bash
sudo apt update
sudo apt install python3 python3-pip -y
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

Manage:
```bash
sudo systemctl status olt-tracker
sudo systemctl stop olt-tracker
sudo systemctl start olt-tracker
```

---

### Windows

**Install Python:**
1. Download Python 3.8+ from [python.org](https://www.python.org/downloads/)
2. Run installer, **check "Add Python to PATH"**
3. Verify: `python --version`

**Run:**
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

**Auto-start on boot:**
1. Create `start.bat`:
```bat
@echo off
cd C:\olt-tracker
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
2. Press `Win+R`, type `shell:startup`, press Enter
3. Put a shortcut to `start.bat` in that folder

---

### macOS

**Install Python (via Homebrew):**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
```

**Run:**
```bash
python3 main.py
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

---

## How It Works

### Step 1: Add OLTs

1. Open the **OLTs & PONs** tab
2. Click **+ Add OLT**
3. Enter name, IP address, and web login credentials
4. PON ports are auto-created on first sync

### Step 2: Sync

1. Click **Sync OLTs** in the header
2. The app logs into each OLT's HTTPS web UI (read-only)
3. Scrapes all ONU data from each PON port
4. Auto-detects GPON vs EPON
5. Compares with previous data and records all changes

### Step 3: Monitor

- **PON View tab** — OLT & PON-wise grouped ONUs with health badges, search, and per-OLT sync
- **New ONUs tab** — see which ONUs need customer names
- **OLTs & PONs tab** — check PON health at a glance
- **History tab** — review all changes over time

---

## GPON vs EPON

| Feature | GPON OLTs | EPON OLTs |
|---|---|---|
| Web login | `/action/main.html` | `/action/login.html` |
| ONU page | Fetches PON1-4 separately | Fetches all with `?select=255` |
| Identifier | Serial Number (SN) | MAC Address |
| Detection | Auto (HTML contains "GPON") | Auto (HTML contains "EPON") |

Both are auto-detected — no manual configuration needed.

---

## Tabs

| Tab | Description |
|---|---|
| **PON View** | ONUs grouped by OLT → PON. Health badges, search, Rx power per ONU, per-OLT sync button. Default tab. |
| **New ONUs** | ONUs with no customer name assigned (N/A or empty). |
| **OLTs & PONs** | OLT cards with PON health badges (green/orange/red). |
| **History** | All changes — moved, renamed, MAC changed, removed. Shows old → new. |

---

## Project Structure

```
olt-onu-tracker/
├── main.py            # FastAPI backend (API + web server)
├── sync.py            # OLT web scraper (GPON + EPON)
├── database.py        # SQLite database layer
├── requirements.txt   # Python dependencies
├── server.sh          # Helper script — Linux/macOS
├── server.bat         # Helper script — Windows
├── static/
│   └── index.html     # Web UI (single file, dark theme)
└── olt_tracker.db     # SQLite database (auto-created, gitignored)
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/olts` | List all OLTs |
| POST | `/api/olts` | Add OLT |
| DELETE | `/api/olts/{id}` | Delete OLT |
| GET | `/api/olts/{id}/pons` | List PONs for OLT |
| POST | `/api/pons` | Add PON |
| GET | `/api/onus?q=` | Search ONUs |
| GET | `/api/new-onus` | List unconfigured ONUs |
| POST | `/api/onus` | Add ONU |
| PUT | `/api/onus/{id}` | Update ONU |
| DELETE | `/api/onus/{id}` | Delete ONU |
| GET | `/api/pon-view?olt_id=` | ONUs grouped by OLT → PON (for PON View tab) |
| GET | `/api/events?onu_id=&limit=` | List history events |
| GET | `/api/onus/{id}/optical` | Fetch live Rx Power for an ONU |
| GET | `/api/stats` | Dashboard stats |
| POST | `/api/sync?olt_id=` | Sync all OLTs (or single OLT if `olt_id` provided) |

---

## Database Schema

### olts
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| name | TEXT | OLT name |
| ip | TEXT | OLT IP address |
| model | TEXT | OLT model |
| telnet_user | TEXT | Web login username |
| telnet_pass | TEXT | Web login password |

### pons
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| olt_id | INTEGER | FK → olts.id |
| pon_number | INTEGER | PON port number (1-8) |

### onus
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| mac | TEXT | MAC address or serial number |
| onu_name | TEXT | Auto-generated (e.g., PON1-ONU5) |
| onu_index | INTEGER | ONU index on the PON port |
| customer_name | TEXT | Customer name (N/A if unassigned) |
| status | TEXT | online / offline |
| olt_id | INTEGER | FK → olts.id |
| pon_id | INTEGER | FK → pons.id |
| last_sync | TEXT | Last sync timestamp |

### events
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| onu_id | INTEGER | FK → onus.id |
| event_type | TEXT | added / moved / removed / updated / replaced |
| olt_id | INTEGER | FK → olts.id |
| pon_id | INTEGER | FK → pons.id |
| old_olt_name | TEXT | Previous OLT (for moves) |
| old_pon_number | INTEGER | Previous PON (for moves) |
| new_olt_name | TEXT | New OLT |
| new_pon_number | INTEGER | New PON |
| mac | TEXT | Current MAC/SN |
| old_mac | TEXT | Previous MAC (for replacements) |
| onu_name | TEXT | ONU name |
| customer_name | TEXT | Current customer name |
| old_customer_name | TEXT | Previous name (for renames/moves) |
| timestamp | TEXT | Event timestamp |

---

## Event Types

| Type | Description | History Display |
|---|---|---|
| **added** | New ONU detected | Not shown in History |
| **moved** | ONU moved to different OLT/PON | Old → new customer name + location |
| **removed** | ONU disappeared from OLT | Location removed from |
| **updated** | Customer name changed | Old name → new name |
| **replaced** | MAC address changed (same customer) | Old MAC → new MAC |

---

## Important Notes

- **Read-only** — never writes commands to OLTs, only reads via HTTPS web UI
- **LAN only** — designed for local network, no internet required
- **No user login** — web UI is open to anyone on the LAN
- **Credentials** — stored in SQLite database, keep server secure on your LAN
- **Database** — each instance has its own `olt_tracker.db` (gitignored)

## License

MIT
