#!/usr/bin/env python3
"""One-time OAuth 2.0 PKCE setup for X API access.

This script guides you through authorizing jarvis to access your X bookmarks.

Usage:
    python scripts/setup_x_oauth.py

Prerequisites:
    1. Create an X app at https://developer.x.com
    2. Set callback URL to http://127.0.0.1:8080/callback
    3. Set X_CLIENT_ID and X_CLIENT_SECRET in .env
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import sys
import time
import webbrowser
from contextlib import suppress
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.config import get_settings
from jarvis.database import Database

CALLBACK_PORT = 8080
CALLBACK_HOST = "127.0.0.1"
REQUIRED_SCOPES = "bookmark.read tweet.read users.read offline.access"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from X."""

    auth_code: str | None = None
    error: str | None = None
    callback_received: bool = False

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return

        query = parse_qs(parsed.query)

        if "error" in query:
            OAuthCallbackHandler.error = query["error"][0]
            self._send_response("Authorization failed. Check console for details.")
            OAuthCallbackHandler.callback_received = True
            return

        if "code" not in query:
            self.send_error(400, "Missing authorization code")
            return

        OAuthCallbackHandler.auth_code = query["code"][0]
        self._send_response("Authorization successful! You can close this window.")
        OAuthCallbackHandler.callback_received = True

    def _send_response(self, message: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Callback</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h2>{message}</h2>
            <p>You can close this window.</p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge.

    Returns:
        Tuple of (code_verifier, code_challenge).
    """
    code_verifier = secrets.token_urlsafe(64)
    if len(code_verifier) > 128:
        code_verifier = code_verifier[:128]

    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

    return code_verifier, code_challenge


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    """Build X OAuth authorization URL.

    Args:
        client_id: OAuth client ID.
        redirect_uri: Callback URL.
        code_challenge: PKCE code challenge.
        state: Random state string.

    Returns:
        Authorization URL.
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": REQUIRED_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://x.com/i/oauth2/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    """Exchange authorization code for access tokens.

    Args:
        client_id: OAuth client ID.
        client_secret: OAuth client secret.
        code: Authorization code.
        redirect_uri: Callback URL.
        code_verifier: PKCE code verifier.

    Returns:
        Token response dictionary.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.x.com/2/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def wait_for_callback(server: HTTPServer, timeout: int = 300) -> bool:
    """Wait for OAuth callback.

    Args:
        server: HTTP server instance.
        timeout: Timeout in seconds.

    Returns:
        True if callback received, False on timeout.
    """
    start = time.time()
    while not OAuthCallbackHandler.callback_received:
        if time.time() - start > timeout:
            return False
        with suppress(Exception):
            server.handle_request()
    return True


def main() -> int:
    print("=" * 60)
    print("X OAuth 2.0 Setup for Jarvis")
    print("=" * 60)
    print()

    try:
        settings = get_settings()
    except Exception as e:
        print(f"ERROR: Failed to load settings: {e}")
        print("Make sure you have a valid .env file with required settings.")
        return 1

    if not settings.x_client_id:
        print("ERROR: X_CLIENT_ID not set in .env")
        print("Get your Client ID from https://developer.x.com console")
        return 1

    if not settings.x_client_secret:
        print("ERROR: X_CLIENT_SECRET not set in .env")
        print("Get your Client Secret from https://developer.x.com console")
        return 1

    redirect_uri = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/callback"

    print(f"Client ID: {settings.x_client_id[:10]}...")
    print(f"Callback URL: {redirect_uri}")
    print(f"Required scopes: {REQUIRED_SCOPES}")
    print()

    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(16)

    auth_url = build_auth_url(
        settings.x_client_id,
        redirect_uri,
        code_challenge,
        state,
    )

    server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), OAuthCallbackHandler)
    print(f"Starting callback server on {CALLBACK_HOST}:{CALLBACK_PORT}...")

    print()
    print("Opening browser for authorization...")
    print("If browser doesn't open, visit this URL:")
    print(auth_url)
    print()

    with suppress(Exception):
        webbrowser.open(auth_url)

    print("Waiting for authorization (timeout: 5 minutes)...")
    if not wait_for_callback(server, timeout=300):
        print("ERROR: Timeout waiting for authorization")
        return 1

    if OAuthCallbackHandler.error:
        print(f"ERROR: Authorization failed: {OAuthCallbackHandler.error}")
        return 1

    if not OAuthCallbackHandler.auth_code:
        print("ERROR: No authorization code received")
        return 1

    print()
    print("Authorization code received. Exchanging for tokens...")

    try:
        tokens = asyncio.run(
            exchange_code_for_tokens(
                settings.x_client_id,
                settings.x_client_secret,
                OAuthCallbackHandler.auth_code,
                redirect_uri,
                code_verifier,
            )
        )
    except Exception as e:
        print(f"ERROR: Failed to exchange code for tokens: {e}")
        return 1

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens["expires_in"]
    scope = tokens.get("scope", REQUIRED_SCOPES)

    expires_at = datetime.now(UTC).timestamp() + expires_in
    expires_at_iso = datetime.fromtimestamp(expires_at, tz=UTC).isoformat()

    print(f"Access token received (expires in {expires_in}s)")
    if refresh_token:
        print("Refresh token received (long-term access enabled)")
    print()

    db = Database(settings.database_path)

    if not refresh_token:
        print("WARNING: No refresh token received. offline.access scope may not be granted.")
        print("Tokens will expire and you'll need to re-authorize.")
        refresh_token = "NO_REFRESH_TOKEN"

    db.save_oauth_tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at_iso,
        scope=scope,
    )

    print("Tokens saved to database successfully!")
    print()
    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print()
    print("You can now:")
    print("  1. Start jarvis with: python -m jarvis")
    print("  2. Or run manual sync with:")
    print('     python -c "import asyncio; from jarvis.config import get_settings; \\')
    print('     from jarvis.database import Database; from jarvis.bookmarks.sync import BookmarkSync; \\')
    print('     s = get_settings(); db = Database(s.database_path); \\')
    print('     sync = BookmarkSync(db, s.x_client_id, s.x_client_secret); \\')
    print('     print(asyncio.run(sync.sync_bookmarks(full_sync=True)))"')
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
