"""Sign-in for the private pages (garden, seeds, tasks, species, admin). Human-owned.

One account, the existing ADMIN_USER / ADMIN_PASSWORD. A successful POST /login sets a signed
cookie (HMAC-SHA256 with SESSION_SECRET) that lasts SESSION_DAYS. Pages depend on
:func:`require_user`: HTML pages redirect to /login?next=…, /api/ paths answer 401.
"""

import base64
import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings

COOKIE = "garden_session"
_FAILS: dict[str, deque[float]] = defaultdict(deque)
MAX_FAILS = 10
FAIL_WINDOW = 600.0

router = APIRouter()


class LoginRequired(Exception):
    """Raised by require_user; main.py turns it into a redirect (HTML) or 401 (API)."""

    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


def _sig(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_cookie(user: str, settings: Settings | None = None, now: float | None = None) -> str:
    s = settings or Settings()
    exp = int((now or time.time()) + s.SESSION_DAYS * 86400)
    payload = base64.urlsafe_b64encode(f"{user}|{exp}".encode()).decode()
    return f"{payload}.{_sig(payload, s.SESSION_SECRET)}"


def read_cookie(
    value: str | None, settings: Settings | None = None, now: float | None = None
) -> str | None:
    """Return the user name in a valid, unexpired cookie, else None."""
    if not value or "." not in value:
        return None
    s = settings or Settings()
    payload, sig = value.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sig(payload, s.SESSION_SECRET)):
        return None
    try:
        user, exp = base64.urlsafe_b64decode(payload.encode()).decode().rsplit("|", 1)
        if int(exp) < (now or time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return user if user == s.ADMIN_USER else None


def _basic_user(header: str | None) -> str | None:
    """Scripts may send HTTP Basic (ADMIN_USER / ADMIN_PASSWORD) instead of the cookie."""
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except (ValueError, UnicodeDecodeError):
        return None
    s = Settings()
    ok = hmac.compare_digest(user.encode(), s.ADMIN_USER.encode())
    ok = hmac.compare_digest(password.encode(), s.ADMIN_PASSWORD.encode()) and ok
    return s.ADMIN_USER if ok else None


def current_user(request: Request) -> str | None:
    return read_cookie(request.cookies.get(COOKIE)) or _basic_user(
        request.headers.get("authorization")
    )


def require_user(request: Request) -> str:
    """FastAPI dependency for private routes."""
    user = current_user(request)
    if user is None:
        nxt = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(nxt)
    return user


RequireUser = Depends(require_user)


def safe_next(nxt: str | None) -> str:
    """Only same-site paths: '/x' yes, '//evil.com' or 'https://…' no."""
    if not nxt or not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
        return "/"
    return nxt


def _client(request: Request) -> str:
    return request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "?"
    )


def _too_many(ip: str, now: float) -> bool:
    q = _FAILS[ip]
    while q and now - q[0] > FAIL_WINDOW:
        q.popleft()
    return len(q) >= MAX_FAILS


@router.get("/login")
async def login_page(request: Request, next: str = "/") -> HTMLResponse:  # noqa: A002
    from app.templating import render

    return render(request, "login.html", next=safe_next(next), error=None)


@router.post("/login", response_model=None)
async def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),  # noqa: A002
) -> Response:
    from app.templating import render

    s = Settings()
    ip, now = _client(request), time.time()
    if _too_many(ip, now):
        return render(
            request,
            "login.html",
            429,
            next=safe_next(next),
            error="Too many attempts. Try again in a few minutes.",
        )
    ok_user = hmac.compare_digest(username.encode(), s.ADMIN_USER.encode())
    ok_pass = hmac.compare_digest(password.encode(), s.ADMIN_PASSWORD.encode())
    if not (ok_user and ok_pass):
        _FAILS[ip].append(now)
        return render(
            request, "login.html", 401, next=safe_next(next), error="Wrong name or password."
        )
    _FAILS.pop(ip, None)
    resp = RedirectResponse(safe_next(next), status_code=303)
    resp.set_cookie(
        COOKIE,
        make_cookie(s.ADMIN_USER, s),
        max_age=s.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=s.APP_ENV == "production",
        path="/",
    )
    return resp


@router.post("/logout")
async def logout() -> RedirectResponse:
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE, path="/")
    return resp
