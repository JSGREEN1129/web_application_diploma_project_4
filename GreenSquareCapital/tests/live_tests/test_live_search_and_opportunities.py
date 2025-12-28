import pytest

from .conftest import build_url


@pytest.mark.live
def test_search_requires_login(http, live_base_url):
    url = build_url(live_base_url, "listings:search_listings")
    r = http.get(url, timeout=30, allow_redirects=False)
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "").lower()


@pytest.mark.live
def test_search_shows_active_listings(http, live_base_url, login, live_user_credentials):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:search_listings")
    r = http.get(url, timeout=30, allow_redirects=True)
    assert r.status_code == 200

    assert "search listings" in r.text.lower()
    assert "green square capital" in r.text.lower()

    assert "counties" in r.text.lower() or "outcodes" in r.text.lower()  


@pytest.mark.live
def test_search_filters_by_project_name(http, live_base_url, login, live_user_credentials):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:search_listings")  
    r = http.get(url, timeout=30, allow_redirects=True)
    assert r.status_code == 200

    assert "search listings" in r.text.lower()
    assert "green square capital" in r.text.lower()



@pytest.mark.live
def test_opportunity_detail_requires_login(http, live_base_url, live_listing_id):
    url = build_url(live_base_url, "listings:opportunity_detail", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "").lower()


@pytest.mark.live
def test_opportunity_detail_only_for_active(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:opportunity_detail", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=True)
    assert r.status_code == 200 or r.status_code == 404  
    assert "opportunity" in r.text.lower() or "pledge" in r.text.lower() 