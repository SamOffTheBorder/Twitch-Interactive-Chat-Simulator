"""
Polls Twitch Helix API for stream metadata at a set interval and appends
each snapshot to a newline-delimited JSON file for research analysis.
"""

import asyncio
import datetime
import json
import aiohttp

import config

_HELIX_STREAMS_URL = "https://api.twitch.tv/helix/streams"
_OUTPUT_FILE = "stream_data.jsonl"
_POLL_INTERVAL_SECONDS = 60


async def _fetch_stream_snapshots(session: aiohttp.ClientSession) -> list[dict]:
    headers = {
        "Client-ID": config.TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {config.TWITCH_ACCESS_TOKEN}",
    }
    params = [("user_login", ch) for ch in config.TWITCH_CHANNELS]
    async with session.get(_HELIX_STREAMS_URL, headers=headers, params=params) as resp:
        if resp.status != 200:
            print(f"[DataCollector] Helix API error {resp.status}")
            return []
        body = await resp.json()
        return body.get("data", [])


def _save_snapshots(snapshots: list[dict]):
    now = datetime.datetime.utcnow().isoformat()
    with open(_OUTPUT_FILE, "a", encoding="utf-8") as f:
        for stream in snapshots:
            record = {
                "collected_at": now,
                "channel": stream.get("user_login"),
                "title": stream.get("title"),
                "game": stream.get("game_name"),
                "viewer_count": stream.get("viewer_count"),
                "started_at": stream.get("started_at"),
                "language": stream.get("language"),
                "is_mature": stream.get("is_mature"),
            }
            f.write(json.dumps(record) + "\n")


async def run_collector():
    """Runs forever, polling Twitch every POLL_INTERVAL_SECONDS."""
    print(f"[DataCollector] Starting — polling every {_POLL_INTERVAL_SECONDS}s")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                snapshots = await _fetch_stream_snapshots(session)
                if snapshots:
                    _save_snapshots(snapshots)
                    channels = [s.get("user_login") for s in snapshots]
                    viewers = sum(s.get("viewer_count", 0) for s in snapshots)
                    print(
                        f"[DataCollector] Recorded {len(snapshots)} stream(s) "
                        f"({channels}) — {viewers} total viewers"
                    )
                else:
                    print("[DataCollector] No live streams found for tracked channels.")
            except Exception as exc:
                print(f"[DataCollector] Error: {exc}")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
