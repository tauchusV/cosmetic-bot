
import redis
from datetime import date
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

def get_daily_count(user_id: int) -> int:
    key = f"limit:{user_id}:{date.today()}"
    return int(r.get(key) or 0)

def increment_count(user_id: int) -> bool:
    key = f"limit:{user_id}:{date.today()}"
    pipe = r.pipeline()
    current = pipe.get(key)
    pipe.incr(key)
    pipe.expire(key, 86400)  # 24h
    pipe.execute()
    return get_daily_count(user_id) <= 5

def is_limit_exceeded(user_id: int) -> bool:
    return get_daily_count(user_id) >= 5