import sqlite3
import os
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

class HistoryDB:
    def __init__(self, db_path="/var/lib/gbot/history.db", retention_days=30):
        self.db_path = db_path
        self.retention_days = retention_days
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Use WAL mode for better SD card performance and concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT,
                    tag TEXT,
                    service TEXT,
                    bytes INTEGER,
                    pkts INTEGER,
                    PRIMARY KEY (date, tag, service)
                )
            """)

    def save_stats(self, stats_date, tag, service, bytes_count, pkts_count):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO daily_stats (date, tag, service, bytes, pkts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, tag, service) DO UPDATE SET
                    bytes = bytes + excluded.bytes,
                    pkts = pkts + excluded.pkts
            """, (stats_date, tag, service, bytes_count, pkts_count))

    def cleanup(self):
        """Delete records older than retention_days and reclaim space."""
        limit_date = str(date.today() - timedelta(days=self.retention_days))
        logger.info(f"Cleaning up history records older than {limit_date}...")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM daily_stats WHERE date < ?", (limit_date,))
                rows_deleted = cursor.rowcount
                if rows_deleted > 0:
                    logger.info(f"Deleted {rows_deleted} old records. Reclaiming space...")
                    conn.execute("VACUUM") # Physically shrink the database file
            return rows_deleted
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0

    def get_report(self, target_date):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT tag, service, bytes, pkts FROM daily_stats WHERE date = ?", 
                (target_date,)
            )
            report = {}
            for tag, service, b, p in cursor:
                if tag not in report: report[tag] = []
                report[tag].append({"service": service, "bytes": b, "packets": p})
            return report
