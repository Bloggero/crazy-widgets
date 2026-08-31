"""
History Store for Antigravity Quota Monitor.
Persists periodic quota readings to a local SQLite database for history & analytics.
Uses Write-Ahead Logging (WAL) and busy timeouts for rock-solid concurrency.
"""
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.services.logger import get_logger

APP_NAME = "AntigravityQuotaMonitor"


class HistoryStore:
    """Stores and queries quota history over time with thread safety and crash resilience."""

    def __init__(self, db_path: Optional[str] = None):
        self._logger = get_logger()
        if db_path is None:
            config_dir = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                APP_NAME
            )
            os.makedirs(config_dir, exist_ok=True)
            self._db_path = os.path.join(config_dir, "quota_history.db")
        else:
            self._db_path = db_path
        
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            self._logger.debug(f"SQLite PRAGMA setup notice: {e}")
        return conn

    def _init_db(self) -> None:
        """Initializes database schema and indexes."""
        try:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS quota_readings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp TEXT NOT NULL,
                            bucket_name TEXT NOT NULL,
                            remaining_fraction REAL NOT NULL,
                            percentage REAL NOT NULL,
                            reset_time TEXT
                        )
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_quota_time 
                        ON quota_readings (bucket_name, timestamp)
                    """)
            finally:
                conn.close()
        except Exception as e:
            self._logger.error(f"Failed to initialize HistoryStore database: {e}")

    def record_snapshot(self, snapshot_or_buckets: Any) -> None:
        """Records a QuotaSnapshot or list of QuotaBucket objects to history."""
        if not snapshot_or_buckets:
            return
        
        if hasattr(snapshot_or_buckets, "buckets"):
            buckets = snapshot_or_buckets.buckets
        elif isinstance(snapshot_or_buckets, list):
            buckets = snapshot_or_buckets
        else:
            return

        if not buckets:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.cursor()
                    for b in buckets:
                        b_name = getattr(b, "display_name", getattr(b, "name", "Unknown"))
                        reset_iso = b.reset_time.isoformat() if getattr(b, "reset_time", None) else ""
                        cursor.execute("""
                            INSERT INTO quota_readings 
                            (timestamp, bucket_name, remaining_fraction, percentage, reset_time)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            now_iso,
                            b_name,
                            float(getattr(b, "remaining_fraction", 0.0)),
                            float(getattr(b, "percentage", 0.0)),
                            reset_iso
                        ))
            finally:
                conn.close()
            
            # Periodically clean up old records (> 30 days)
            self._prune_old_records()
        except Exception as e:
            self._logger.error(f"Error recording quota snapshot to history: {e}")

    def get_history(self, bucket_name: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Retrieves history points within the last N hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            conn = self._get_connection()
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if bucket_name:
                    cursor.execute("""
                        SELECT timestamp, bucket_name, percentage, remaining_fraction, reset_time
                        FROM quota_readings
                        WHERE timestamp >= ? AND bucket_name = ?
                        ORDER BY timestamp ASC
                    """, (cutoff, bucket_name))
                else:
                    cursor.execute("""
                        SELECT timestamp, bucket_name, percentage, remaining_fraction, reset_time
                        FROM quota_readings
                        WHERE timestamp >= ?
                        ORDER BY timestamp ASC
                    """, (cutoff,))
                
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
        except Exception as e:
            self._logger.error(f"Error fetching history points: {e}")
            return []

    def get_unique_bucket_names(self) -> List[str]:
        """Returns distinct bucket names stored in history."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT bucket_name FROM quota_readings ORDER BY bucket_name")
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            self._logger.error(f"Error fetching bucket names: {e}")
            return []

    def _prune_old_records(self, days: int = 30) -> None:
        """Deletes records older than specified days."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM quota_readings WHERE timestamp < ?", (cutoff,))
            finally:
                conn.close()
        except Exception as e:
            self._logger.warning(f"HistoryStore prune warning: {e}")

    def close(self) -> None:
        """Flushes SQLite journal and closes resources."""
        pass
