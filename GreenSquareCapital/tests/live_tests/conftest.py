import os
import re
from urllib.parse import urljoin

import pytest
import requests

def _setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "GreenSquareCapital.settings"))
    try:
        import django  # type: ignore
        django.setup()
    except Exception as e:
        raise RuntimeError(
            "Failed to set up Django for URL reversing. "
            "Make sure your repo (including apps and urls) is on PYTHONPATH and "
            "DJANGO_SETTINGS_MODULE points at your settings module. "
            f"Original error: {e!r}"
        )

_setup_django()

from django.urls import reverse  # noqa: E402


def build_url(base_url: str, viewname: str, args=None, kwargs=None, query: str | None = None) -> str:
    path = reverse(viewname, args=args or (), kwargs=kwargs or {})
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    if query:
        url = url + ("&" if "?" in url else "?") + query.lstrip("?")
    return url


@pytest.fixture(scope="session")
def live_base_url() -> str:
    base = os.getenv("LIVE_BASE_URL", "").strip()
    if not base:
        pytest.skip("LIVE_BASE_URL is not set (e.g. https://your-app.onrender.com)")
    return base


@pytest.fixture()
def http() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "greensquare-live-tests/1.0"})
    return s


def _extract_csrf(html: str) -> str | None:
    m = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.fixture()
def login(http: requests.Session, live_base_url: str):
    """Return a function that logs in and leaves the session authenticated (cookies preserved)."""

    def _login(username: str, password: str, *, next_view: str = "users:dashboard") -> requests.Session:
        login_url = build_url(live_base_url, "users:login")
        r_get = http.get(login_url, timeout=30)
        r_get.raise_for_status()

        csrf_token = _extract_csrf(r_get.text) or http.cookies.get("csrftoken") or http.cookies.get("csrf")
        headers = {}
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token

        data = {
            "username": username,
            "email": username,
            "password": password,
        }
        if csrf_token:
            data["csrfmiddlewaretoken"] = csrf_token

        r_post = http.post(login_url, data=data, headers=headers, allow_redirects=True, timeout=30)
        if r_post.status_code not in (200, 302):
            raise AssertionError(f"Unexpected login response: {r_post.status_code} {r_post.text[:300]}")

        dash_url = build_url(live_base_url, next_view)
        r_dash = http.get(dash_url, timeout=30, allow_redirects=True)
        if r_dash.status_code != 200:
            raise AssertionError(
                f"Login did not yield access to {next_view}. "
                f"Dashboard status={r_dash.status_code}, final_url={r_dash.url}"
            )
        return http

    return _login


@pytest.fixture(scope="session")
def live_user_credentials():
    """Optional dedicated live test account credentials."""
    u = os.getenv("LIVE_TEST_USERNAME") or os.getenv("LIVE_TEST_EMAIL") or ""
    p = os.getenv("LIVE_TEST_PASSWORD") or ""
    if not (u and p):
        pytest.skip("Set LIVE_TEST_USERNAME (or LIVE_TEST_EMAIL) and LIVE_TEST_PASSWORD to run authenticated live tests.")
    return u, p


@pytest.fixture(scope="session")
def live_listing_id() -> str:
    """A listing PK to use for read-only tests (detail/estimate-return/opportunity)."""
    pk = os.getenv("LIVE_TEST_LISTING_ID", "").strip()
    if not pk:
        pytest.skip("Set LIVE_TEST_LISTING_ID (an existing listing PK on the live site) to run listing-based tests.")
    return pk
