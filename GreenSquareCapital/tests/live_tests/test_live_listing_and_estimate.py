import pytest

from .conftest import build_url


@pytest.mark.live
def test_estimate_return_json_when_authenticated(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    assert any(c.name == "sessionid" for c in http.cookies), (
        f"Expected sessionid cookie after login. Cookies={[c.name for c in http.cookies]}"
    )

    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": live_base_url.rstrip("/"),
        "Referer": build_url(live_base_url, "listings:listing_detail", args=[live_listing_id]),
    }

    url = build_url(live_base_url, "listings:estimate_return", args=[live_listing_id])

    r = http.get(url, headers=headers, params={"amount": "100"}, timeout=30, allow_redirects=False)

    if r.status_code in (301, 302, 303, 307, 308):
        location = r.headers.get("Location", "")
        pytest.fail(f"estimate_return redirected unexpectedly to: {location}")

    assert r.status_code == 200

    content_type = (r.headers.get("Content-Type") or "").lower()
    assert "application/json" in content_type, (
        f"Expected JSON but got Content-Type={content_type}. "
        f"Final URL={r.url}. Body starts:\n{r.text[:300]}"
    )

    data = r.json()
    assert isinstance(data, dict)
    assert data.get("ok") is True
