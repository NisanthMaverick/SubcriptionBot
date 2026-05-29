import logging
import json
from typing import List, Dict, Any, Optional
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)

class PlanQueries(ConnectionManager):
    def count_plans(self) -> int:
        try:
            row = self._run_read_query_one("SELECT COUNT(*) FROM plans")
            return row[0] if row else 0
        except Exception:
            return 0

    def _seed_default_plans(self):
        try:
            row = self._run_read_query_one("SELECT COUNT(*) FROM plans")
            count = row[0] if row else 0
        except Exception:
            count = 0

        if count == 0:
            logger.info("Seeding default subscription plans across cluster...")
            p1_dur = [{"duration": "1 Month", "price": "₹20"}, {"duration": "2 Months", "price": "₹35"}]
            self.save_plan(1, "1️⃣ Series Channel - Premium 📺", "Access all exclusive series without interruptions.", "₹20 - ₹35", p1_dur, overwrite=False)

            p2_dur = [{"duration": "1 Month", "price": "₹40"}, {"duration": "2 Months", "price": "₹70"}]
            self.save_plan(2, "2️⃣ Movie & DB Channel - Premium 🍿", "Unlimited high-speed downloads for all premium movies.", "₹40 - ₹70", p2_dur, overwrite=False)

            p3_dur = [{"duration": "1 Month", "price": "₹50"}, {"duration": "2 Months", "price": "₹90"}]
            self.save_plan(3, "3️⃣ All Channels Premium 👑", "🔥 Full Access Pass 🔥 Get VIP access across all channels.", "₹50 - ₹90", p3_dur, overwrite=False)

    def save_plan(self, plan_id: int, name: str, description: str, amount: str, durations: List[Dict[str, str]], overwrite: bool = True) -> None:
        durations_str = json.dumps(durations)
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    if overwrite:
                        cursor.execute("""
                            INSERT INTO plans (plan_id, name, description, amount, durations)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (plan_id) DO UPDATE SET 
                                name = EXCLUDED.name, description = EXCLUDED.description, 
                                amount = EXCLUDED.amount, durations = EXCLUDED.durations
                        """, (plan_id, name, description, amount, durations_str))
                    else:
                        cursor.execute("""
                            INSERT INTO plans (plan_id, name, description, amount, durations)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (plan_id) DO NOTHING
                        """, (plan_id, name, description, amount, durations_str))
            except Exception as e:
                logger.warning(f"save_plan failed on DB {url[:30]}: {e}")

    def get_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        try:
            row = self._run_read_query_one("SELECT plan_id, name, description, amount, durations FROM plans WHERE plan_id = %s", (plan_id,))
            if row:
                try:
                    durations = json.loads(row[4])
                except Exception:
                    durations = []
                return {
                    "plan_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "amount": row[3],
                    "durations": durations
                }
        except Exception:
            pass
        return None

    def get_all_plans(self) -> List[Dict[str, Any]]:
        try:
            rows = self._run_read_query("SELECT plan_id, name, description, amount, durations FROM plans ORDER BY plan_id ASC")
            plans = []
            for row in rows:
                try:
                    durations = json.loads(row[4])
                except Exception:
                    durations = []
                plans.append({
                    "plan_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "amount": row[3],
                    "durations": durations
                })
            return plans
        except Exception:
            pass
        return []

    def delete_plan(self, plan_id: int) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM plans WHERE plan_id = %s", (plan_id,))
            except Exception:
                pass

    def clear_plans(self) -> None:
        for url in self._db_urls:
            if self._db_status.get(url) != "Online":
                continue
            try:
                with self._get_cursor(specific_url=url) as (cursor, conn):
                    cursor.execute("DELETE FROM plans")
            except Exception:
                pass
