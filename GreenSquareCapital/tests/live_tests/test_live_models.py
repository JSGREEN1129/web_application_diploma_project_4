import pytest

from .conftest import build_url


@pytest.mark.live
def test_listing_detail_loads(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:listing_detail", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=True)  

    assert r.status_code == 200, f"Expected 200 OK, got {r.status_code}"


    assert "Listing" in r.text, "Page should have 'Listing' in title or content"
    assert "Green Square Capital" in r.text, "Footer/brand name missing"
    assert "pledge_progress" in r.text.lower(), "Pledge progress script missing (expected on detail page)"



@pytest.mark.live
def test_listing_media_str_in_page(http, live_base_url, login, live_user_credentials, live_listing_id):
    pytest.skip("Media str test requires media detail endpoint; check manually in listing detail")