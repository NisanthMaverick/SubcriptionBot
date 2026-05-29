import logging
import threading
import json
import os
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2 import pool
from config import DATABASE_URL

logger = logging.getLogger(__name__)

def get_friendly_db_name(url: str, idx: int) -> str:
    lower_url = url.lower()
    if "prisma.io" in lower_url:
        return "⚡ Prisma Cloud Pooler"
    elif "neon.tech" in lower_url:
        return "🐘 Neon Serverless DB"
    elif "supabase" in lower_url:
        return "🟢 Supabase PostgreSQL"
    elif "railway" in lower_url:
        return "🚂 Railway Cloud DB"
    elif "render" in lower_url:
        return "☁️ Render Cloud DB"
    elif "aiven" in lower_url:
        return "🦀 Aiven Postgres DB"
    else:
        return f"🗄️ Cluster Shard #{idx + 1}"

class ConnectionManager:
    _pools: Dict[str, Any] = {}
    _db_status: Dict[str, str] = {}
    _db_urls: List[str] = []
    _active_db_idx: int = 0
    _lock = threading.Lock()

    def _init_pools(self):
        self._pools = {}
        self._db_status = {}
        self._db_urls = []
        self._active_db_idx = 0

        if os.path.exists("db_config.json"):
            try:
                with open("db_config.json", "r") as f:
                    data = json.load(f)
                    self._db_urls = data.get("db_urls", [])
            except Exception as e:
                logger.warning(f"Could not load db_config.json: {e}")

        if not self._db_urls:
            env_primary = os.getenv("DATABASE_URL", DATABASE_URL)
            if env_primary and env_primary not in self._db_urls:
                self._db_urls.append(env_primary)
            self._save_db_config()

        if not self._db_urls:
            raise ValueError("No database URLs configured!")

        for url in self._db_urls:
            self._connect_db_pool(url)

    def _save_db_config(self):
        try:
            with open("db_config.json", "w") as f:
                json.dump({"db_urls": self._db_urls}, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not save db_config.json: {e}")

    def _connect_db_pool(self, url):
        try:
            pool_inst = psycopg2.pool.SimpleConnectionPool(1, 10, url, sslmode='require')
            self._pools[url] = pool_inst
            self._db_status[url] = "Online"
            idx = self._db_urls.index(url)
            logger.info(f"Successfully connected DB #{idx + 1}: {url.split('@')[-1] if '@' in url else url[:30]}")
            self._init_db_schema_for_pool(pool_inst, idx)
        except Exception as e:
            logger.error(f"Failed to connect to DB {url[:30]}: {e}")
            self._db_status[url] = "Offline"

    def _init_db_schema_for_pool(self, pool_inst, idx):
        conn = pool_inst.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        joined_date TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS plans (
                        plan_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        amount TEXT NOT NULL,
                        durations TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        sub_id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        username TEXT,
                        profile_link TEXT,
                        plan_id INTEGER NOT NULL,
                        plan_name TEXT NOT NULL,
                        duration TEXT NOT NULL,
                        start_date TEXT,
                        expiry_date TEXT,
                        amount TEXT NOT NULL,
                        status TEXT NOT NULL,
                        screenshot_file_id TEXT,
                        notes TEXT,
                        notified_window TEXT DEFAULT ''
                    )
                """)
                cursor.execute("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS log_message_id TEXT")
                cursor.execute("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_notified_at TEXT")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS premium_channels (
                        channel_id BIGINT PRIMARY KEY,
                        title TEXT NOT NULL,
                        invite_link TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS channel_mappings (
                        channel_id BIGINT,
                        plan_id INTEGER,
                        PRIMARY KEY (channel_id, plan_id)
                    )
                """)
                if idx > 0:
                    cursor.execute("SELECT COUNT(*) FROM subscriptions")
                    cnt = cursor.fetchone()[0]
                    if cnt == 0:
                        start_val = idx * 1000000 + 1
                        cursor.execute(f"ALTER SEQUENCE subscriptions_sub_id_seq RESTART WITH {start_val}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Schema init failed for DB #{idx + 1}: {e}")
        finally:
            pool_inst.putconn(conn)

    def add_database(self, new_url: str) -> bool:
        with self._lock:
            if new_url in self._db_urls:
                return False
            try:
                conn = psycopg2.connect(new_url, sslmode='require')
                conn.close()
            except Exception as e:
                logger.error(f"Validation failed for new DB URL: {e}")
                raise e
            self._db_urls.append(new_url)
            self._connect_db_pool(new_url)
            self._save_db_config()
            return True

    def get_all_db_urls(self) -> List[str]:
        return self._db_urls

    def get_db_status_map(self) -> Dict[str, str]:
        return self._db_status

    @contextmanager
    def _get_cursor(self, specific_url=None):
        url = specific_url
        if not url:
            for _ in range(len(self._db_urls)):
                cand = self._db_urls[self._active_db_idx]
                if self._db_status.get(cand) == "Online" and cand in self._pools:
                    url = cand
                    break
                self._active_db_idx = (self._active_db_idx + 1) % len(self._db_urls)
            if not url:
                url = self._db_urls[0]

        pool_inst = self._pools.get(url)
        if not pool_inst:
            self._connect_db_pool(url)
            pool_inst = self._pools.get(url)
            if not pool_inst:
                raise Exception(f"Database pool for {url[:30]} unavailable.")

        try:
            conn = pool_inst.getconn()
            if conn.closed != 0:
                pool_inst.putconn(conn, close=True)
                conn = pool_inst.getconn()
        except Exception as e:
            logger.warning(f"Connection pool error for {url[:30]}: {e}")
            self._connect_db_pool(url)
            pool_inst = self._pools[url]
            conn = pool_inst.getconn()

        try:
            with conn.cursor() as cursor:
                yield cursor, conn
            conn.commit()
        except Exception as e:
            if conn.closed == 0:
                conn.rollback()
            err_str = str(e).lower()
            if getattr(e, 'pgcode', '') == '53100' or 'disk full' in err_str or 'quota' in err_str or 'space' in err_str:
                logger.error(f"🚨 DATABASE {url[:30]} IS FULL! Marking as Full and switching active pool.")
                self._db_status[url] = "Full"
                self._active_db_idx = (self._active_db_idx + 1) % len(self._db_urls)
            raise e
        finally:
            if conn.closed == 0:
                pool_inst.putconn(conn)
            else:
                pool_inst.putconn(conn, close=True)

    def _run_read_query(self, query_str: str, params: tuple = ()) -> List[tuple]:
        try:
            with self._get_cursor() as (cursor, conn):
                cursor.execute(query_str, params)
                return cursor.fetchall()
        except Exception as e:
            logger.warning(f"Read query failed on active DB: {e}. Falling back to search.")
            for url in self._db_urls:
                if self._db_status.get(url) != "Online":
                    continue
                try:
                    with self._get_cursor(specific_url=url) as (cursor, conn):
                        cursor.execute(query_str, params)
                        res = cursor.fetchall()
                        self._active_db_idx = self._db_urls.index(url)
                        return res
                except Exception:
                    pass
            raise e

    def _run_read_query_one(self, query_str: str, params: tuple = ()) -> Optional[tuple]:
        try:
            with self._get_cursor() as (cursor, conn):
                cursor.execute(query_str, params)
                return cursor.fetchone()
        except Exception as e:
            logger.warning(f"Read one query failed on active DB: {e}. Falling back to search.")
            for url in self._db_urls:
                if self._db_status.get(url) != "Online":
                    continue
                try:
                    with self._get_cursor(specific_url=url) as (cursor, conn):
                        cursor.execute(query_str, params)
                        res = cursor.fetchone()
                        self._active_db_idx = self._db_urls.index(url)
                        return res
                except Exception:
                    pass
            raise e

    def get_database_analytics(self) -> List[Dict[str, Any]]:
        analytics = []
        for idx, url in enumerate(self._db_urls):
            fname = get_friendly_db_name(url, idx)
            status = self._db_status.get(url, "Unknown")
            db_size_mb = 0.0
            total_users = 0
            total_subs = 0
            active_subs = 0
            usage_percent = 0.0

            if status == "Online":
                try:
                    with self._get_cursor(specific_url=url) as (cursor, conn):
                        cursor.execute("SELECT pg_database_size(current_database())")
                        size_bytes = cursor.fetchone()[0]
                        db_size_mb = round(size_bytes / (1024 * 1024), 2)
                        usage_percent = min(round((db_size_mb / 500.0) * 100, 2), 100.0)

                        cursor.execute("SELECT COUNT(*) FROM users")
                        total_users = cursor.fetchone()[0]

                        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM subscriptions")
                        total_subs = cursor.fetchone()[0]

                        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status IN ('Paid', 'Granted') AND expiry_date IS NOT NULL")
                        active_subs = cursor.fetchone()[0]
                except Exception as e:
                    logger.warning(f"Analytics query failed for DB #{idx + 1}: {e}")
                    status = "Error"

            analytics.append({
                "db_index": idx + 1,
                "name": fname,
                "status": status,
                "size_mb": db_size_mb,
                "usage_percent": usage_percent,
                "total_users": total_users,
                "total_subs": total_subs,
                "active_subs": active_subs
            })
        return analytics

    def ping_databases(self) -> None:
        """Ping all online databases to keep serverless connections alive."""
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("SELECT 1")
            except Exception:
                pass
