from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

import os
import re
from urllib.parse import urljoin

import pytest
import requests


def _setup_django():
    # Ensure Django knows which settings module to use for reverse()
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        os.getenv("DJANGO_SETTINGS_MODULE", "GreenSquareCapital.settings"),
    )

    # Initialise Django
    import django
    django.setup()


_setup_django() 

from django.urls import reverse 


def build_url(base_url: str, viewname: str, args=None, kwargs=None, query: str | None = None) -> str:
    # Build a full URL using Django reverse() and the live base URL
    path = reverse(viewname, args=args or (), kwargs=kwargs or {})
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))

    # Optional query string support
    if query:
        url = url + ("&" if "?" in url else "?") + query.lstrip("?")

    return url


@pytest.fixture(scope="session")
def live_base_url() -> str:
    # Base URL of the deployed site
    base = os.getenv("LIVE_BASE_URL", "").strip()
    if not base:
        pytest.skip("LIVE_BASE_URL is not set")
    return base


@pytest.fixture()
def http() -> requests.Session:
    # Shared session so cookies remain across requests (login -> authenticated calls)
    s = requests.Session()
    s.headers.update({"User-Agent": "greensquare-live-tests/1.0"})
    return s


def _find_form(html: str):
    # Find all form blocks (content between <form> and </form>)
    form_blocks = list(re.finditer(r'<form\b[^>]*>(.*?)</form>', html, re.IGNORECASE | re.DOTALL))

    selected_form_content = None
    action = ""

    # Prefer the login form:
    # - action contains /users/login/
    # - OR form contains login_submit button
    for form_match in form_blocks:
        form_content = form_match.group(1)
        form_tag = form_match.group(0)

        # Extract action from opening <form ...> tag
        action_match = re.search(r'action=["\']([^"\']+)["\']', form_tag, re.IGNORECASE)
        form_action = action_match.group(1) if action_match else ""

        if '/users/login/' in form_action or 'name="login_submit"' in form_content:
            selected_form_content = form_content
            action = form_action
            break

    # Fallback: if we can’t detect a login form, use the first form found
    if selected_form_content is None and form_blocks:
        selected_form_content = form_blocks[0].group(1)
        action_match = re.search(r'action=["\']([^"\']+)["\']', form_blocks[0].group(0), re.IGNORECASE)
        action = action_match.group(1) if action_match else ""

    # If no forms exist at all, fail clearly
    if selected_form_content is None:
        raise ValueError("No form found on page")

    # Extract input fields from the selected form
    inputs = {}
    for tag_match in re.finditer(r'<input\b[^>]*>', selected_form_content, re.IGNORECASE):
        tag = tag_match.group(0)

        name_match = re.search(r'name=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if not name_match:
            continue
        name = name_match.group(1)

        value_match = re.search(r'value=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        value = value_match.group(1) if value_match else ""

        inputs[name] = value

    return action, inputs


def _pick_first_present(candidates, present):
    # Utility: return the first candidate that exists in the provided set/dict
    for c in candidates:
        if c in present:
            return c
    return None


@pytest.fixture()
def login(http: requests.Session, live_base_url: str):
    # Returns a helper function that logs in and returns the authenticated session
    def _login(username: str, password: str, *, next_view: str = "users:dashboard") -> requests.Session:
        # Build login URL from Django route name
        login_url = build_url(live_base_url, "users:login")

        # Step 1: GET the login page 
        r_get = http.get(login_url, timeout=30, allow_redirects=True)
        r_get.raise_for_status()

        # Find the login form and any hidden inputs
        action, inputs = _find_form(r_get.text)
        post_url = urljoin(login_url, action) if action else login_url

        # CSRF token can appear as:
        # - hidden form input
        # - cookie value
        csrf_token = inputs.get("csrfmiddlewaretoken") or http.cookies.get("csrftoken") or http.cookies.get("csrf")

        # Headers commonly expected by CSRF protection
        headers = {
            "Referer": login_url,
            "Origin": live_base_url.rstrip("/"),
        }
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token

        # Login form fields
        user_field = "username"
        pass_field = "password"

        # POST payload
        data = {
            "csrfmiddlewaretoken": csrf_token,
            user_field: username,
            pass_field: password,
            "login_submit": "Sign In"
        }

        # Step 2: POST credentials and follow redirects
        r_post = http.post(post_url, data=data, headers=headers, timeout=30, allow_redirects=True)

        # Success check: Django session cookie should exist after login
        if not any(c.name == "sessionid" for c in http.cookies):
            raise AssertionError(
                "Login failed: sessionid cookie was not set.\n"
                f"POST URL: {post_url}\n"
                f"Final URL: {r_post.url}\n"
                f"Cookies now: {[c.name for c in http.cookies]}\n"
                f"Form fields sent: {sorted(data.keys())}\n"
                f"Response starts:\n{r_post.text[:800]}"
            )

        return http

    return _login


@pytest.fixture(scope="session")
def live_user_credentials():
    # Credentials used for live testing (stored in env vars)
    u = os.getenv("LIVE_TEST_USERNAME") or os.getenv("LIVE_TEST_EMAIL") or ""
    p = os.getenv("LIVE_TEST_PASSWORD") or ""
    if not (u and p):
        pytest.skip("Missing live test credentials")
    return u, p


@pytest.fixture(scope="session")
def live_listing_id() -> str:
    # Listing ID used for live listing tests (stored in env vars)
    pk = os.getenv("LIVE_TEST_LISTING_ID", "").strip()
    if not pk:
        pytest.skip("Missing live listing id")
    return pk
