"""Sign-in for private pages (SPEC 11.0)."""

import time

import pytest

from app import auth
from app.config import Settings

PRIVATE = ["/garden", "/seeds", "/tasks", "/species", "/admin"]


@pytest.fixture(autouse=True)
def _reset_fails():
    auth._FAILS.clear()
    yield
    auth._FAILS.clear()


def login(client, password=None, nxt="/"):
    s = Settings()
    return client.post(
        "/login",
        data={"username": s.ADMIN_USER, "password": password or s.ADMIN_PASSWORD, "next": nxt},
        follow_redirects=False,
    )


@pytest.mark.parametrize("path", PRIVATE)
def test_private_pages_redirect_to_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/login?next={path}"


def test_login_sets_cookie_and_opens_private_pages(client):
    r = login(client, nxt="/tasks")
    assert r.status_code == 303 and r.headers["location"] == "/tasks"
    assert auth.COOKIE in r.cookies
    for path in PRIVATE:
        assert client.get(path).status_code == 200, path
    t = client.get("/").text
    assert 'href="/garden"' in t and "Sign out" in t


def test_wrong_password_401_and_rate_limit(client):
    assert login(client, password="nope").status_code == 401
    for _ in range(auth.MAX_FAILS):
        login(client, password="nope")
    assert login(client).status_code == 429  # even the right password, until the window passes


def test_logout_clears_cookie(client):
    login(client)
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    client.cookies.clear()
    assert client.get("/tasks", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("nxt", ["//evil.com", "https://evil.com", "/\\evil", ""])
def test_next_must_be_local(client, nxt):
    assert login(client, nxt=nxt).headers["location"] == "/"


def test_cookie_tamper_and_expiry():
    s = Settings()
    good = auth.make_cookie(s.ADMIN_USER, s)
    assert auth.read_cookie(good, s) == s.ADMIN_USER
    assert auth.read_cookie(good[:-1] + ("0" if good[-1] != "0" else "1"), s) is None
    old = auth.make_cookie(s.ADMIN_USER, s, now=time.time() - (s.SESSION_DAYS + 1) * 86400)
    assert auth.read_cookie(old, s) is None
    assert auth.read_cookie(auth.make_cookie("someone-else", s), s) is None


def test_basic_auth_for_scripts(client):
    s = Settings()
    assert client.get("/admin", auth=(s.ADMIN_USER, s.ADMIN_PASSWORD)).status_code == 200
    assert client.get("/admin", auth=(s.ADMIN_USER, "wrong")).status_code == 401
