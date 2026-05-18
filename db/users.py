import logging
from datetime import datetime
from typing import List
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class UserQueries(ConnectionManager):
    def add_user(self, user_id: int, username: str, first_name: str) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted_new = False
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO users (user_id, username, first_name, joined_date)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id) DO NOTHING
                    """, (user_id, username or "", first_name or "", now_str))
                    if cursor.rowcount > 0:
                        inserted_new = True
            except Exception as e:
                logger.warning(f"add_user failed on DB {url[:30]}: {e}")
        return inserted_new

    def count_users(self) -> int:
        uids = set()
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT user_id FROM users")
                    for r in cursor.fetchall():
                        uids.add(r[0])
                    cursor.execute("SELECT user_id FROM subscriptions")
                    for r in cursor.fetchall():
                        uids.add(r[0])
            except Exception:
                pass
        return len(uids)

    def get_all_unique_user_ids(self) -> List[int]:
        uids = set()
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT user_id FROM users")
                    for r in cursor.fetchall():
                        uids.add(r[0])
                    cursor.execute("SELECT user_id FROM subscriptions")
                    for r in cursor.fetchall():
                        uids.add(r[0])
            except Exception:
                pass
        return list(uids)
