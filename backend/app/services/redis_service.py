import json
import redis
from ..config import Config


class RedisService:
    """Redis 缓存服务封装"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        return self._client

    def set_json(self, key, value, ttl=3600):
        """存储 JSON 数据，默认1小时过期"""
        self.client.setex(key, ttl, json.dumps(value))

    def get_json(self, key):
        """读取 JSON 数据"""
        val = self.client.get(key)
        return json.loads(val) if val else None

    def set_sorted_set(self, key, mapping, ttl=86400):
        """存储有序集合 {member: score}，默认24小时过期"""
        if mapping:
            self.client.zadd(key, mapping)
            self.client.expire(key, ttl)

    def get_top_from_sorted_set(self, key, count=200):
        """按分数降序获取 Top-N"""
        return self.client.zrevrange(key, 0, count - 1, withscores=True)

    def set_value(self, key, value, ttl=None):
        """存储字符串值"""
        if ttl:
            self.client.setex(key, ttl, value)
        else:
            self.client.set(key, value)

    def get_value(self, key):
        """读取字符串值"""
        return self.client.get(key)

    def delete(self, key):
        """删除缓存键"""
        self.client.delete(key)


redis_service = RedisService()
