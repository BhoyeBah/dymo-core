import json
from typing import Optional, Any
import redis
import structlog
from dymo_saas_core.core.config import settings

logger = structlog.get_logger(__name__)

class CacheService:
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        
    @property
    def client(self) -> Optional[redis.Redis]:
        if self._client is None and settings.REDIS_URL:
            try:
                self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                # Test connection
                self._client.ping()
                logger.info("Connected to Redis successfully", url=settings.REDIS_URL)
            except Exception as e:
                logger.warning("Failed to connect to Redis, caching will be disabled", error=str(e))
                self._client = None
        return self._client

    def get(self, key: str) -> Optional[Any]:
        r = self.client
        if not r:
            return None
        try:
            val = r.get(key)
            if val is not None:
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return val
            return None
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = 3600) -> bool:
        r = self.client
        if not r:
            return False
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            if ttl:
                r.set(key, serialized, ex=ttl)
            else:
                r.set(key, serialized)
            return True
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False

    def delete(self, key: str) -> bool:
        r = self.client
        if not r:
            return False
        try:
            r.delete(key)
            return True
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False

    def flush(self) -> bool:
        r = self.client
        if not r:
            return False
        try:
            r.flushdb()
            return True
        except Exception as e:
            logger.error("Redis flushdb error", error=str(e))
            return False

# Global Cache Service Instance
cache_service = CacheService()
