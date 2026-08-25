import re
import ssl
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime
from database import get_conn


# ============================================================
# Web Scraper: Unified for GPON and EPON OLTs
# ============================================================

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _create_opener():
    """Create HTTPS opener that ignores self-signed certs."""
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_SSL_CTX),
        urllib.request.HTTPCookieProcessor(cookie_jar),
    )
    return opener


def _login(opener, ip, user, passwd):
    """Try logging in. Returns 'gpon', 'epon', or raises error."""
    base_url = f"https://{ip}"
    login_data = urllib.parse.urlencode({
        "user": user, "pass": passwd, "who": "100",
    }).encode("utf-8")

    for login_path in ["/action/main.html", "/action/login.html"]:
        try:
            req = urllib.request.Request(f"{base_url}{login_path}", data=login_data)
            req.add_header("User-Agent", "Mozilla/5.0")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            resp = opener.open(req, timeout=10)
            resp.read(2048)
            return "gpon" if "main.html" in login_path else "epon"
        except Exception:
            continue

    raise RuntimeError(f"Login failed for {ip}")


def _fetch_gpon(opener, ip):
    """Scrape GPON OLT: fetch PON1-4 with single session."""

    results = []
    for pon in [1, 2, 3, 4]:
        url = f"https://{ip}/action/onuauthinfo.html?select={pon}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            resp = opener.open(req, timeout=15)
            html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            continue

        # GPON rows: <td>GPON0/X:Y</td> ... Status ... Description ... Model ... Profile ... Mode ... Info(SN)
        row_pattern = re.compile(
            r"<td>\s*GPON0/(\d+):(\d+)\s*</td>\s*"
            r"<td[^>]*>.*?>(Online|Offline)</.*?</td>\s*"
            r"<td[^>]*>\s*(.*?)\s*</td>\s*"       # Description
            r"<td[^>]*>\s*(.*?)\s*</td>\s*"        # Model
            r"<td[^>]*>\s*(.*?)\s*</td>\s*"        # Profile
            r"<td[^>]*>\s*(.*?)\s*</td>\s*"        # Mode
            r"<td[^>]*>\s*(.*?)\s*</td>\s*"        # Info (SN)
            r"<td[^>]*>",                            # Action (don't capture)
            re.IGNORECASE | re.DOTALL,
        )

        for m in row_pattern.finditer(html):
            pon_port = int(m.group(1))
            onu_id = m.group(2)
            status = m.group(3).strip().lower()
            customer_name = re.sub(r"<[^>]+>", "", m.group(4)).strip()
            sn = re.sub(r"<[^>]+>", "", m.group(8)).strip()

            if not sn:
                continue

            results.append({
                "onu_id": onu_id,
                "mac": sn.upper(),
                "onu_name": f"PON{pon_port}-ONU{onu_id}",
                "customer_name": customer_name,
                "status": status,
                "pon_number": pon_port,
            })

    return results


def _fetch_epon(opener, ip):
    """Scrape EPON OLT: fetch all PONs with select=255, parse MAC."""

    url = f"https://{ip}/action/onuauthinfo.html?select=255"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = opener.open(req, timeout=15)
    html = resp.read().decode("utf-8", errors="ignore")

    results = []
    row_pattern = re.compile(
        r"<td\s+class=['\"]hd['\"]>\s*EPON0/(\d+):(\d+)\s*</td>\s*"
        r"<td[^>]*>.*?>(Online|Offline)</.*?</td>\s*"
        r"<td[^>]*>\s*([0-9A-Fa-f:]{17})\s*</td>\s*"
        r"<td[^>]*>\s*(.*?)\s*</td>",
        re.IGNORECASE | re.DOTALL,
    )

    for m in row_pattern.finditer(html):
        pon_port = int(m.group(1))
        onu_id = m.group(2)
        status = m.group(3).strip().lower()
        mac = m.group(4).strip().upper()
        customer_name = re.sub(r"<[^>]+>", "", m.group(5)).strip()

        results.append({
            "onu_id": onu_id,
            "mac": mac,
            "onu_name": f"PON{pon_port}-ONU{onu_id}",
            "customer_name": customer_name,
            "status": status,
            "pon_number": pon_port,
        })

    return results


