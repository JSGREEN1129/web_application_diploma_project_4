import pytest

from .conftest import build_url


@pytest.mark.live
def test_stripe_webhook_rejects_bad_request(http, live_base_url):
    # Call the Stripe webhook endpoint with an invalid / unsigned payload
    url = build_url(live_base_url, "listings:stripe_webhook")
    r = http.post(
        url,
        data=b"{}",  # Empty JSON payload (no Stripe signature)
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    # Webhook should reject malformed or unauthenticated requests
    assert 400 <= r.status_code < 500


@pytest.mark.live
@pytest.mark.skip("Requires real Stripe config/sig — test manually or with ngrok")
def test_stripe_webhook_returns_200_on_valid(http, live_base_url):
    # Call the Stripe webhook endpoint with a simulated valid payload
    # (Skipped by default because it requires real Stripe signing configuration)
    url = build_url(live_base_url, "listings:stripe_webhook")

    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": "fake_sig"  # Placeholder signature
    }

    # Example Stripe event payload (checkout completed)
    data = b'{"type": "checkout.session.completed", "data": {"object": {"payment_status": "paid"}}}'

    r = http.post(url, data=data, headers=headers, timeout=30)

    # With valid Stripe verification, the webhook should acknowledge the event
    assert r.status_code == 200
