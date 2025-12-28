import pytest

from .conftest import build_url


@pytest.mark.live
def test_stripe_webhook_rejects_bad_request(http, live_base_url):
    url = build_url(live_base_url, "listings:stripe_webhook")
    r = http.post(url, data=b"{}", headers={"Content-Type": "application/json"}, timeout=30)
    assert 400 <= r.status_code < 500
