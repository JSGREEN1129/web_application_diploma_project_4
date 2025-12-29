import pytest

from .conftest import build_url


@pytest.mark.live
def test_pledge_requires_login(http, live_base_url, live_listing_id):
    # Get login page first
    login_url = build_url(live_base_url, "users:login")
    r_get = http.get(login_url, timeout=30)

    # CSRF token is expected to be set as a cookie after GET
    csrf_token = http.cookies.get('csrftoken') or ""

    # If there is no CSRF cookie, the login page is missing CSRF / form setup
    if not csrf_token:
        pytest.fail(
            "No csrftoken cookie received even after GET to login page!\n"
            "This means the login template is missing {% csrf_token %} or forms.\n"
            f"Response body start:\n{r_get.text[:500]}"
        )

    # Build the pledge URL for a known live listing
    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])

    # CSRF headers that Django commonly expects
    headers = {
        "Referer": login_url,
        "Origin": live_base_url.rstrip("/"),
    }

    # Minimal pledge payload
    data = {
        "amount_gbp": "100.00",
        "csrfmiddlewaretoken": csrf_token
    }

    # POST while unauthenticated
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

    # Confirm redirect target points to login
    location = r.headers.get("Location", "")
    assert "users/login" in location.lower(), f"Expected redirect to login, but got: {location}"


@pytest.mark.live
def test_pledge_get_not_allowed(http, live_base_url, login, live_user_credentials, live_listing_id):
    # Log in first
    username, password = live_user_credentials
    login(username, password)

    # Pledge view should be POST-only
    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])
    r = http.get(url, timeout=30, allow_redirects=False)

    # GET should return 405 Method Not Allowed
    assert r.status_code == 405, f"Expected 405 Method Not Allowed, got {r.status_code}"


@pytest.mark.live
@pytest.mark.skip("Creates data — run only if safe on live; clean up after")
def test_pledge_success(http, live_base_url, login, live_user_credentials, live_listing_id):
    # Log in using live test credentials
    username, password = live_user_credentials
    login(username, password)

    # Get login page again to collect CSRF cookie for POST
    login_url = build_url(live_base_url, "users:login")
    r_get = http.get(login_url, timeout=30)
    csrf_token = http.cookies.get('csrftoken') or ""

    # If there is no CSRF cookie, POST will be rejected
    if not csrf_token:
        pytest.fail("No csrftoken cookie received after login")

    # Use listing detail
    headers = {
        "Referer": build_url(live_base_url, "listings:listing_detail", args=[live_listing_id]),
        "Origin": live_base_url.rstrip("/"),
    }

    # Build pledge URL
    url = build_url(live_base_url, "investments:pledge", args=[live_listing_id])

    # Pledge data
    data = {
        "amount_gbp": "100.00",
        "csrfmiddlewaretoken": csrf_token
    }

    # Submit pledge and follow redirects to final page
    r = http.post(url, data=data, headers=headers, timeout=60, allow_redirects=True)

    # Expect success response after completing flow
    assert r.status_code == 200, f"Expected 200 OK after pledge, got {r.status_code}"

    # Check page contains a likely success indicator
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
