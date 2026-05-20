import logging
from typing import List, Dict, Any, Optional
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class SubscriptionQueries(ConnectionManager):
    def add_subscription(self, user_id: int, username: str, profile_link: str, plan_id: int, 
                         plan_name: str, duration: str, amount: str, screenshot_file_id: str) -> int:
        sub_id = None
        primary_url = None
        for _ in range(len(self._db_urls)):
            url = self._db_urls[self._active_db_idx]
            if self._db_status.get(url) != "Online":
                self._active_db_idx = (self._active_db_idx + 1) % len(self._db_urls)
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO subscriptions (user_id, username, profile_link, plan_id, plan_name, duration, amount, status, screenshot_file_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING sub_id
                    """, (user_id, username, profile_link, plan_id, plan_name, duration, amount, "Pending", screenshot_file_id))
                    sub_id = cursor.fetchone()[0]
                    primary_url = url
                    break
            except Exception as e:
                err_str = str(e).lower()
                if getattr(e, 'pgcode', '') == '53100' or 'disk full' in err_str or 'quota' in err_str or 'space' in err_str:
                    logger.error(f"🚨 DB {url[:30]} IS FULL during write! Failing over to next DB.")
                    self._db_status[url] = "Full"
                self._active_db_idx = (self._active_db_idx + 1) % len(self._db_urls)

        if sub_id is None:
            raise Exception("All configured databases failed or are full during add_subscription.")

        # Sync/replicate this record with the same sub_id to all other online databases
        for url in self._db_urls:
            if url == primary_url:
                continue
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        INSERT INTO subscriptions (sub_id, user_id, username, profile_link, plan_id, plan_name, duration, amount, status, screenshot_file_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sub_id) DO NOTHING
                    """, (sub_id, user_id, username, profile_link, plan_id, plan_name, duration, amount, "Pending", screenshot_file_id))
            except Exception as e:
                logger.warning(f"Failed to sync subscription {sub_id} to DB {url[:30]}: {e}")

        return sub_id

    def get_subscription(self, sub_id: int) -> Optional[Dict[str, Any]]:
        try:
            row = self._run_read_query_one("""
                SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window, log_message_id, last_notified_at
                FROM subscriptions WHERE sub_id = %s
            """, (sub_id,))
            if row:
                return {
                    "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                    "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                    "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                    "notes": row[12] or "", "notified_window": row[13] or "",
                    "log_message_id": row[14] or "", "last_notified_at": row[15] or ""
                }
        except Exception:
            pass
        return None

    def update_subscription_status(self, sub_id: int, status: str, start_date: str = None, expiry_date: str = None, notes: str = None) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        UPDATE subscriptions
                        SET status = %s, start_date = COALESCE(%s, start_date), expiry_date = COALESCE(%s, expiry_date), notes = COALESCE(%s, notes)
                        WHERE sub_id = %s
                    """, (status, start_date, expiry_date, notes, sub_id))
            except Exception as e:
                logger.warning(f"update_subscription_status failed on DB {url[:30]}: {e}")

    def delete_subscription(self, sub_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM subscriptions WHERE sub_id = %s", (sub_id,))
            except Exception as e:
                logger.warning(f"delete_subscription failed on DB {url[:30]}: {e}")

    def delete_other_user_subscriptions(self, user_id: int, keep_sub_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute(
                        "DELETE FROM subscriptions WHERE user_id = %s AND sub_id != %s",
                        (user_id, keep_sub_id)
                    )
            except Exception as e:
                logger.warning(f"delete_other_user_subscriptions failed on DB {url[:30]}: {e}")

    def update_notified_window(self, sub_id: int, window: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("UPDATE subscriptions SET notified_window = %s WHERE sub_id = %s", (window, sub_id))
            except Exception as e:
                logger.warning(f"update_notified_window failed on DB {url[:30]}: {e}")

    def renew_subscription_record(self, sub_id: int, expiry_date: str, duration: str, amount: str, screenshot_file_id: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        UPDATE subscriptions
                        SET expiry_date = %s, duration = %s, amount = %s, screenshot_file_id = %s, status = 'Paid'
                        WHERE sub_id = %s
                    """, (expiry_date, duration, amount, screenshot_file_id, sub_id))
            except Exception as e:
                logger.warning(f"renew_subscription_record failed on DB {url[:30]}: {e}")

    def update_subscription_log_message(self, sub_id: int, log_message_id: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("UPDATE subscriptions SET log_message_id = %s WHERE sub_id = %s", (log_message_id, sub_id))
            except Exception as e:
                logger.warning(f"update_subscription_log_message failed on DB {url[:30]}: {e}")

    def update_last_notified_at(self, sub_id: int, timestamp: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("UPDATE subscriptions SET last_notified_at = %s WHERE sub_id = %s", (timestamp, sub_id))
            except Exception as e:
                logger.warning(f"update_last_notified_at failed on DB {url[:30]}: {e}")



    def get_all_subscriptions(self, offset: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("""
                SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window, log_message_id, last_notified_at
                FROM subscriptions ORDER BY sub_id DESC LIMIT %s OFFSET %s
            """, (limit, offset))
            subs = []
            for row in rows:
                subs.append({
                    "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                    "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                    "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                    "notes": row[12] or "", "notified_window": row[13] or "",
                    "log_message_id": row[14] or "", "last_notified_at": row[15] or ""
                })
            return subs
        except Exception:
            pass
        return []

    def get_subscriptions_by_plan(self, plan_id: int) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("""
                SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window, log_message_id, last_notified_at
                FROM subscriptions WHERE plan_id = %s AND status IN ('Paid', 'Granted') ORDER BY sub_id DESC
            """, (plan_id,))
            subs = []
            for row in rows:
                subs.append({
                    "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                    "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                    "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                    "notes": row[12] or "", "notified_window": row[13] or "",
                    "log_message_id": row[14] or "", "last_notified_at": row[15] or ""
                })
            return subs
        except Exception:
            pass
        return []

    def count_subscriptions(self) -> int:
        try:
            row = self._run_read_query_one("SELECT COUNT(*) FROM subscriptions")
            return row[0] if row else 0
        except Exception:
            pass
        return 0

    def get_active_paid_subscriptions(self) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("""
                SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window, log_message_id, last_notified_at
                FROM subscriptions WHERE status IN ('Paid', 'Granted') AND expiry_date IS NOT NULL
            """)
            subs = []
            for row in rows:
                subs.append({
                    "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                    "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                    "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                    "notes": row[12] or "", "notified_window": row[13] or "",
                    "log_message_id": row[14] or "", "last_notified_at": row[15] or ""
                })
            return subs
        except Exception:
            pass
        return []

    def clear_subscriptions(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM subscriptions")
            except Exception:
                pass

    def clear_all_tables(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM users")
                    cursor.execute("DELETE FROM subscriptions")
                    cursor.execute("DELETE FROM plans")
                    cursor.execute("DELETE FROM settings")
            except Exception:
                pass
