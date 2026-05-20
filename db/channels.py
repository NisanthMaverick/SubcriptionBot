import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class ChannelQueries(ConnectionManager):
    def add_premium_channel(self, channel_id: int, title: str, invite_link: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO premium_channels (channel_id, title, invite_link)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (channel_id) DO UPDATE SET 
                            title = EXCLUDED.title, invite_link = EXCLUDED.invite_link
                    """, (channel_id, title, invite_link))
            except Exception as e:
                logger.warning(f"add_premium_channel failed on DB {url[:30]}: {e}")

    def get_premium_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            row = self._run_read_query_one("SELECT channel_id, title, invite_link FROM premium_channels WHERE channel_id = %s", (channel_id,))
            if row:
                return {"channel_id": row[0], "title": row[1], "invite_link": row[2]}
        except Exception:
            pass
        return None

    def get_all_premium_channels(self) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("SELECT channel_id, title, invite_link FROM premium_channels ORDER BY title ASC")
            return [{"channel_id": r[0], "title": r[1], "invite_link": r[2]} for r in rows]
        except Exception:
            pass
        return []

    def delete_premium_channel(self, channel_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM premium_channels WHERE channel_id = %s", (channel_id,))
                    cursor.execute("DELETE FROM channel_mappings WHERE channel_id = %s", (channel_id,))
            except Exception:
                pass

    def clear_premium_channels(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM premium_channels")
            except Exception:
                pass

    def clear_channel_mappings(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM channel_mappings")
            except Exception:
                pass

    def add_channel_mapping(self, channel_id: int, plan_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO channel_mappings (channel_id, plan_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (channel_id, plan_id))
            except Exception as e:
                logger.warning(f"add_channel_mapping failed on DB {url[:30]}: {e}")

    def remove_channel_mapping(self, channel_id: int, plan_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM channel_mappings WHERE channel_id = %s AND plan_id = %s", (channel_id, plan_id))
            except Exception:
                pass

    def delete_channel_mappings(self, channel_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM channel_mappings WHERE channel_id = %s", (channel_id,))
            except Exception:
                pass

    def get_channels_for_plan(self, plan_id: int) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("""
                SELECT c.channel_id, c.title, c.invite_link 
                FROM premium_channels c
                JOIN channel_mappings m ON c.channel_id = m.channel_id
                WHERE m.plan_id = %s
            """, (plan_id,))
            return [{"channel_id": r[0], "title": r[1], "invite_link": r[2]} for r in rows]
        except Exception:
            pass
        return []

    def check_user_access_to_channel(self, user_id: int, channel_id: int) -> bool:
        # First check if the channel is mapped to any plan at all.
        try:
            row = self._run_read_query_one("SELECT COUNT(*) FROM channel_mappings WHERE channel_id = %s", (channel_id,))
            is_mapped = row[0] > 0 if row else False
        except Exception:
            is_mapped = False

        if not is_mapped:
            return True

        # Now fetch user's active subscriptions
        try:
            rows = self._run_read_query("""
                SELECT plan_id, expiry_date, status 
                FROM subscriptions 
                WHERE user_id = %s AND status IN ('Paid', 'Granted')
            """, (user_id,))
            
            now = datetime.now()
            for plan_id, expiry_str, status in rows:
                if not expiry_str:
                    continue
                try:
                    expiry_dt = datetime.strptime(expiry_str, "%d/%m/%Y")
                    expiry_dt = expiry_dt.replace(hour=23, minute=59, second=59)
                except Exception:
                    continue
                
                if expiry_dt >= now:
                    # User has active sub for this plan_id. Check if channel is mapped to it.
                    mapping_row = self._run_read_query_one("""
                        SELECT COUNT(*) FROM channel_mappings 
                        WHERE channel_id = %s AND plan_id = %s
                    """, (channel_id, plan_id))
                    if mapping_row and mapping_row[0] > 0:
                        return True
        except Exception:
            pass
        return False

    def get_all_channel_mappings(self) -> list:
        try:
            rows = self._run_read_query("SELECT channel_id, plan_id FROM channel_mappings")
            return [{"channel_id": r[0], "plan_id": r[1]} for r in rows]
        except Exception:
            pass
        return []

