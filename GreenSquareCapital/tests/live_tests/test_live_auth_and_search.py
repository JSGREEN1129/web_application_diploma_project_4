import pytest

from .conftest import build_url


@pytest.mark.live
def test_login_and_dashboard(http, live_base_url, login, live_user_credentials):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Access the dashboard page after login
    dash = build_url(live_base_url, "users:dashboard")
    r = http.get(dash, timeout=30)

    # Dashboard should load successfully for an authenticated user
    assert r.status_code == 200


@pytest.mark.live
def test_search_listings(http, live_base_url):
    # Access the public listings search page with an empty query
    url = build_url(live_base_url, "listings:search_listings", query="q=")
    r = http.get(url, timeout=30)

    # Search page should load successfully
    assert r.status_code == 200
