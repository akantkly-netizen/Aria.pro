import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

class JobStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, url TEXT NOT NULL, quality TEXT NOT NULL, status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0, downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER, speed TEXT, filename TEXT, file_path TEXT, error TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
            """)
            db.execute("UPDATE jobs SET status='queued', updated_at=? WHERE status='running' AND cancel_requested=0", (self._now(),))
            db.execute("UPDATE jobs SET status='cancelled', updated_at=? WHERE status='running' AND cancel_requested=1", (self._now(),))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _row(row):
        if row is None: return None
        item = dict(row)
        item["metadata"] = json.loads(item.get("metadata") or "{}")
        item.pop("cancel_requested", None)
        item.pop("file_path", None)
        return item

    def create(self, job_id: str, url: str, quality: str) -> dict[str, Any]:
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO jobs(id,url,quality,status,created_at,updated_at) VALUES(?,?,?,'queued',?,?)", (job_id,url,quality,now,now))
            return self._row(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def get(self, job_id: str):
        with self._lock, self._connect() as db:
            return self._row(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list(self, limit: int = 25):
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._row(row) for row in rows]

    def claim(self):
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None: return None
            now = self._now()
            changed = db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=? AND status='queued'", (now,row['id'])).rowcount
            if not changed: return None
            return row['id']

    def progress(self, job_id: str, percent: float, downloaded: int, total: int | None, speed: str | None, filename: str | None):
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET progress=?,downloaded_bytes=?,total_bytes=?,speed=?,filename=COALESCE(?,filename),updated_at=? WHERE id=? AND status='running'", (max(0,min(100,percent)),downloaded,total,speed,filename,self._now(),job_id))

    def cancelled(self, job_id: str) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
            return bool(row and row[0])

    def finish(self, job_id: str, file_path: str, filename: str, metadata: dict):
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET status='succeeded',progress=100,file_path=?,filename=?,metadata=?,updated_at=? WHERE id=?", (file_path,filename,json.dumps(metadata,ensure_ascii=False),self._now(),job_id))

    def fail(self, job_id: str, error: str, cancelled: bool = False):
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?", ('cancelled' if cancelled else 'failed',error[:1500],self._now(),job_id))

    def request_cancel(self, job_id: str):
        with self._lock, self._connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row: return None
            if row['status'] == 'queued':
                db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=?", (self._now(),job_id))
            elif row['status'] == 'running':
                db.execute("UPDATE jobs SET cancel_requested=1,updated_at=? WHERE id=?", (self._now(),job_id))
            updated = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row(updated)

    def prune(self, hours: int = 48):
        cutoff = (datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT id,file_path FROM jobs WHERE updated_at<? AND status IN ('succeeded','failed','cancelled')", (cutoff,)).fetchall()
            db.executemany("DELETE FROM jobs WHERE id=?", [(row['id'],) for row in rows])
            return [row['file_path'] for row in rows if row['file_path']]
