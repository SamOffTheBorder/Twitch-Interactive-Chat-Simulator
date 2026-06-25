---
sidebar_position: 8
sidebar_label: Browser Sessions
---

# Browser Sessions (Optional)

When enabled, the bot opens one headed browser window per bot account — each in a different browser (Chrome, Firefox, Edge, etc.) — so you can visually monitor and test channel point redemptions. Sessions are saved locally so you only log in once.

## How it works

Each bot account gets its own persistent browser profile stored under `sessions/<index>/`. Playwright manages the profiles, so cookies and login state survive between runs. On startup, all browsers open automatically with your saved sessions.

A security phase runs after each browser loads: the bot detects installed VPN extensions (ProtonVPN, NordVPN, ExpressVPN, Windscribe) and activates them automatically before the session is used.

## Prerequisites

Install Playwright browsers (run once):

```bash
python -m playwright install chromium firefox webkit
```

For Chrome and Edge, the system-installed versions are used automatically — no extra install needed.

## Setup

### 1. First-time login

Run this once for each bot account:

```bash
python setup_sessions.py
```

A browser window opens per account. Log in to Twitch as that bot account — the script detects the login, saves the session, and moves to the next account. You have 3 minutes per account.

### 2. Enable the feature

In `.env`:

```
BROWSER_SESSIONS_ENABLED=true
```

### 3. Run the bot

```bash
python main.py
```

All browser windows open automatically. No login prompts.

## Browser Cycle

Each bot account is assigned a browser based on its position in `TWITCH_TOKENS`:

| Account # | Browser |
|---|---|
| 1 | Chromium (bundled) |
| 2 | Firefox (bundled) |
| 3 | WebKit (bundled) |
| 4 | Chrome (system) |
| 5 | Edge (system) |
| 6+ | Repeats from Chromium |

If Chrome or Edge is not installed, that slot falls back to bundled Chromium with a warning printed in the terminal.

## VPN Extension Support (Optional)

Install a supported VPN extension in one or more of your browsers. The bot detects and activates it automatically at startup.

| VPN | Install |
|---|---|
| ProtonVPN | [Chrome Web Store](https://chrome.google.com/webstore/detail/protonvpn/jplgfhpmjnbigmhklmmbgecoobifkmpa) |
| NordVPN | [Chrome Web Store](https://chrome.google.com/webstore/detail/nordvpn/fjoaledfpmneenckfbpdfhkmimnjocfa) |
| ExpressVPN | [Chrome Web Store](https://chrome.google.com/webstore/detail/expressvpn/fgddmllnllkalaagkghckoinaemmogpe) |
| Windscribe | [Chrome Web Store](https://chrome.google.com/webstore/detail/windscribe/hnmpcagpplmpfojmgmnngilcnanddlhb) |

VPN activation is best-effort — if it fails or times out (15s), the bot continues normally. Not all accounts need a VPN installed.

:::note WebKit limitation
WebKit does not support browser extensions. VPN activation is automatically skipped for the WebKit browser slot (account 3, or wherever it falls in the cycle).
:::

## Diagnostics

The `diag` terminal command shows browser and VPN status when sessions are enabled:

```
Browser 0 [chromium]: VPN=ProtonVPN, status=connected
Browser 1 [firefox]:  VPN=none,      status=—
Browser 2 [webkit]:   VPN=none,      status=—
Browser 3 [chrome]:   VPN=NordVPN,   status=connected
```

## Session expiry

Twitch sessions expire eventually. If a browser shows the login page on startup, re-run `setup_sessions.py` — it only re-logs in for accounts whose sessions have expired.

## Notes

- Sessions are stored in `sessions/` which is excluded from git
- If your project is on OneDrive, consider excluding `sessions/` from OneDrive sync — browser profiles can be large and cause sync conflicts
- Browsers are always headed (visible) — headless mode is not supported for this feature
