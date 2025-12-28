import pytest

from .conftest import build_url


@pytest.mark.live
def test_login_and_dashboard(http, live_base_url, login, live_user_credentials):
    username, password = live_user_credentials
    login(username, password)
    dash = build_url(live_base_url, "users:dashboard")
    r = http.get(dash, timeout=30)
    assert r.status_code == 200


@pytest.mark.live
def test_search_listings(http, live_base_url):
    url = build_url(live_base_url, "listings:search_listings", query="q=")
    r = http.get(url, timeout=30)
    assert r.status_code == 200
