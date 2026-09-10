import json
import re
import ssl
import urllib.request
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
    conn.execute("DELETE FROM olts WHERE id=?", (olt_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

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
        SELECT o.onu_index, p.pon_number, ol.ip, ol.model
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
    if not ip or not pon or not idx:
        raise HTTPException(400, "Missing OLT IP, PON, or ONU index")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    rx = None
    # Try GPON URL first if model contains GPON, otherwise try both
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
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'[Rr]x\s*(?:optical\s*)?[Ll]evel.*?(-?\d+\.?\d*)', html)
            if not m:
                m = re.search(r'[Rr]eceive\s*[Pp]ower.*?(-?\d+\.?\d*)\s*dBm', html)
            if m:
                rx = m.group(1) + " dBm"
                break
        except Exception:
            pass
    return {"rx_power": rx or "N/A"}

# --- Sync ---
@app.post("/api/sync")
def run_sync():
    result = sync_all()
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
