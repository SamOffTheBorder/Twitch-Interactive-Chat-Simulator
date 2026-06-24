"""
One-time OAuth token generator for bot accounts.

Run this once per bot account:
    python token_gen.py

It opens your browser to Twitch's login page. Log in as the bot account,
approve the permissions, and the access token is printed here to copy into .env.

BEFORE RUNNING: add http://localhost:3000 as an OAuth Redirect URL in your
Twitch Developer Console at https://dev.twitch.tv/console/apps
"""
import http.server
import json
import threading
import urllib.parse
import urllib.request
import webbrowser

import config

_SCOPES = "chat:read+chat:edit+channel:read:redemptions"
_REDIRECT_URI = "http://localhost:3000"
_PORT = 3000

_captured_code: str = ""
_server_ready = threading.Event()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _captured_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _captured_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Token captured! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>No code found. Try again.</h2>")

    def log_message(self, format, *args):
        pass  # suppress request logs


def _exchange_code(code: str) -> str:
    body = urllib.parse.urlencode({
        "client_id": config.TWITCH_CLIENT_ID,
        "client_secret": config.TWITCH_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": _REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        "https://id.twitch.tv/oauth2/token",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data.get("access_token", "")


def main():
    if not config.TWITCH_CLIENT_ID or not config.TWITCH_CLIENT_SECRET:
        print("ERROR: TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET must be set in .env")
        return

    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?client_id={config.TWITCH_CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(_REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={_SCOPES}"
        f"&force_verify=true"
    )

    server = http.server.HTTPServer(("localhost", _PORT), _Handler)

    print("=" * 60)
    print("Twitch Bot Token Generator")
    print("=" * 60)
    print()
    print("1. Make sure http://localhost:3000 is added as an OAuth Redirect")
    print("   URL in your Twitch app at dev.twitch.tv/console/apps")
    print()
    print("2. A browser window will open. Log in as the BOT ACCOUNT")
    print("   (not your streamer account) and click Authorize.")
    print()
    print("3. The token will be printed here when done.")
    print()
    input("Press Enter to open the browser...")

    webbrowser.open(auth_url)
    print("Waiting for Twitch to redirect back...")

    server.handle_request()  # handles exactly one request then returns

    if not _captured_code:
        print("ERROR: No authorization code received. Did you complete the login?")
        return

    print("Authorization code received — exchanging for access token...")
    try:
        token = _exchange_code(_captured_code)
        if token:
            print()
            print("=" * 60)
            print("ACCESS TOKEN:")
            print(f"  {token}")
            print("=" * 60)
            print()
            print("Copy the token above and add it to TWITCH_TOKENS in .env")
            print("Run this script again (in a private/incognito window) for each bot account.")
        else:
            print("ERROR: Token exchange returned empty. Check your client_id and client_secret.")
    except Exception as e:
        print(f"ERROR exchanging code: {e}")


if __name__ == "__main__":
    main()
