"""
Test that all public nginx endpoints are protected against unauthenticated access.

Each endpoint has its own expected unauthenticated behavior:
  - "401"      : server must return HTTP 401 (nginx basic auth)
  - "redirect" : server must redirect to a specific path (e.g. navidrome login)

Optionally re-tests with credentials to confirm authenticated access works.

Usage:
    # Test unauthenticated behavior only:
    python test_auth.py --base-url https://example.com

    # Also verify authenticated access works — credentials via env var:
    WEBRADIO_CREDENTIALS=user:pass python test_auth.py --base-url https://example.com --with-auth

    # Also verify authenticated access works — credentials via interactive prompt:
    python test_auth.py --base-url https://example.com --with-auth
"""

import argparse
import getpass
import os
import sys
import time
from dataclasses import dataclass
from typing import Literal

import requests

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"


@dataclass
class Endpoint:
    path: str
    description: str
    # Expected unauthenticated behavior: 401 block, HTTP redirect, or 2xx where
    # the application handles auth internally (e.g. a SPA with a JS-driven login redirect)
    unauth_expect: Literal["401", "redirect", "app_handles_auth"]
    # Required when unauth_expect == "redirect": the path that Location must contain
    redirect_to: str | None = None


PUBLIC_ENDPOINTS: list[Endpoint] = [
    Endpoint("/", "Main site (webtune_live)", unauth_expect="401"),
    Endpoint(
        "/navidrome/app",
        "Navidrome music server proxy",
        # Navidrome serves its SPA shell (200); login redirect is handled client-side by JS
        unauth_expect="app_handles_auth",
    ),
    Endpoint("/recime", "Recime backend proxy", unauth_expect="401"),
    Endpoint("/recime/", "Recime backend proxy (subpath)", unauth_expect="401"),
]


def load_credentials() -> tuple[str, str] | None:
    """
    Load credentials from WEBRADIO_CREDENTIALS env var (user:pass) or by
    prompting interactively. Returns (username, password) or None if the
    user declines to enter credentials.
    """
    env_val = os.environ.get("WEBRADIO_CREDENTIALS", "")
    if env_val:
        parts = env_val.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            print(
                "Error: WEBRADIO_CREDENTIALS must be in user:pass format",
                file=sys.stderr,
            )
            sys.exit(2)
        return (parts[0], parts[1])

    # Fall back to interactive prompt.
    print("No WEBRADIO_CREDENTIALS env var set — enter credentials interactively.")
    username = input("Username: ").strip()
    if not username:
        print("No username provided; skipping authenticated checks.", file=sys.stderr)
        return None
    password = getpass.getpass("Password: ")
    if not password:
        print("No password provided; skipping authenticated checks.", file=sys.stderr)
        return None
    return (username, password)


def check_unauthenticated(
    base_url: str, endpoint: Endpoint
) -> tuple[str, int | None, str]:
    """
    Check that an unauthenticated request is blocked as expected.
    Returns (status, http_code, message).
    """
    url = base_url.rstrip("/") + endpoint.path
    try:
        response = requests.get(url, timeout=10, allow_redirects=False)
        code = response.status_code

        if endpoint.unauth_expect == "401":
            if code == 401:
                return PASS, code, "correctly returned 401 Unauthorized"
            else:
                return FAIL, code, f"expected 401 but got {code} — endpoint may be unprotected"

        elif endpoint.unauth_expect == "redirect":
            if code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                if endpoint.redirect_to and endpoint.redirect_to not in location:
                    return (
                        FAIL,
                        code,
                        f"redirected but Location '{location}' does not contain '{endpoint.redirect_to}'",
                    )
                return PASS, code, f"correctly redirected to '{location}'"
            else:
                return (
                    FAIL,
                    code,
                    f"expected a redirect to '{endpoint.redirect_to}' but got {code}",
                )

        elif endpoint.unauth_expect == "app_handles_auth":
            if 200 <= code < 300:
                return PASS, code, "app shell served; auth is handled by the application"
            else:
                return FAIL, code, f"expected 2xx (app handles auth) but got {code}"

    except requests.ConnectionError as e:
        return ERROR, None, f"connection error: {e}"
    except requests.Timeout:
        return ERROR, None, "request timed out"
    except requests.RequestException as e:
        return ERROR, None, f"request failed: {e}"


