## Why

Bot browser sessions were unreliable because all accounts shared the same Chromium instance, causing login conflicts and session collisions. Spreading sessions across different real browsers (Chrome, Firefox, Edge, Chromium, WebKit) with persistent profiles eliminates cross-session interference and lets each bot account operate independently — with optional VPN extension activation per browser for added separation and privacy.

## What Changes

- Add `BROWSER_SESSIONS_ENABLED` toggle to `.env` / `config.py`
- Add `BROWSER_VPN_EXTENSIONS` config listing which VPN extensions to activate per browser (optional)
- Create `browser_sessions.py` — runtime manager that launches one browser per bot account, cycling across browser types, using Playwright persistent contexts so login state persists between runs
- Create `setup_sessions.py` — one-time setup script: opens each browser headed, user logs in once, session saved automatically
- Security phase in `browser_sessions.py`: after loading each persistent context, detect installed VPN extensions and activate them before the session is used
- Wire `browser_sessions.py` into `main.py` startup/shutdown
- Add `browser-sessions.md` to Docusaurus docs site

## Capabilities

### New Capabilities
- `browser-session-management`: Launch and manage one Playwright persistent browser context per bot account, cycling across Chromium, Firefox, WebKit, Chrome (system), and Edge (system), with sessions stored under `sessions/<index>/`
- `vpn-extension-activation`: After loading each browser context, detect and activate known VPN browser extensions (ProtonVPN, NordVPN, ExpressVPN, Windscribe) before the session is used

### Modified Capabilities

## Impact

- **New files**: `browser_sessions.py`, `setup_sessions.py`
- **Modified files**: `config.py`, `.env.example`, `main.py`, `docs/docs/browser-sessions.md` (new), `docs/sidebars.ts` (if needed)
- **New dependency**: `playwright` (already in `requirements.txt` per README, needs `python -m playwright install` for Firefox/WebKit/Chromium bundles)
- **Optional system browsers**: Chrome and Edge must be installed on the user's machine; graceful fallback to Chromium if not found
- **Sessions folder**: `sessions/<index>/` stores persistent browser profiles (already gitignored)
