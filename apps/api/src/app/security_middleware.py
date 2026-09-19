import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger("argus.audit")
RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return count
"""


async def security_boundary(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    settings = get_settings()
    request_id = uuid4().hex
    request.state.request_id = request_id
    response: Response
    limited = (
        settings.app_env == "production"
        and request.url.path
        in {f"{settings.api_v1_prefix}/auth/token", f"{settings.api_v1_prefix}/auth/refresh"}
        and request.method == "POST"
    )
    if limited:
        # Use the server-resolved client address, never a caller-supplied forwarding header.
        address = request.client.host if request.client else "unknown"
        key = "argus:auth-limit:" + hashlib.sha256(address.encode()).hexdigest()
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            count = await client.eval(RATE_SCRIPT, 1, key)
            if int(count) > settings.auth_rate_limit_per_minute:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many attempts"},
                    headers={"Retry-After": "60"},
                )
            else:
                response = await call_next(request)
        except RedisError:
            response = JSONResponse(
                status_code=503,
                content={"detail": "Authentication temporarily unavailable"},
                headers={"Retry-After": "5"},
            )
        finally:
            await client.aclose()
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    # No request bodies, credentials, tokens, query strings, or email addresses.
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "actor_id": getattr(request.state, "actor_id", None),
            }
        )
    )
    return response