def sync_olt(olt):
    """Detect OLT type and scrape ONUs via web UI."""
    ip = olt["ip"]
    user = olt.get("telnet_user") or "admin"
    passwd = olt.get("telnet_pass") or "admin"

    print(f"  [SYNC] {olt['name']} ({ip}) — connecting to web UI...")

    opener = _create_opener()
    _login(opener, ip, user, passwd)

    # Detect type from first PON page
    req = urllib.request.Request(f"https://{ip}/action/onuauthinfo.html?select=1")
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = opener.open(req, timeout=10)
    sample = resp.read(4096).decode("utf-8", errors="ignore")
    is_gpon = "GPON" in sample

    if is_gpon:
        print(f"  [SYNC] {olt['name']} — GPON, fetching PON1-4...")
        return _fetch_gpon(opener, ip)
    else:
        print(f"  [SYNC] {olt['name']} — EPON, fetching all PONs...")
        return _fetch_epon(opener, ip)


# ============================================================
# Sync Logic
# ============================================================

def diff_and_update(olt_id, new_onus):
    """Compare new_onus from OLT with database. Record changes."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    old_rows = conn.execute("SELECT * FROM onus WHERE olt_id=?", (olt_id,)).fetchall()
    old_by_mac = {r["mac"]: dict(r) for r in old_rows}

    olt_row = conn.execute("SELECT name FROM olts WHERE id=?", (olt_id,)).fetchone()
    olt_name = olt_row["name"] if olt_row else ""

    new_by_mac = {item["mac"]: item for item in new_onus}

    added, removed, moved = [], [], []

    for mac, new_data in new_by_mac.items():
        if mac not in old_by_mac:
            other = conn.execute(
                "SELECT o.*, ol.name as olt_name, p.pon_number FROM onus o "
                "JOIN olts ol ON o.olt_id = ol.id JOIN pons p ON o.pon_id = p.id "
                "WHERE o.mac=?", (mac,)
            ).fetchone()

            new_pon = ensure_pon(conn, olt_id, new_data.get("pon_number", 1))

            if other:
                other = dict(other)
                conn.execute(
                    "UPDATE onus SET olt_id=?, pon_id=?, status=?, customer_name=?, last_sync=? WHERE id=?",
                    (olt_id, new_pon, new_data.get("status", "online"),
                     new_data.get("customer_name", ""), now, other["id"])
                )
                conn.execute(
                    "INSERT INTO events (onu_id, event_type, olt_id, pon_id, old_olt_name, old_pon_number, new_olt_name, new_pon_number, mac, onu_name, customer_name, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (other["id"], "moved", olt_id, new_pon,
                     other["olt_name"], other["pon_number"],
                     olt_name, new_data.get("pon_number", 1),
                     mac, new_data.get("onu_name", ""), new_data.get("customer_name", ""), now)
                )
                moved.append(new_data)
            else:
                conn.execute(
                    "INSERT INTO onus (mac, onu_name, customer_name, status, olt_id, pon_id, last_sync) VALUES (?,?,?,?,?,?,?)",
                    (mac, new_data.get("onu_name", ""), new_data.get("customer_name", ""),
                     new_data.get("status", "online"), olt_id, new_pon, now)
                )
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                pon_num = new_data.get("pon_number", 1)
                conn.execute(
                    "INSERT INTO events (onu_id, event_type, olt_id, pon_id, new_olt_name, new_pon_number, mac, onu_name, customer_name, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (new_id, "added", olt_id, new_pon, olt_name, pon_num,
                     mac, new_data.get("onu_name", ""), new_data.get("customer_name", ""), now)
                )
                added.append(new_data)
        else:
            old = old_by_mac[mac]
            new_pon = ensure_pon(conn, olt_id, new_data.get("pon_number", 1))
            if old["olt_id"] != olt_id or old["pon_id"] != new_pon:
                old_pon = conn.execute("SELECT pon_number FROM pons WHERE id=?", (old["pon_id"],)).fetchone()
                old_pon_num = old_pon["pon_number"] if old_pon else 0
                conn.execute(
                    "UPDATE onus SET olt_id=?, pon_id=?, status=?, customer_name=?, last_sync=? WHERE id=?",
                    (olt_id, new_pon, new_data.get("status", "online"),
                     new_data.get("customer_name", ""), now, old["id"])
                )
                conn.execute(
                    "INSERT INTO events (onu_id, event_type, olt_id, pon_id, old_olt_name, old_pon_number, new_olt_name, new_pon_number, mac, onu_name, customer_name, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (old["id"], "moved", olt_id, new_pon,
                     olt_name, old_pon_num, olt_name, new_data.get("pon_number", 1),
                     mac, new_data.get("onu_name", ""), new_data.get("customer_name", ""), now)
                )
                moved.append(new_data)
            else:
                new_cust = new_data.get("customer_name", "")
                if new_cust and new_cust != old.get("customer_name", ""):
                    conn.execute("UPDATE onus SET customer_name=?, last_sync=? WHERE id=?",
                                 (new_cust, now, old["id"]))
                conn.execute("UPDATE onus SET status=?, last_sync=? WHERE id=?",
                             (new_data.get("status", "online"), now, old["id"]))

    for mac, old_data in old_by_mac.items():
        if mac not in new_by_mac:
            old_pon = conn.execute("SELECT pon_number FROM pons WHERE id=?", (old_data["pon_id"],)).fetchone()
            old_pon_num = old_pon["pon_number"] if old_pon else 0
            conn.execute(
                "INSERT INTO events (onu_id, event_type, olt_id, pon_id, old_olt_name, old_pon_number, mac, onu_name, customer_name, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (old_data["id"], "removed", olt_id, old_data["pon_id"],
                 olt_name, old_pon_num, mac, old_data.get("onu_name", ""),
                 old_data.get("customer_name", ""), now)
            )
            conn.execute("DELETE FROM onus WHERE id=?", (old_data["id"],))
            removed.append({"mac": mac})

    conn.commit()
    conn.close()
    return {"added": added, "removed": removed, "moved": moved}


def ensure_pon(conn, olt_id, pon_number):
    """Get or create PON record, return pon_id."""
    row = conn.execute(
        "SELECT id FROM pons WHERE olt_id=? AND pon_number=?", (olt_id, pon_number)
    ).fetchone()
    if row:
        return row["id"]
    conn.execute("INSERT INTO pons (olt_id, pon_number) VALUES (?, ?)", (olt_id, pon_number))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def sync_all():
    """Sync all OLTs. Returns summary dict."""
    conn = get_conn()
    olts = conn.execute("SELECT * FROM olts").fetchall()
    conn.close()

    if not olts:
        return {"ok": False, "error": "No OLTs configured"}

    results = {"olts_synced": 0, "total_added": 0, "total_removed": 0, "total_moved": 0, "errors": []}

    for olt in olts:
        olt = dict(olt)
        try:
            onus = sync_olt(olt)
            if not onus:
                results["errors"].append(f"{olt['name']}: No ONUs found or connection failed")
                continue

            diff = diff_and_update(olt["id"], onus)
            results["olts_synced"] += 1
            results["total_added"] += len(diff["added"])
            results["total_removed"] += len(diff["removed"])
            results["total_moved"] += len(diff["moved"])
            print(f"  [OK] {olt['name']}: +{len(diff['added'])} -{len(diff['removed'])} ~{len(diff['moved'])}")

        except Exception as e:
            results["errors"].append(f"{olt['name']}: {str(e)}")
            print(f"  [ERROR] {olt['name']}: {e}")

    results["ok"] = len(results["errors"]) == 0 or results["olts_synced"] > 0
    return results
