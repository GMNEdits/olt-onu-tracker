import json
import re
import ssl
import threading
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from database import get_conn, init_db
from sync import sync_all

app = FastAPI()
init_db()

# Only one sync may run at a time (across ALL clients/tabs).
# Concurrent syncs log into the same OLT web UIs, killing each other's
# sessions and letting stale scrape data overwrite fresh status changes.
_sync_mutex = threading.Lock()

app.mount("/static", StaticFiles(directory="static"), name="static")

class OLTCreate(BaseModel):
    name: str
    ip: str
    model: str = ""
    telnet_user: str = ""
    telnet_pass: str = ""

class PONCreate(BaseModel):
    olt_id: int
    pon_number: int

class ONUCreate(BaseModel):
    mac: str
    onu_name: str = ""
    customer_name: str = ""
    status: str = "offline"
    olt_id: int
    pon_id: int

class ONUUpdate(BaseModel):
    mac: str = ""
    onu_name: str = ""
    customer_name: str = ""
    status: str = ""
    olt_id: int = 0
    pon_id: int = 0

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def record_event(conn, event_type, onu=None, olt_id=None, pon_id=None,
                 old_olt_name="", old_pon_number=0,
                 new_olt_name="", new_pon_number=0):
    conn.execute(
        "INSERT INTO events (onu_id, event_type, olt_id, pon_id, old_olt_name, old_pon_number, new_olt_name, new_pon_number, mac, onu_name, customer_name, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (onu["id"] if onu else None,
         event_type,
         olt_id,
         pon_id,
         old_olt_name,
         old_pon_number,
         new_olt_name,
         new_pon_number,
         onu["mac"] if onu else "",
         onu["onu_name"] if onu else "",
         onu["customer_name"] if onu else "",
         now_str())
    )

@app.get("/")
def root():
    return FileResponse("static/index.html")

# --- OLTs ---
@app.get("/api/olts")
def list_olts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM olts ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/olts")
def add_olt(data: OLTCreate):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO olts (name, ip, model, telnet_user, telnet_pass) VALUES (?, ?, ?, ?, ?)",
                     (data.name, data.ip, data.model, data.telnet_user, data.telnet_pass))
        conn.commit()
        olt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return {"id": olt_id, "ok": True}
    except Exception as e:
        conn.close()
        raise HTTPException(400, str(e))

@app.delete("/api/olts/{olt_id}")
def delete_olt(olt_id: int):
    conn = get_conn()
    try:
        pon_ids = [r["id"] for r in conn.execute("SELECT id FROM pons WHERE olt_id=?", (olt_id,)).fetchall()]
        if pon_ids:
            placeholders = ",".join("?" * len(pon_ids))
            conn.execute(f"DELETE FROM events WHERE olt_id=? OR pon_id IN ({placeholders})", [olt_id] + pon_ids)
        else:
            conn.execute("DELETE FROM events WHERE olt_id=?", (olt_id,))
        conn.execute("DELETE FROM onus WHERE olt_id=?", (olt_id,))
        conn.execute("DELETE FROM pons WHERE olt_id=?", (olt_id,))
        conn.execute("DELETE FROM olts WHERE id=?", (olt_id,))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()

# --- PONs ---
@app.get("/api/olts/{olt_id}/pons")
def list_pons(olt_id: int):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pons WHERE olt_id=? ORDER BY pon_number", (olt_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/pons")
def add_pon(data: PONCreate):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO pons (olt_id, pon_number) VALUES (?, ?)", (data.olt_id, data.pon_number))
        conn.commit()
        pon_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return {"id": pon_id, "ok": True}
    except Exception as e:
        conn.close()
        raise HTTPException(400, str(e))

