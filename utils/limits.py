import redis
from datetime import date
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

DAILY_LIMIT = 5
EXTERNAL_LOOKUP_LIMIT = 10

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    r.ping()  # Проверяем соединение
    REDIS_AVAILABLE = True
except redis.ConnectionError:
    REDIS_AVAILABLE = False
    print("Redis unavailable. Limits disabled.")

def get_daily_count(user_id: int) -> int:
    if not REDIS_AVAILABLE:
        return 0  # Без Redis считаем, что лимит не превышен
    key = f"limit:{user_id}:{date.today()}"
    return int(r.get(key) or 0)


def has_subscription(user_id: int) -> bool:
    if not REDIS_AVAILABLE:
        return False
    key = f"subscription:{user_id}"
    return r.exists(key)

def grant_subscription(user_id: int) -> bool:
    if not REDIS_AVAILABLE:
        return False
    key = f"subscription:{user_id}"
    r.set(key, 1)
    return True

def is_limit_exceeded(user_id: int) -> bool:
    if not REDIS_AVAILABLE:
        return False  # Без Redis разрешаем
    if has_subscription(user_id):
        return False
    return get_daily_count(user_id) >= DAILY_LIMIT

def get_external_lookup_count(user_id: int) -> int:
    if not REDIS_AVAILABLE:
        return 0
    key = f"external:{user_id}:{date.today()}"
    return int(r.get(key) or 0)

def increment_external_lookup_count(user_id: int):
    if not REDIS_AVAILABLE:
        return
    key = f"external:{user_id}:{date.today()}"
    r.incr(key)
    r.expire(key, 86400)  # 24h

def is_external_lookup_limit_exceeded(user_id: int) -> bool:
    if not REDIS_AVAILABLE:
        return False
    if has_subscription(user_id):
        return False
    return get_external_lookup_count(user_id) >= EXTERNAL_LOOKUP_LIMIT

def increment_count(user_id: int) -> bool:
    if not REDIS_AVAILABLE:
        return True  # Позволяем продолжать
    if has_subscription(user_id):
        return True
    key = f"limit:{user_id}:{date.today()}"
    pipe = r.pipeline()
    current = pipe.get(key)
    pipe.incr(key)
    pipe.expire(key, 86400)  # 24h
    pipe.execute()
    return get_daily_count(user_id) <= 5