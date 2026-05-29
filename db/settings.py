import logging
import json
from typing import List, Any
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

import time

_settings_cache = {}
_settings_cache_time = 0

class SettingQueries(ConnectionManager):
    def get_setting(self, key: str, default: Any = None) -> Any:
        global _settings_cache, _settings_cache_time
        if time.time() - _settings_cache_time > 300:
            try:
                rows = self._run_read_query("SELECT key, value FROM settings")
                _settings_cache = {row[0]: row[1] for row in rows}
                _settings_cache_time = time.time()
            except Exception:
                pass
                
        if key in _settings_cache:
            return _settings_cache[key]
            
        try:
            row = self._run_read_query_one("SELECT value FROM settings WHERE key = %s", (key,))
            if row:
                _settings_cache[key] = row[0]
                return row[0]
            return default
        except Exception:
            return default

    def get_all_settings(self) -> dict:
        try:
            rows = self._run_read_query("SELECT key, value FROM settings")
            return {row[0]: row[1] for row in rows}
        except Exception:
            return {}

    def clear_settings(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM settings")
            except Exception:
                pass

    def set_setting(self, key: str, value: str, overwrite: bool = True) -> None:
        global _settings_cache
        _settings_cache[key] = str(value)
        
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    if overwrite:
                        cursor.execute("""
                            INSERT INTO settings (key, value) VALUES (%s, %s)
                            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                        """, (key, str(value)))
                    else:
                        cursor.execute("""
                            INSERT INTO settings (key, value) VALUES (%s, %s)
                            ON CONFLICT (key) DO NOTHING
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

    def _seed_default_settings(self) -> None:
        defaults = {
            "welcome_msg_text": (
                "👋 **Welcome to our Premium VIP Subscription Bot!**\n\n"
                "Unlock exclusive premium features, high-speed downloads, and VIP channel access instantly.\n\n"
                "🚀 Type /plan or click below to browse available subscription plans and start your premium journey today!\n\n"
                "💬 *Facing any issues or have questions?*\n"
                "Please contact our Admin directly anytime for prompt assistance!"
            ),
            "welcome_custom_buttons": "[]",
            "upi_ids": '["nisanthlatha2001-3@okaxis"]',
            "payment_validity": "Pay within 30 minutes",
            "expiry_notify_enabled": "0",
            "expiry_notify_hours": "24",
            "expiry_notify_interval": "10",
            "raid_enabled": "0",
            "auto_remove_enabled": "0",
            "auto_remove_timeout_mins": "10",
            "scan_interval_hours": "0.5",
            "log_channel_id": "Not Set",
            "pay_method_qr_enabled": "1",
            "pay_method_upi_enabled": "1",
            "pay_method_app_enabled": "1"
        }
        for k, v in defaults.items():
            self.set_setting(k, v, overwrite=False)
