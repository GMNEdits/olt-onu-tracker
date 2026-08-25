import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "olt_tracker.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS olts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            ip TEXT NOT NULL,
            model TEXT DEFAULT '',
            telnet_user TEXT DEFAULT '',
            telnet_pass TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS pons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            olt_id INTEGER NOT NULL,
            pon_number INTEGER NOT NULL,
            FOREIGN KEY (olt_id) REFERENCES olts(id),
            UNIQUE(olt_id, pon_number)
        );

        CREATE TABLE IF NOT EXISTS onus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac TEXT NOT NULL,
            onu_name TEXT NOT NULL DEFAULT '',
            customer_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'offline',
            olt_id INTEGER NOT NULL,
            pon_id INTEGER NOT NULL,
            last_sync TEXT,
            FOREIGN KEY (olt_id) REFERENCES olts(id),
            FOREIGN KEY (pon_id) REFERENCES pons(id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            onu_id INTEGER,
            event_type TEXT NOT NULL,
            olt_id INTEGER,
            pon_id INTEGER,
            old_olt_name TEXT DEFAULT '',
            old_pon_number INTEGER DEFAULT 0,
            new_olt_name TEXT DEFAULT '',
            new_pon_number INTEGER DEFAULT 0,
            mac TEXT DEFAULT '',
            onu_name TEXT DEFAULT '',
            customer_name TEXT DEFAULT '',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (olt_id) REFERENCES olts(id),
            FOREIGN KEY (pon_id) REFERENCES pons(id)
        );

        CREATE INDEX IF NOT EXISTS idx_onu_mac ON onus(mac);
        CREATE INDEX IF NOT EXISTS idx_onu_name ON onus(onu_name);
        CREATE INDEX IF NOT EXISTS idx_onu_customer ON onus(customer_name);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    """)
    conn.commit()
    conn.close()
