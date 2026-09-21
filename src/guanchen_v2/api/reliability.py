"""Bounded single-worker admission, Redis rate limits and short-lived replay keys.

Redis is never conversation memory. Ambiguous failures retain their reservation:
clients must read PostgreSQL session state instead of blindly repeating effects.
"""

import asyncio
import hashlib
import json
import re

from redis.exceptions import RedisError
from starlette.responses import JSONResponse

from guanchen_v2.api.contracts import ChatResponse
from guanchen_v2.api.errors import APIApplicationError

RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return n
"""


class Reliability:
    def __init__(self, redis, *, rate_limit=30, max_concurrent=2, timeout=180):
        self.redis = redis
        self.rate_limit = rate_limit
        self.slots = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout
        self.ttl = max(900, int(timeout) + 120)

    async def admit(self, identity):
        key = hashlib.sha256(identity.encode()).hexdigest()
        try:
            count = await self.redis.eval(RATE_SCRIPT, 1, f"gc:rate:{key}")
        except RedisError as exc:
            raise APIApplicationError("DEPENDENCY_UNAVAILABLE", "服务暂不可用，请稍后重试。", None, 503) from exc
        if count > self.rate_limit:
            raise APIApplicationError("RATE_LIMITED", "请求过于频繁，请稍后重试。", None, 429)

    async def execute(self, session_id, key, payload, operation):
        if key and not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
            raise APIApplicationError("INVALID_IDEMPOTENCY_KEY", "请求标识格式错误。", None, 422)
        # Reject overload rather than create an unbounded queue of model requests.
        if self.slots.locked():
            raise APIApplicationError("SERVER_BUSY", "服务繁忙，请稍后重试。", None, 429)
        async with self.slots:
            cache_key = None
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            try:
                if key:
                    suffix = hashlib.sha256(f"{session_id}:{key}".encode()).hexdigest()
                    cache_key = f"gc:request:{suffix}"
                    reserved = await self.redis.set(cache_key, json.dumps({"fingerprint": fingerprint}), nx=True, ex=self.ttl)
                    if not reserved:
                        cached = await self.redis.get(cache_key)
                        record = json.loads(cached) if cached else {}
                        if record.get("fingerprint") != fingerprint:
                            raise APIApplicationError("IDEMPOTENCY_CONFLICT", "请求标识已用于其他内容。", None, 409)
                        if "response" in record:
                            return ChatResponse.model_validate(record["response"])
                        raise APIApplicationError("REQUEST_PENDING", "请求执行中或结果待确认，请读取会话状态。", None, 409)
                async with asyncio.timeout(self.timeout):
                    result = await operation()
                if cache_key:
                    await self.redis.set(
                        cache_key,
                        json.dumps({"fingerprint": fingerprint, "response": result.model_dump(mode="json", exclude={"session_token"})}),
                        ex=self.ttl,
                    )
                return result
            except RedisError as exc:
                raise APIApplicationError("DEPENDENCY_UNAVAILABLE", "服务暂不可用，请读取会话状态后再试。", None, 503) from exc
            except TimeoutError as exc:
                raise APIApplicationError("REQUEST_TIMEOUT", "请求超时，请读取会话状态。", None, 504) from exc


class AdmissionMiddleware:
    """Pure ASGI middleware preserves streaming and disconnect cancellation."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in {"POST", "PATCH"} and scope["path"].startswith("/api/"):
            state = scope["app"].state
            reliability = getattr(state, "reliability", None)
            if reliability is not None:
                host = (scope.get("client") or ("unknown",))[0]
                if getattr(state, "trust_proxy", False):
                    host = dict(scope["headers"]).get(b"x-real-ip", host.encode()).decode()
                try:
                    await reliability.admit(host)
                except APIApplicationError as exc:
                    response = JSONResponse({"code": exc.code, "message": exc.message, "trace_id": None}, status_code=exc.status_code)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


async def execute_request(request, payload, operation):
    reliability = getattr(request.app.state, "reliability", None)
    if reliability is None:
        return await operation()
    return await reliability.execute(
        payload.session_id, request.headers.get("Idempotency-Key"),
        {"path": request.url.path, "body": payload.model_dump(mode="json")}, operation,
    )
