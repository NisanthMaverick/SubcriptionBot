import logging
from typing import List, Dict, Any, Optional
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class SubscriptionQueries(ConnectionManager):
    def add_subscription(self, user_id: int, username: str, profile_link: str, plan_id: int, 
                         plan_name: str, duration: str, amount: str, screenshot_file_id: str) -> int:
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
                    return sub_id
            except Exception as e:
                err_str = str(e).lower()
                if getattr(e, 'pgcode', '') == '53100' or 'disk full' in err_str or 'quota' in err_str or 'space' in err_str:
                    logger.error(f"🚨 DB {url[:30]} IS FULL during write! Failing over to next DB.")
                    self._db_status[url] = "Full"
                self._active_db_idx = (self._active_db_idx + 1) % len(self._db_urls)
        raise Exception("All configured databases failed or are full during add_subscription.")

    def get_subscription(self, sub_id: int) -> Optional[Dict[str, Any]]:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window
                        FROM subscriptions WHERE sub_id = %s
                    """, (sub_id,))
                    row = cursor.fetchone()
                    if row:
                        return {
                            "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                            "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                            "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                            "notes": row[12] or "", "notified_window": row[13] or ""
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
                    if cursor.rowcount > 0:
                        break
            except Exception:
                pass

    def delete_subscription(self, sub_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM subscriptions WHERE sub_id = %s", (sub_id,))
                    if cursor.rowcount > 0:
                        break
            except Exception:
                pass

    def update_notified_window(self, sub_id: int, window: str) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("UPDATE subscriptions SET notified_window = %s WHERE sub_id = %s", (window, sub_id))
                    if cursor.rowcount > 0:
                        break
            except Exception:
                pass

    def get_all_subscriptions(self, offset: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        subs = []
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window
                        FROM subscriptions ORDER BY sub_id DESC LIMIT %s
                    """, (limit + offset,))
                    rows = cursor.fetchall()
                    for row in rows:
                        subs.append({
                            "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                            "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                            "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                            "notes": row[12] or "", "notified_window": row[13] or ""
                        })
            except Exception:
                pass
        subs.sort(key=lambda x: x["sub_id"], reverse=True)
        return subs[offset:offset+limit]

    def get_subscriptions_by_plan(self, plan_id: int) -> List[Dict[str, Any]]:
        subs = []
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window
                        FROM subscriptions WHERE plan_id = %s ORDER BY sub_id DESC
                    """, (plan_id,))
                    rows = cursor.fetchall()
                    for row in rows:
                        subs.append({
                            "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                            "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                            "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                            "notes": row[12] or "", "notified_window": row[13] or ""
                        })
            except Exception:
                pass
        subs.sort(key=lambda x: x["sub_id"], reverse=True)
        return subs

    def count_subscriptions(self) -> int:
        total = 0
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT COUNT(*) FROM subscriptions")
                    total += cursor.fetchone()[0]
            except Exception:
                pass
        return total

    def get_active_paid_subscriptions(self) -> List[Dict[str, Any]]:
        subs = []
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("""
                        SELECT sub_id, user_id, username, profile_link, plan_id, plan_name, duration, start_date, expiry_date, amount, status, screenshot_file_id, notes, notified_window
                        FROM subscriptions WHERE status IN ('Paid', 'Granted') AND expiry_date IS NOT NULL
                    """)
                    rows = cursor.fetchall()
                    for row in rows:
                        subs.append({
                            "sub_id": row[0], "user_id": row[1], "username": row[2], "profile_link": row[3],
                            "plan_id": row[4], "plan_name": row[5], "duration": row[6], "start_date": row[7],
                            "expiry_date": row[8], "amount": row[9], "status": row[10], "screenshot_file_id": row[11],
                            "notes": row[12] or "", "notified_window": row[13] or ""
                        })
            except Exception:
                pass
        return subs

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
