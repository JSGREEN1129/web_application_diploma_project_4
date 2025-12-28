import pytest

from .conftest import build_url


@pytest.mark.live
def test_listing_detail_loads(http, live_base_url, live_listing_id):
    url = build_url(live_base_url, "listings:listing_detail", args=[live_listing_id])
    r = http.get(url, timeout=30)
    assert r.status_code == 200


@pytest.mark.live
def test_estimate_return_requires_auth_or_returns_200(http, live_base_url, live_listing_id):

    url = build_url(live_base_url, "listings:estimate_return", args=[live_listing_id], query="amount=100")
    r = http.get(url, timeout=30, allow_redirects=False)
    assert r.status_code in (200, 302, 401, 403)


@pytest.mark.live
def test_estimate_return_json_when_authenticated(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "listings:estimate_return", args=[live_listing_id], query="amount=100")
    r = http.get(url, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    for key in ["min_pct", "max_pct", "profit_min", "profit_max", "total_min", "total_max", "duration_days"]:
        assert key in data
