"""Per-client fixed-window rate limiting for one API process.

This is an abuse brake, not the system of record for quotas. Edge throttling (API
Gateway, WAF or an ALB-fronted limiter) and per-account quotas belong in later phases.
State is process-local: each Lambda or container instance enforces its own window.
"""
import threading
import time
from collections import OrderedDict

from starlette.responses import JSONResponse

MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    def __init__(self, limits: dict[str, int], default_limit: int, window_seconds: int = 60,
                 clock=time.monotonic):
        self.limits = limits
        self.default_limit = default_limit
        self.window = window_seconds
        self.clock = clock
        self._buckets: OrderedDict[tuple[str, str], tuple[int, float]] = OrderedDict()
        self._lock = threading.Lock()

    def limit_for(self, path: str) -> int:
        for prefix, limit in self.limits.items():
            if path.startswith(prefix):
                return limit
        return self.default_limit

    def check(self, client: str, path: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        limit = self.limit_for(path)
        bucket_key = (client, path.split('/')[2] if path.count('/') >= 2 else path)
        now = self.clock()
        with self._lock:
            count, window_start = self._buckets.get(bucket_key, (0, now))
            if now - window_start >= self.window:
                count, window_start = 0, now
            if count >= limit:
                retry = max(1, int(self.window - (now - window_start)) + 1)
                self._buckets[bucket_key] = (count, window_start)
                self._buckets.move_to_end(bucket_key)
                return False, 0, retry
            self._buckets[bucket_key] = (count + 1, window_start)
            self._buckets.move_to_end(bucket_key)
            while len(self._buckets) > MAX_TRACKED_CLIENTS:
                self._buckets.popitem(last=False)
            return True, limit - count - 1, 0


def client_key(scope, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = dict(scope.get('headers') or []).get(b'x-forwarded-for', b'').decode('latin-1')
        first = forwarded.split(',')[0].strip()
        if first:
            return first
    client = scope.get('client')
    return client[0] if client else 'unknown'


class RateLimit:
    """ASGI middleware applying RateLimiter to mutating /api requests."""

    def __init__(self, app, limiter: RateLimiter, trust_proxy_headers: bool = False):
        self.app = app
        self.limiter = limiter
        self.trust_proxy_headers = trust_proxy_headers

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/') \
                or scope['method'] not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return await self.app(scope, receive, send)
        allowed, _remaining, retry_after = self.limiter.check(
            client_key(scope, self.trust_proxy_headers), scope['path'])
        if not allowed:
            response = JSONResponse(
                {'detail': {'code': 'rate_limited',
                            'message': 'Too many requests from this client. Wait a moment and try again.'}},
                status_code=429, headers={'Retry-After': str(retry_after)})
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)
