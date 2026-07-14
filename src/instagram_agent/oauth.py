"""Instagram / Facebook OAuth 2.0 flow.

Implements the Authorization Code flow for Instagram Graph API:

1. Generate the Facebook authorization URL
2. Spin up a local HTTP server to capture the callback ?code=
3. Exchange the code for a short-lived User access token
4. Exchange the short-lived token for a long-lived token
5. Optionally exchange for a long-lived page token (needed for IG posting)
6. Persist the tokens + IG account ID into config.ini

References:
  https://developers.facebook.com/docs/instagram-platform/getting-started
  https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow
"""

import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple

import requests

from instagram_agent.config import (
    get_fb_app_id,
    get_fb_app_secret,
    save_token_to_config,
    CONFIG_FILE,
)

FB_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FB_GRAPH_URL = "https://graph.facebook.com/v19.0"

# Scopes required for Instagram content publishing
IG_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]

# ── Local HTTP server to capture the OAuth callback ─────────────────────

_CALLBACK_CODE: Optional[str] = None
_CALLBACK_ERROR: Optional[str] = None
_CALLBACK_EVENT = threading.Event()


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the ?code= from the OAuth redirect."""

    def do_GET(self):
        global _CALLBACK_CODE, _CALLBACK_ERROR

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _CALLBACK_CODE = params["code"][0]
            self._respond(
                200,
                "✅ Authorization successful! You can close this tab.",
            )
        elif "error" in params:
            _CALLBACK_ERROR = params.get("error_description", params["error"])[0]
            self._respond(
                400,
                f"❌ Authorization failed: {_CALLBACK_ERROR}",
            )
        else:
            self._respond(400, "❌ Unexpected callback — no code or error.")

        _CALLBACK_EVENT.set()

    def _respond(self, status: int, message: str):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body><h2>{message}</h2></body></html>".encode()
        )

    def log_message(self, format, *args):
        # Suppress noisy HTTP server logs
        pass


# ── Public API ──────────────────────────────────────────────────────────


def generate_auth_url(app_id: str, redirect_uri: str, state: str = "ig-agent") -> str:
    """Build the Facebook OAuth authorization URL."""
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(IG_SCOPES),
        "response_type": "code",
        "state": state,
    }
    return f"{FB_AUTH_URL}?{urllib.parse.urlencode(params)}"


def start_oauth_flow(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    port: int = 8765,
    open_browser: bool = True,
) -> dict:
    """Run the full OAuth flow end-to-end.

    1. Open browser to Facebook consent screen
    2. Listen on localhost for the callback
    3. Exchange code → short-lived token
    4. Exchange short-lived → long-lived token
    5. Discover the user's Instagram Business Account ID
    6. Save everything to config.ini

    Returns:
        dict with keys: access_token, ig_account_id, fb_user_id
    """
    global _CALLBACK_CODE, _CALLBACK_ERROR, _CALLBACK_EVENT

    app_id = app_id or get_fb_app_id()
    app_secret = app_secret or get_fb_app_secret()

    if not app_id or not app_secret:
        raise SystemExit(
            "ERROR: FB_APP_ID and FB_APP_SECRET are required.\n"
            "Set them in config.ini, .env, or environment variables.\n"
            f"Config file: {CONFIG_FILE}"
        )

    redirect_uri = f"http://localhost:{port}/"
    auth_url = generate_auth_url(app_id, redirect_uri)

    # ── Start local server ──────────────────────────────────────────
    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server.timeout = 120  # 2-minute timeout

    print(f"\n🔑 Starting Instagram OAuth flow...\n")
    print(f"  If your browser doesn't open, visit:\n")
    print(f"  {auth_url}\n")
    print(f"  Listening for callback on http://localhost:{port} ...\n")

    if open_browser:
        webbrowser.open(auth_url)

    # Reset callback state
    _CALLBACK_CODE = None
    _CALLBACK_ERROR = None
    _CALLBACK_EVENT = threading.Event()

    # ── Wait for callback ───────────────────────────────────────────
    _CALLBACK_EVENT.wait(timeout=120)
    server.server_close()

    if _CALLBACK_ERROR:
        raise SystemExit(f"OAuth error: {_CALLBACK_ERROR}")

    if not _CALLBACK_CODE:
        raise SystemExit("OAuth flow timed out — no code received within 120s.")

    print("  ✅ Authorization code received. Exchanging for token...")

    # ── Exchange code → short-lived token ───────────────────────────
    short_token = _exchange_code_for_token(app_id, app_secret, _CALLBACK_CODE, redirect_uri)

    # ── Exchange short-lived → long-lived token ────────────────────
    long_token = _exchange_for_long_lived_token(app_id, app_secret, short_token)

    # ── Discover Instagram Business Account ID ──────────────────────
    ig_account_id = _discover_ig_account_id(long_token)

    # ── Persist to config.ini ───────────────────────────────────────
    save_token_to_config("IG_ACCESS_TOKEN", long_token)
    save_token_to_config("IG_ACCOUNT_ID", ig_account_id)

    print(f"\n✅ Tokens saved to {CONFIG_FILE}")
    print(f"   IG_ACCESS_TOKEN = {long_token[:12]}...")
    print(f"   IG_ACCOUNT_ID  = {ig_account_id}\n")

    return {
        "access_token": long_token,
        "ig_account_id": ig_account_id,
    }


def refresh_long_lived_token(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    current_token: Optional[str] = None,
) -> str:
    """Refresh a long-lived token (valid for 60 days, refresh before expiry).

    Returns:
        The new long-lived access token.
    """
    from instagram_agent.config import get

    app_id = app_id or get_fb_app_id() or get("FB_APP_ID")
    app_secret = app_secret or get_fb_app_secret() or get("FB_APP_SECRET")
    current_token = current_token or get_ig_access_token_static()

    if not all([app_id, app_secret, current_token]):
        raise SystemExit(
            "ERROR: FB_APP_ID, FB_APP_SECRET, and IG_ACCESS_TOKEN are required to refresh."
        )

    resp = requests.get(
        FB_TOKEN_URL,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": current_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    new_token = data["access_token"]
    save_token_to_config("IG_ACCESS_TOKEN", new_token)

    print(f"✅ Token refreshed and saved to {CONFIG_FILE}")
    return new_token


def get_ig_access_token_static() -> Optional[str]:
    """Import-free helper to get the current IG token (used by refresh)."""
    from instagram_agent.config import get
    return get("IG_ACCESS_TOKEN")


# ── Internal helpers ────────────────────────────────────────────────────


def _exchange_code_for_token(
    app_id: str, app_secret: str, code: str, redirect_uri: str
) -> str:
    """Exchange an authorization code for a short-lived user access token."""
    resp = requests.get(
        FB_TOKEN_URL,
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise SystemExit(f"Token exchange error: {data['error'].get('message', data['error'])}")

    return data["access_token"]


def _exchange_for_long_lived_token(app_id: str, app_secret: str, short_token: str) -> str:
    """Exchange a short-lived token for a long-lived token (60-day validity)."""
    resp = requests.get(
        FB_TOKEN_URL,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise SystemExit(f"Long-lived token error: {data['error'].get('message', data['error'])}")

    return data["access_token"]


def _discover_ig_account_id(access_token: str) -> str:
    """Discover the Instagram Business Account ID from the user's Pages.

    The Instagram Graph API requires the IG Business Account ID (not the FB
    Page ID). We get it by listing the user's Pages, then looking up the
    IG Business Account for each Page.
    """
    # 1. Get user's pages
    resp = requests.get(
        f"{FB_GRAPH_URL}/me/accounts",
        params={
            "access_token": access_token,
            "fields": "id,access_token,name",
        },
    )
    resp.raise_for_status()
    pages = resp.json().get("data", [])

    if not pages:
        raise SystemExit(
            "No Facebook Pages found. You need a Facebook Page linked to an "
            "Instagram Business/Creator account.\n"
            "See: https://developers.facebook.com/docs/instagram-platform/getting-started"
        )

    # 2. For each page, try to find the linked IG Business Account
    for page in pages:
        page_token = page.get("access_token", access_token)
        ig_resp = requests.get(
            f"{FB_GRAPH_URL}/{page['id']}",
            params={
                "fields": "instagram_business_account",
                "access_token": page_token,
            },
        )
        ig_resp.raise_for_status()
        ig_data = ig_resp.json()

        if "instagram_business_account" in ig_data:
            ig_id = ig_data["instagram_business_account"]["id"]

            # Store the page token too — it's needed for some operations
            save_token_to_config("IG_PAGE_TOKEN", page_token)

            # Verify we can query the account
            verify = requests.get(
                f"{FB_GRAPH_URL}/{ig_id}",
                params={
                    "fields": "id,username,name",
                    "access_token": access_token,
                },
            )
            verify.raise_for_status()
            info = verify.json()

            print(f"  📸 Found Instagram account: @{info.get('username', ig_id)} (ID: {ig_id})")
            return ig_id

    raise SystemExit(
        "No Instagram Business/Creator account linked to your Facebook Pages.\n"
        "Convert your Instagram to a Business/Creator account and link it to a Page.\n"
        "See: https://help.instagram.com/502981923235522"
    )
