"""
SQLite Database Manager — vehicle logs, alerts, hourly counts, settings.
"""

import sqlite3
import os
from datetime import datetime
import config


class DatabaseManager:

    def __init__(self, path=None):
        self.path = path or config.DATABASE_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        c = self._conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS vehicle_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER, vehicle_type TEXT, speed REAL DEFAULT 0,
                direction TEXT, timestamp TEXT, snapshot_path TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT, severity TEXT, message TEXT,
                timestamp TEXT, acknowledged INTEGER DEFAULT 0, snapshot_path TEXT
            );
            CREATE TABLE IF NOT EXISTS hourly_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, hour INTEGER, count INTEGER DEFAULT 0,
                UNIQUE(date, hour)
            );
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY, value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_vl_ts ON vehicle_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_al_ts ON alerts(timestamp);
        """)
        c.commit()
        c.close()

    # ── Vehicles ──────────────────────────────────────────────
    def log_vehicle(self, track_id, vtype, speed=0, direction=None, snapshot=None):
        # Extract just the filename for storage
        snap_file = None
        if snapshot:
            import os
            snap_file = os.path.basename(snapshot)
        c = self._conn()
        c.execute("INSERT INTO vehicle_logs (track_id,vehicle_type,speed,direction,timestamp,snapshot_path) VALUES (?,?,?,?,?,?)",
                  (track_id, vtype, speed, direction, datetime.now().isoformat(), snap_file))
        c.commit()
        c.close()


    def get_vehicles(self, limit=100, offset=0, date_f=None, type_f=None):
        c = self._conn()
        q, p = "SELECT * FROM vehicle_logs", []
        conds = []
        if date_f:
            conds.append("DATE(timestamp)=?"); p.append(date_f)
        if type_f:
            conds.append("vehicle_type=?"); p.append(type_f)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        p += [limit, offset]
        rows = c.execute(q, p).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_total_today(self):
        c = self._conn()
        r = c.execute("SELECT COUNT(*) as n FROM vehicle_logs WHERE DATE(timestamp)=DATE('now')").fetchone()
        c.close()
        return r["n"] if r else 0

    # ── Alerts ────────────────────────────────────────────────
    def add_alert(self, alert_type, severity, message, snapshot=None):
        # Extract just the filename for storage
        snap_file = None
        if snapshot:
            import os
            snap_file = os.path.basename(snapshot)
        c = self._conn()
        c.execute("INSERT INTO alerts (alert_type,severity,message,timestamp,snapshot_path) VALUES (?,?,?,?,?)",
                  (alert_type, severity, message, datetime.now().isoformat(), snap_file))
        c.commit()
        alert_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.close()
        return alert_id



    def get_alerts(self, limit=50, unack=False):
        c = self._conn()
        q = "SELECT * FROM alerts"
        p = []
        if unack:
            q += " WHERE acknowledged=0"
        q += " ORDER BY timestamp DESC LIMIT ?"
        p.append(limit)
        rows = c.execute(q, p).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def ack_alert(self, aid):
        c = self._conn()
        c.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (aid,))
        c.commit()
        c.close()

    def unack_count(self):
        c = self._conn()
        r = c.execute("SELECT COUNT(*) as n FROM alerts WHERE acknowledged=0").fetchone()
        c.close()
        return r["n"] if r else 0

    # ── Hourly ────────────────────────────────────────────────
    def inc_hourly(self):
        now = datetime.now()
        c = self._conn()
        c.execute("INSERT INTO hourly_counts (date,hour,count) VALUES (?,?,1) ON CONFLICT(date,hour) DO UPDATE SET count=count+1",
                  (now.strftime("%Y-%m-%d"), now.hour))
        c.commit()
        c.close()

    def get_hourly(self, days=1):
        c = self._conn()
        rows = c.execute("SELECT date,hour,count FROM hourly_counts WHERE date>=DATE('now',?) ORDER BY date,hour",
                         (f"-{days} days",)).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_today_count(self):
        c = self._conn()
        r = c.execute("SELECT COALESCE(SUM(count),0) as n FROM hourly_counts WHERE date=DATE('now')").fetchone()
        c.close()
        return r["n"] if r else 0


    def get_vehicle_detail(self, track_id):
        """Get full detail for a single tracked vehicle."""
        c = self._conn()
        try:
            logs = c.execute(
                "SELECT * FROM vehicle_logs WHERE track_id = ? ORDER BY timestamp DESC",
                (track_id,)
            ).fetchall()
            logs = [dict(r) for r in logs]

            alerts = c.execute(
                "SELECT * FROM alerts WHERE message LIKE ? ORDER BY timestamp DESC",
                (f"%#{track_id}%",)
            ).fetchall()
            alerts = [dict(a) for a in alerts]

            speeds = [l["speed"] for l in logs if l["speed"] and l["speed"] > 0]
            avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0
            max_speed = round(max(speeds), 1) if speeds else 0

            directions = set(l["direction"] for l in logs if l["direction"])
            direction = list(directions)[0] if directions else "—"

            first_seen = logs[-1]["timestamp"] if logs else None
            last_seen = logs[0]["timestamp"] if logs else None
            vtype = logs[0]["vehicle_type"] if logs else "unknown"
            snapshot = logs[0].get("snapshot_path") if logs else None

            return {
                "track_id": track_id,
                "vehicle_type": vtype,
                "snapshot": snapshot,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "direction": direction,
                "detection_count": len(logs),
                "logs": logs,
                "alerts": alerts,
            }
        except Exception as e:
            print(f"[DB] Vehicle detail error: {e}")
            return {
                "track_id": track_id,
                "vehicle_type": "unknown",
                "snapshot": None,
                "first_seen": None,
                "last_seen": None,
                "avg_speed": 0,
                "max_speed": 0,
                "direction": "—",
                "detection_count": 0,
                "logs": [],
                "alerts": [],
            }
        finally:
            c.close()

    
    # ── Settings ──────────────────────────────────────────────
    def get_setting(self, key, default=None):
        c = self._conn()
        r = c.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone()
        c.close()
        return r["value"] if r else default

    def set_setting(self, key, value):
        c = self._conn()
        c.execute("INSERT INTO system_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?",
                  (key, value, value))
        c.commit()
        c.close()