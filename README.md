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

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/olt-onu-tracker.git
cd olt-onu-tracker
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
python3 main.py
```

Open `http://YOUR_LAPTOP_IP:8000` in any browser on the same LAN.

### 4. Auto-start on boot (Linux/systemd)

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
├── server.sh          # Helper script (start/stop/restart)
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
