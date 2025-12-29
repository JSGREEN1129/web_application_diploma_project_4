import pytest

from .conftest import build_url


@pytest.mark.live
def test_homepage_loads(http, live_base_url):
    # Request the public homepage
    url = live_base_url.rstrip("/") + "/"
    r = http.get(url, timeout=30, allow_redirects=True)

    # Homepage should load successfully
    assert r.status_code == 200


@pytest.mark.live
def test_login_page_loads(http, live_base_url):
    # Request the login page
    url = build_url(live_base_url, "users:login")
    r = http.get(url, timeout=30)

    # Login page should load successfully
    assert r.status_code == 200
