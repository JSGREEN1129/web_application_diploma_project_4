import pytest

from .conftest import build_url


@pytest.mark.live
def test_pledge_requires_login(http, live_base_url, live_listing_id):
    login_url = build_url(live_base_url, "users:login")
    r_get = http.get(login_url, timeout=30)
    csrf_token = http.cookies.get('csrftoken') or ""

    if not csrf_token:
        pytest.fail(
            "No csrftoken cookie received even after GET to login page!\n"
            "This means the login template is missing {% csrf_token %} or forms.\n"
            f"Response body start:\n{r_get.text[:500]}"
        )

    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])

    headers = {
        "Referer": login_url,
        "Origin": live_base_url.rstrip("/"),
    }

    data = {
        "amount_gbp": "100.00",
        "csrfmiddlewaretoken": csrf_token
    }

    r = http.post(url, data=data, headers=headers, timeout=30, allow_redirects=False)

    if r.status_code not in (301, 302, 303):
        pytest.fail(
            f"Expected redirect to login (301/302/303) but got {r.status_code}\n"
            f"URL: {url}\n"
            f"CSRF token used: {csrf_token}\n"
            f"Headers sent: {headers}\n"
            f"Cookies after GET: {[c.name for c in http.cookies]}\n"
            f"Response body start:\n{r.text[:500]}"
        )

    location = r.headers.get("Location", "")
    assert "users/login" in location.lower(), f"Expected redirect to login, but got: {location}"


@pytest.mark.live
def test_pledge_get_not_allowed(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)
    assert r.status_code == 405, f"Expected 405 Method Not Allowed, got {r.status_code}"


@pytest.mark.live
@pytest.mark.skip("Creates data — run only if safe on live; clean up after")
def test_pledge_success(http, live_base_url, login, live_user_credentials, live_listing_id):
    username, password = live_user_credentials
    login(username, password)

    login_url = build_url(live_base_url, "users:login")
    r_get = http.get(login_url, timeout=30)
    csrf_token = http.cookies.get('csrftoken') or ""

    if not csrf_token:
        pytest.fail("No csrftoken cookie received after login")

    headers = {
        "Referer": build_url(live_base_url, "listings:listing_detail", args=[live_listing_id]),
        "Origin": live_base_url.rstrip("/"),
    }

    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])

    data = {
        "amount_gbp": "100.00",
        "csrfmiddlewaretoken": csrf_token
    }

    r = http.post(url, data=data, headers=headers, timeout=60, allow_redirects=True)

    assert r.status_code == 200, f"Expected 200 OK after pledge, got {r.status_code}"

    success_phrases = [
        "pledge created",
        "successfully pledged",
        "investment created",
        "pledge successful",
        "thank you",
        "success"
    ]
    assert any(phrase in r.text.lower() for phrase in success_phrases), (
        f"Success message not found.\n"
        f"Response body start:\n{r.text[:500]}"
    )