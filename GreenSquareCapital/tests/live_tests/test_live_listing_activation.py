import pytest

from .conftest import build_url


@pytest.mark.live
def test_activate_requires_login(http, live_base_url, live_listing_id):
    url = build_url(live_base_url, "listings:activate_listing", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "")


@pytest.mark.live
def test_activate_only_draft_listings(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:activate_listing", args=[live_listing_id])
    r = http.get(url, timeout=60, allow_redirects=True)  
    assert r.status_code == 200 or r.status_code == 302
    if "only draft listings can be activated" in r.text.lower():
        pass  
    else:
        assert "checkout" in r.text.lower() 


