import logging
import threading
from db.connection import ConnectionManager, get_friendly_db_name
from db.users import UserQueries
from db.settings import SettingQueries
from db.plans import PlanQueries
from db.subscriptions import SubscriptionQueries
from db.channels import ChannelQueries

logger = logging.getLogger(__name__)

class Database(UserQueries, SettingQueries, PlanQueries, SubscriptionQueries, ChannelQueries):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_pools()
                cls._instance._init_db()
                cls._instance._seed_default_plans()
                cls._instance._seed_default_settings()
            return cls._instance

    def _init_db(self):
        pass

    def is_admin_check(self, user_id: int) -> bool:
        from config import ADMIN_ID
        if str(user_id) == str(ADMIN_ID):
            return True
        import json, time
        admins_str = self.get_setting("additional_admins", "[]")
        try:
            admins = json.loads(admins_str)
        except Exception:
            admins = []
        for admin in admins:
            if int(admin.get("user_id", 0)) == int(user_id):
                if admin.get("expiry_type") == "lifetime":
                    return True
                elif admin.get("expiry_type") == "month":
                    if time.time() < admin.get("expiry_timestamp", 0):
                        return True
        return False

db = Database()