def check_authenticated(
    base_url: str, endpoint: Endpoint, credentials: tuple[str, str]
) -> tuple[str, int | None, str]:
    """
    Check that an authenticated request is not blocked with 401.
    Returns (status, http_code, message).
    """
    url = base_url.rstrip("/") + endpoint.path
    try:
        response = requests.get(url, auth=credentials, timeout=10, allow_redirects=False)
        code = response.status_code
        if code != 401:
            return PASS, code, f"authenticated request returned {code}"
        else:
            return FAIL, code, "credentials provided but still got 401 — check credentials"
    except requests.ConnectionError as e:
        return ERROR, None, f"connection error: {e}"
    except requests.Timeout:
        return ERROR, None, "request timed out"
    except requests.RequestException as e:
        return ERROR, None, f"request failed: {e}"


def wait_for_server(base_url: str) -> bool:
    """Wait up to 60 seconds for the server to respond. Returns False on timeout."""
    start_time = time.time()
    while True:
        try:
            requests.get(base_url, timeout=5, allow_redirects=False)
            return True
        except requests.ConnectionError:
            if time.time() - start_time > 60:
                print("Error: Server did not respond within 60 seconds.", file=sys.stderr)
                return False
            print("Waiting for server to be up...", end="\r")
            time.sleep(5)


def run_tests(base_url: str, credentials: tuple[str, str] | None) -> bool:
    """Run all endpoint checks and return True if all pass."""
    if not wait_for_server(base_url):
        return False

    all_passed = True

    # --- Unauthenticated checks ---
    print(f"\n{'='*60}")
    print("Checking endpoints WITHOUT credentials")
    print(f"{'='*60}")

    for endpoint in PUBLIC_ENDPOINTS:
        result, code, message = check_unauthenticated(base_url, endpoint)
        code_str = str(code) if code is not None else "N/A"
        expect_label = f"expect {endpoint.unauth_expect}" + (
            f" → {endpoint.redirect_to}" if endpoint.redirect_to else ""
        )
        print(f"[{result:5s}] {endpoint.path:<20} ({endpoint.description}; {expect_label})")
        print(f"        HTTP {code_str}: {message}")
        if result != PASS:
            all_passed = False

    # --- Authenticated checks (optional) ---
    if credentials is not None:
        print(f"\n{'='*60}")
        print("Checking endpoints WITH credentials (expect non-401)")
        print(f"{'='*60}")

        for endpoint in PUBLIC_ENDPOINTS:
            if endpoint.unauth_expect == "app_handles_auth":
                print(f"[SKIP ] {endpoint.path:<20} ({endpoint.description})")
                print(f"        skipped — application manages its own credentials")
                continue
            result, code, message = check_authenticated(base_url, endpoint, credentials)
            code_str = str(code) if code is not None else "N/A"
            print(f"[{result:5s}] {endpoint.path:<20} ({endpoint.description})")
            print(f"        HTTP {code_str}: {message}")
            if result == FAIL:
                all_passed = False

    print(f"\n{'='*60}")
    print(f"Overall result: {'ALL PASSED ✓' if all_passed else 'FAILURES DETECTED ✗'}")
    print(f"{'='*60}\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Verify that all nginx endpoints are protected against unauthenticated access.",
        epilog=(
            "Credentials can be supplied via the WEBRADIO_CREDENTIALS=user:pass "
            "environment variable, or entered interactively when --with-auth is given."
        ),
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of the server, e.g. https://example.com",
    )
    parser.add_argument(
        "--with-auth",
        action="store_true",
        default=False,
        help=(
            "Also verify that authenticated requests succeed. "
            "Reads credentials from WEBRADIO_CREDENTIALS env var or prompts interactively."
        ),
    )
    args = parser.parse_args()

    credentials = None
    if args.with_auth:
        credentials = load_credentials()

    passed = run_tests(args.base_url, credentials)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
