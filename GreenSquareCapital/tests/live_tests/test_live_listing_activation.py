import pytest

from .conftest import build_url


@pytest.mark.live
def test_activate_requires_login(http, live_base_url, live_listing_id):
    # Attempt to activate a listing while logged out
    url = build_url(live_base_url, "listings:activate_listing", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)

    # Unauthenticated users should be redirected to login
    assert r.status_code in (301, 302, 303)
    assert "users/login" in r.headers.get("Location", "")


@pytest.mark.live
def test_activate_only_draft_listings(http, live_base_url, login, live_user_credentials, live_listing_id):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Attempt to activate the listing
    url = build_url(live_base_url, "listings:activate_listing", args=[live_listing_id])
    r = http.get(url, timeout=60, allow_redirects=True)

    # Activation either:
    # - shows a validation message (already active / not draft), or
    # - proceeds into the checkout / activation flow
    assert r.status_code == 200 or r.status_code == 302

    if "only draft listings can be activated" in r.text.lower():
        # Expected validation message for non-draft listings
        pass
    else:
        # Otherwise, user should be taken into the activation flow
        assert "checkout" in r.text.lower()
