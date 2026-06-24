import json
import threading
import time
import urllib.parse
import urllib.request

import config


def _fetch_app_token() -> str:
    """Client Credentials flow — no user login needed, just Client-ID + Secret."""
    if not config.TWITCH_CLIENT_ID or not config.TWITCH_CLIENT_SECRET:
        return ""
    try:
        body = urllib.parse.urlencode({
            "client_id": config.TWITCH_CLIENT_ID,
            "client_secret": config.TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }).encode()
        req = urllib.request.Request(
            "https://id.twitch.tv/oauth2/token",
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        token = data.get("access_token", "")
        if token:
            print("[StreamInfo] App access token obtained")
        return token
    except Exception as e:
        print(f"[StreamInfo] Could not get app token: {e}")
        return ""


class StreamInfo:
    def __init__(self):
        self.title = ""
        self.category = ""
        self.streamer = config.TWITCH_CHANNEL
        self.viewer_count = 0
        self._lock = threading.Lock()
        self._app_token = ""

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def snapshot(self) -> dict:
        with self._lock:
            return {"title": self.title, "category": self.category, "streamer": self.streamer, "viewer_count": self.viewer_count}

    def _run(self):
        self._app_token = _fetch_app_token()
        while True:
            self._fetch()
            time.sleep(300)

    def _fetch(self):
        if not self._app_token or not config.TWITCH_CLIENT_ID:
            return
        try:
            req = urllib.request.Request(
                f"https://api.twitch.tv/helix/streams?user_login={config.TWITCH_CHANNEL}",
                headers={
                    "Authorization": f"Bearer {self._app_token}",
                    "Client-Id": config.TWITCH_CLIENT_ID,
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            streams = data.get("data", [])
            if streams:
                with self._lock:
                    self.title = streams[0].get("title", "")
                    self.category = streams[0].get("game_name", "")
                    self.viewer_count = streams[0].get("viewer_count", 0)
                print(f"[StreamInfo] {self.category!r} — {self.title!r} ({self.viewer_count} viewers)")
            else:
                print("[StreamInfo] Channel offline — no stream data")
        except Exception as e:
            print(f"[StreamInfo] Fetch failed: {e}")