# --- ONUs ---
@app.get("/api/onus")
def list_onus(q: str = ""):
    conn = get_conn()
    if q:
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT o.*, ol.name as olt_name, p.pon_number
            FROM onus o
            JOIN olts ol ON o.olt_id = ol.id
            JOIN pons p ON o.pon_id = p.id
            WHERE o.mac LIKE ? OR o.onu_name LIKE ? OR o.customer_name LIKE ?
            ORDER BY ol.name, p.pon_number, o.onu_name
        """, (like, like, like)).fetchall()
    else:
        rows = conn.execute("""
            SELECT o.*, ol.name as olt_name, p.pon_number
            FROM onus o
            JOIN olts ol ON o.olt_id = ol.id
            JOIN pons p ON o.pon_id = p.id
            ORDER BY ol.name, p.pon_number, o.onu_name
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/onus")
def add_onu(data: ONUCreate):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM onus WHERE mac=?", (data.mac,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "MAC already exists")
    conn.execute(
        "INSERT INTO onus (mac, onu_name, customer_name, status, olt_id, pon_id) VALUES (?, ?, ?, ?, ?, ?)",
        (data.mac.upper(), data.onu_name, data.customer_name, data.status, data.olt_id, data.pon_id)
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    onu = dict(conn.execute("SELECT * FROM onus WHERE id=?", (new_id,)).fetchone())
    olt_name = conn.execute("SELECT name FROM olts WHERE id=?", (data.olt_id,)).fetchone()[0]
    pon_num = conn.execute("SELECT pon_number FROM pons WHERE id=?", (data.pon_id,)).fetchone()[0]
    record_event(conn, "added", onu, data.olt_id, data.pon_id,
                 new_olt_name=olt_name, new_pon_number=pon_num)
    conn.commit()
    conn.close()
    return {"id": new_id, "ok": True}

@app.put("/api/onus/{onu_id}")
def update_onu(onu_id: int, data: ONUUpdate):
    conn = get_conn()
    old = conn.execute("SELECT * FROM onus WHERE id=?", (onu_id,)).fetchone()
    if not old:
        conn.close()
        raise HTTPException(404, "ONU not found")
    old = dict(old)
    old_olt = dict(conn.execute("SELECT name FROM olts WHERE id=?", (old["olt_id"],)).fetchone())
    old_pon = dict(conn.execute("SELECT pon_number FROM pons WHERE id=?", (old["pon_id"],)).fetchone())

    new_mac = data.mac.upper() if data.mac else old["mac"]
    new_name = data.onu_name if data.onu_name else old["onu_name"]
    new_cust = data.customer_name if data.customer_name else old["customer_name"]
    new_status = data.status if data.status else old["status"]
    new_olt = data.olt_id if data.olt_id else old["olt_id"]
    new_pon = data.pon_id if data.pon_id else old["pon_id"]

    conn.execute(
        "UPDATE onus SET mac=?, onu_name=?, customer_name=?, status=?, olt_id=?, pon_id=? WHERE id=?",
        (new_mac, new_name, new_cust, new_status, new_olt, new_pon, onu_id)
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM onus WHERE id=?", (onu_id,)).fetchone())
    new_olt_name = conn.execute("SELECT name FROM olts WHERE id=?", (new_olt,)).fetchone()[0]
    new_pon_num = conn.execute("SELECT pon_number FROM pons WHERE id=?", (new_pon,)).fetchone()[0]

    event_type = "updated"
    if new_olt != old["olt_id"] or new_pon != old["pon_id"]:
        event_type = "moved"
    elif new_mac != old["mac"]:
        event_type = "replaced"

    record_event(conn, event_type, updated, new_olt, new_pon,
                 old_olt_name=old_olt["name"], old_pon_number=old_pon["pon_number"],
                 new_olt_name=new_olt_name, new_pon_number=new_pon_num)
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/onus/{onu_id}")
def delete_onu(onu_id: int):
    conn = get_conn()
    old = conn.execute("SELECT * FROM onus WHERE id=?", (onu_id,)).fetchone()
    if not old:
        conn.close()
        raise HTTPException(404, "ONU not found")
    old = dict(old)
    old_olt = dict(conn.execute("SELECT name FROM olts WHERE id=?", (old["olt_id"],)).fetchone())
    old_pon = dict(conn.execute("SELECT pon_number FROM pons WHERE id=?", (old["pon_id"],)).fetchone())
    record_event(conn, "removed", old, old["olt_id"], old["pon_id"],
                 old_olt_name=old_olt["name"], old_pon_number=old_pon["pon_number"])
    conn.execute("DELETE FROM onus WHERE id=?", (onu_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# --- Events ---
@app.get("/api/events")
def list_events(onu_id: int = 0, limit: int = 100):
    conn = get_conn()
    if onu_id:
        rows = conn.execute(
            "SELECT * FROM events WHERE onu_id=? ORDER BY timestamp DESC LIMIT ?",
            (onu_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/changes")
def list_changes(since: str = "", since_id: int = 0, limit: int = 100):
    conn = get_conn()
    if since_id > 0:
        rows = conn.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit)
        ).fetchall()
    elif since:
        rows = conn.execute(
            "SELECT * FROM events WHERE timestamp > ? ORDER BY id ASC LIMIT ?",
            (since, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Operations ---
@app.post("/api/operations")
def start_operation(body: dict):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Operation name required")
    conn = get_conn()
    active = conn.execute("SELECT id FROM operations WHERE status='active'").fetchone()
    if active:
        conn.close()
        raise HTTPException(400, "An operation is already active. End it first.")
    now = now_str()
    conn.execute("INSERT INTO operations (name, start_time, status) VALUES (?, ?, 'active')", (name, now))
    conn.commit()
    op_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id": op_id, "name": name, "start_time": now, "status": "active"}

@app.put("/api/operations/{op_id}")
def end_operation(op_id: int):
    conn = get_conn()
    op = conn.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
    if not op:
        conn.close()
        raise HTTPException(404, "Operation not found")
    if op["status"] != "active":
        conn.close()
        raise HTTPException(400, "Operation already ended")
    now = now_str()
    conn.execute("UPDATE operations SET end_time=?, status='completed' WHERE id=?", (now, op_id))
    conn.commit()
    conn.close()
    return {"id": op_id, "status": "completed", "end_time": now}

@app.get("/api/operations")
def list_operations():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM operations ORDER BY start_time DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/operations/{op_id}/report")
def operation_report(op_id: int):
    conn = get_conn()
    op = conn.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
    if not op:
        conn.close()
        raise HTTPException(404, "Operation not found")
    start = op["start_time"]
    end = op["end_time"] or now_str()
    events = conn.execute(
        "SELECT * FROM events WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
        (start, end)
    ).fetchall()
    events = [dict(e) for e in events]
    by_mac = {}
    for e in events:
        mac = e.get("mac") or ""
        if mac not in by_mac:
            by_mac[mac] = {"mac": mac, "customer_name": e.get("customer_name", ""), "events": []}
        by_mac[mac]["events"].append(e)
    rx_rows = conn.execute("""
        SELECT rh.onu_id, rh.rx_value, rh.rx_text, rh.timestamp, o.mac, o.customer_name
        FROM rx_history rh
        JOIN onus o ON rh.onu_id = o.id
        WHERE rh.timestamp >= ? AND rh.timestamp <= ?
        ORDER BY rh.timestamp ASC
    """, (start, end)).fetchall()
    rx_by_mac = {}
    for r in rx_rows:
        d = dict(r)
        mac = d.get("mac") or ""
        if mac not in rx_by_mac:
            rx_by_mac[mac] = []
        rx_by_mac[mac].append({"rx_value": d["rx_value"], "rx_text": d["rx_text"], "timestamp": d["timestamp"]})
    conn.close()
    return {
        "operation": dict(op),
        "total_events": len(events),
        "onus_affected": len(by_mac),
        "by_mac": list(by_mac.values()),
        "rx_history": rx_by_mac,
    }

@app.get("/api/stats")
def stats():
    conn = get_conn()
    olts_count = conn.execute("SELECT COUNT(*) FROM olts").fetchone()[0]
    pons_count = conn.execute("SELECT COUNT(*) FROM pons").fetchone()[0]
    onus_count = conn.execute("SELECT COUNT(*) FROM onus").fetchone()[0]
    online = conn.execute("SELECT COUNT(*) FROM onus WHERE status='online'").fetchone()[0]
    new_onus_count = conn.execute("SELECT COUNT(*) FROM onus WHERE customer_name='N/A' OR customer_name=''").fetchone()[0]
    conn.close()
    return {"olts": olts_count, "pons": pons_count, "onus": onus_count, "online": online, "new_onus": new_onus_count}

@app.get("/api/new-onus")
def list_new_onus():
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, ol.name as olt_name, p.pon_number
        FROM onus o
        JOIN olts ol ON o.olt_id = ol.id
        JOIN pons p ON o.pon_id = p.id
        WHERE o.customer_name='N/A' OR o.customer_name=''
        ORDER BY ol.name, p.pon_number, o.mac
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/onus/{onu_id}/optical")
def get_optical(onu_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT o.onu_index, p.pon_number, ol.ip, ol.model, ol.telnet_user, ol.telnet_pass
        FROM onus o
        JOIN pons p ON o.pon_id = p.id
        JOIN olts ol ON o.olt_id = ol.id
        WHERE o.id=?
    """, (onu_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "ONU not found")
    ip = row["ip"]
    pon = row["pon_number"]
    idx = row["onu_index"]
    model = (row["model"] or "").upper()
    user = row["telnet_user"] or "admin"
    passwd = row["telnet_pass"] or "admin"
    if not ip or not pon or not idx:
        raise HTTPException(400, "Missing OLT IP, PON, or ONU index")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(cookie_jar),
    )

    login_data = urllib.parse.urlencode({"user": user, "pass": passwd, "who": "100"}).encode("utf-8")
    for login_path in ["/action/main.html", "/action/login.html"]:
        try:
            req = urllib.request.Request(f"https://{ip}{login_path}", data=login_data)
            req.add_header("User-Agent", "Mozilla/5.0")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            resp = opener.open(req, timeout=10)
            resp.read(2048)
            break
        except Exception:
            continue

    rx = None
    urls = []
    if "GPON" in model:
        urls = [f"https://{ip}/action/onuoptical.html?ponid={pon}&onuid={idx}"]
    elif "EPON" in model:
        urls = [f"https://{ip}/action/onuBasic.html?gponid={pon}&gonuid={idx}"]
    else:
        urls = [
            f"https://{ip}/action/onuoptical.html?ponid={pon}&onuid={idx}",
            f"https://{ip}/action/onuBasic.html?gponid={pon}&gonuid={idx}",
        ]
    for url in urls:
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = opener.open(req, timeout=10)
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'[Rr]x\s*(?:optical\s*)?[Ll]evel.*?(-?\d+\.?\d*)', html)
            if not m:
                m = re.search(r'[Rr]eceive\s*[Pp]ower.*?(-?\d+\.?\d*)\s*dBm', html)
            if m:
                rx = m.group(1) + " dBm"
                try:
                    rx_val = float(m.group(1))
                    conn2 = get_conn()
                    conn2.execute(
                        "INSERT INTO rx_history (onu_id, rx_value, rx_text, timestamp) VALUES (?, ?, ?, ?)",
                        (onu_id, rx_val, rx, now_str())
                    )
                    conn2.commit()
                    conn2.close()
                except Exception:
                    pass
                break
        except Exception:
            pass
    return {"rx_power": rx or "N/A"}

@app.get("/api/onus/{onu_id}/rx-history")
def get_rx_history(onu_id: int, limit: int = 20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT rx_value, rx_text, timestamp FROM rx_history WHERE onu_id=? ORDER BY timestamp DESC LIMIT ?",
        (onu_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- PON View (grouped ONUs by OLT → PON) ---
@app.get("/api/pon-view")
def pon_view(olt_id: int = 0):
    conn = get_conn()
    if olt_id:
        olts = conn.execute("SELECT * FROM olts WHERE id=? ORDER BY name", (olt_id,)).fetchall()
    else:
        olts = conn.execute("SELECT * FROM olts ORDER BY name").fetchall()

    result = []
    for olt in olts:
        olt = dict(olt)
        pons = conn.execute("SELECT * FROM pons WHERE olt_id=? ORDER BY pon_number", (olt["id"],)).fetchall()
        pon_list = []
        for pon in pons:
            pon = dict(pon)
            onus = conn.execute("""
                SELECT id, onu_index, mac, customer_name, status
                FROM onus WHERE pon_id=?
                ORDER BY onu_index
            """, (pon["id"],)).fetchall()
            online = sum(1 for o in onus if o["status"] == "online")
            pon_list.append({
                "pon_id": pon["id"],
                "pon_number": pon["pon_number"],
                "total": len(onus),
                "online": online,
                "offline": len(onus) - online,
                "onus": [dict(o) for o in onus],
            })
        result.append({
            "olt_id": olt["id"],
            "olt_name": olt["name"],
            "ip": olt["ip"],
            "model": olt.get("model", ""),
            "pons": pon_list,
        })
    conn.close()
    return result

# --- Sync ---
@app.post("/api/sync")
def run_sync(olt_id: int = 0):
    if olt_id:
        conn = get_conn()
        olt = conn.execute("SELECT * FROM olts WHERE id=?", (olt_id,)).fetchone()
        conn.close()
        if not olt:
            raise HTTPException(404, "OLT not found")
    if not _sync_mutex.acquire(blocking=False):
        return {"ok": False, "already_running": True, "olts_synced": 0,
                "total_added": 0, "total_removed": 0, "total_moved": 0,
                "total_replaced": 0, "errors": []}
    try:
        result = sync_all(olt_id=olt_id)
    finally:
        _sync_mutex.release()
    result["already_running"] = False
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
