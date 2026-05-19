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
            return cls._instance

    def _init_db(self):
        pass

db = Database()
