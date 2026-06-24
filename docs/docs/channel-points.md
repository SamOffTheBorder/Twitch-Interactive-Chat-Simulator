---
sidebar_position: 7
---

# Channel Points (Optional)

Bot accounts can redeem your channel point rewards (TTS, Highlight My Message) using persistent browser sessions. This is optional — without it, everything falls back to regular chat messages.

## How it works

Each bot account has a saved Chromium browser session stored locally. At runtime the sessions load headlessly, extract a live auth token from browser storage, and use it to call Twitch's internal redemption API directly.

Sessions are saved to `sessions/` which is excluded from git — they never leave your machine.

## Setup

Run once per bot account:

```bash
python setup_sessions.py
```

A browser window opens for each account. Log in as that bot account, then wait — the script detects the login automatically and saves the session. Repeat for all accounts.

After setup, sessions load automatically when you run `python main.py`.

## Reward matching

The bot discovers your reward IDs automatically at startup by matching reward titles:

| Reward | Title must contain |
|---|---|
| TTS | "text" + "speech" |
| Highlight | "highlight" |

You can also set `TTS_REWARD_ID` and `HIGHLIGHT_REWARD_ID` directly in `.env` to skip the lookup.

## Fallback behavior

If browser sessions aren't set up, or if a redemption fails, the bot sends the message as regular chat instead. The feature degrades gracefully.

## Session expiry

Browser sessions persist until the Twitch account is logged out in that browser profile or the account password changes. If redemptions stop working, re-run `python setup_sessions.py` for that account.
