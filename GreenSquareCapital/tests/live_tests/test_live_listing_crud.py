import pytest

from .conftest import build_url


@pytest.mark.live
@pytest.mark.skip("Destructive test — run only if safe on live with test draft listing")
def test_listing_delete_requires_login(http, live_base_url, live_listing_id):
    url = build_url(live_base_url, "listings:listing_delete", args=[live_listing_id])
    r = http.post(url, data={"password": "Password123!"}, timeout=30, allow_redirects=False)
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "")


@pytest.mark.live
@pytest.mark.skip("Destructive test — run only if safe on live with test draft listing")
def test_listing_delete_requires_correct_password(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:listing_delete", args=[live_listing_id])
    r = http.post(url, data={"password": "WRONG"}, timeout=30, allow_redirects=True)
    assert r.status_code == 200  
    assert "incorrect password" in r.text.lower()


@pytest.mark.live
@pytest.mark.skip("Destructive test — run only if safe on live with test draft listing")
def test_listing_delete_success(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:listing_delete", args=[live_listing_id])
    r = http.post(url, data={"password": "Password123!"}, timeout=30, allow_redirects=True)
    assert r.status_code == 200 
    assert "listing deleted" in r.text.lower()


