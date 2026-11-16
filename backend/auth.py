import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Cookie, HTTPException, Request, Response

from config import OPERATOR_HMAC_SECRET

COOKIE = "__Host-operator_session"
TTL = 8 * 60 * 60
KEY = bytes.fromhex(OPERATOR_HMAC_SECRET)
WINDOW, LIMIT = 60, 10
_failures: dict[str, deque] = defaultdict(deque)


def _sign(body: str) -> str:
    return hmac.new(KEY, body.encode(), hashlib.sha256).hexdigest()


def make_session() -> str:
    body = f"v1.{int(time.time()) + TTL}.{secrets.token_urlsafe(18)}"
    return f"{body}.{_sign(body)}"


def valid_session(value: Optional[str]) -> bool:
    if not value:
        return False
    parts = value.split(".")
    if len(parts) != 4 or parts[0] != "v1" or not parts[1].isdigit():
        return False
    if int(parts[1]) <= int(time.time()):
        return False
    return hmac.compare_digest(_sign(".".join(parts[:3])), parts[3])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_rate(request: Request) -> None:
    q = _failures[_client_ip(request)]
    t = time.time()
    while q and q[0] <= t - WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, "Too many attempts. Try again in a minute.")


def verify_secret(request: Request, submitted: str) -> bool:
    ok = hmac.compare_digest(hashlib.sha256(submitted.encode()).digest(), hashlib.sha256(OPERATOR_HMAC_SECRET.encode()).digest())
    ip = _client_ip(request)
    if ok:
        _failures[ip].clear()
    else:
        _failures[ip].append(time.time())
    return ok


def set_session(response: Response) -> None:
    response.set_cookie(COOKIE, make_session(), max_age=TTL, path="/", secure=True, httponly=True, samesite="strict")


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")


def require_operator(session: Optional[str] = Cookie(default=None, alias=COOKIE)) -> None:
    if not valid_session(session):
        raise HTTPException(401, "Unauthorized")
