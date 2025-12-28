import pytest

from .conftest import build_url


@pytest.mark.live
def test_homepage_loads(http, live_base_url):
    url = live_base_url.rstrip("/") + "/"
    r = http.get(url, timeout=30, allow_redirects=True)
    assert r.status_code == 200


@pytest.mark.live
def test_login_page_loads(http, live_base_url):
    url = build_url(live_base_url, "users:login")
    r = http.get(url, timeout=30)
    assert r.status_code == 200
