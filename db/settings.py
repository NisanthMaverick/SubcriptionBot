import logging
import json
from typing import List, Any
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class SettingQueries(ConnectionManager):
    def get_setting(self, key: str, default: Any = None) -> Any:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
                    row = cursor.fetchone()
                    if row:
                        return row[0]
            except Exception:
                pass
        return default

    def get_all_settings(self) -> dict:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT key, value FROM settings")
                    rows = cursor.fetchall()
                    return {row[0]: row[1] for row in rows}
            except Exception:
                pass
        return {}

    def set_setting(self, key: str, value: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO settings (key, value) VALUES (%s, %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """, (key, str(value)))
            except Exception as e:
                logger.warning(f"set_setting failed on DB {url[:30]}: {e}")

    def get_upi_ids(self) -> List[str]:
        val = self.get_setting("upi_ids")
        if val:
            try:
                return json.loads(val)
            except Exception:
                return [val]
        old_single = self.get_setting("upi_id")
        if old_single:
            return [old_single]
        return ["nisanthlatha2001-3@okaxis"]

    def save_upi_ids(self, upi_list: List[str]) -> None:
        self.set_setting("upi_ids", json.dumps(upi_list[:3]))
