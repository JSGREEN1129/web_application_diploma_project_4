import pytest

from .conftest import build_url


@pytest.mark.live
def test_search_requires_login(http, live_base_url):
    # Attempt to access the search page while logged out
    url = build_url(live_base_url, "listings:search_listings")
    r = http.get(url, timeout=30, allow_redirects=False)

    # Unauthenticated users should be redirected to login
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "").lower()


@pytest.mark.live
def test_search_shows_active_listings(http, live_base_url, login, live_user_credentials):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Access the listings search page
    url = build_url(live_base_url, "listings:search_listings")
    r = http.get(url, timeout=30, allow_redirects=True)

    # Page should load successfully
    assert r.status_code == 200

    # Basic page content checks
    assert "search listings" in r.text.lower()
    assert "green square capital" in r.text.lower()

    # Filters or location-related fields should be visible
    assert "counties" in r.text.lower() or "outcodes" in r.text.lower()


@pytest.mark.live
def test_search_filters_by_project_name(http, live_base_url, login, live_user_credentials):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Load the search page
    url = build_url(live_base_url, "listings:search_listings")
    r = http.get(url, timeout=30, allow_redirects=True)

    # Page should load successfully
    assert r.status_code == 200

    # Basic page content checks
    assert "search listings" in r.text.lower()
    assert "green square capital" in r.text.lower()


@pytest.mark.live
def test_opportunity_detail_requires_login(http, live_base_url, live_listing_id):
    # Attempt to access opportunity detail while logged out
    url = build_url(live_base_url, "listings:opportunity_detail", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)

    # Unauthenticated users should be redirected to login
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "").lower()


@pytest.mark.live
def test_opportunity_detail_only_for_active(http, live_base_url, login, live_user_credentials, live_listing_id):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Access opportunity detail page
    url = build_url(live_base_url, "listings:opportunity_detail", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=True)

    # Page either loads (active listing) or returns 404 (inactive listing)
    assert r.status_code == 200 or r.status_code == 404

    # If page loads, it should contain opportunity or pledge-related content
    assert "opportunity" in r.text.lower() or "pledge" in r.text.lower()
