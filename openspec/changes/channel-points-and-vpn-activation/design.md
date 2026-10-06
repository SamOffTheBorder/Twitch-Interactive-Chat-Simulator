## Context

`rewards.py` already has `discover()` and `redeem()` — the GQL plumbing exists and works. The problem is:

1. `discover()` is never called on startup in `main.py`, so `TTS_REWARD_ID` stays blank unless manually set in `.env`, causing `redeem()` to return `False` immediately and fall through to regular chat.
2. When `redeem()` does fail, it only logs a short error. Callers in `tts_sender.py` and `responder.py` silently fall back to chat with no indication that the redemption is the part that failed.
3. VPN activation was spec'd for Playwright persistent contexts. That approach was abandoned because Twitch detects browser automation — we switched to `subprocess.Popen`, which opens browsers exactly like a user double-clicked them. VPN extension clicking needs a different path now.

## Goals / Non-Goals

**Goals:**
- Call `rewards.discover()` automatically in `main.py` before bots connect
- Print a clear startup summary: which reward IDs were resolved, which are still missing
- When `redeem()` fails, print the GQL error code or HTTP status so the user knows if it's a points/auth/reward issue — not a silent fallback
- Re-implement VPN activation using headless Playwright connecting to the running subprocess browser's remote debug port (or, if that's not feasible, connecting to the profile directly in a separate headed instance just for extension interaction)

**Non-Goals:**
- Changing the subprocess launch approach for main browser windows — that's working
- Supporting VPN extensions that don't have a clickable popup (silent/system-tray-only VPNs)
- Automatically earning channel points (users must have enough points already)
- Changing the GQL redemption API itself

## Decisions

### 1. Call `discover()` on startup, before bots connect

Wire `rewards.discover()` into `main.py` after `config.validate()` and `_ensure_ollama()`, before `ChatBot` instances are created. This ensures reward IDs are populated by the time the first TTS or highlight fires. `discover()` already prints what it found; add a post-discover summary log showing resolved IDs.

**Alternative considered:** Call discover lazily inside `_fire()`/`_do_highlight()` the first time they run. Rejected: adds lock complexity and the first fire could happen within seconds of startup.

### 2. Structured redemption error logging in `redeem()`

`redeem()` already prints errors but callers silently swallow them. The fix: `redeem()` already returns `bool` — callers need to log before falling back. In `tts_sender._fire()` and `responder._do_highlight()`, print a warning like `[TTS] Redemption failed — falling back to chat (reward_id=...)` before the fallback send. Also add token masking in the log (show only last 6 chars).

**Alternative considered:** Make `redeem()` raise on failure. Rejected: callers need the chat fallback path; bool return is cleaner.

### 3. VPN activation via Playwright connecting to browser's remote debug port

After `launch_sessions()` spawns subprocess browsers, `activate_vpns()` will:

1. Re-launch a **headless** Playwright Chromium context pointed at `--user-data-dir=sessions/<index>/` **for each Chromium-family browser** (Brave, Chrome, Edge, Opera, Vivaldi)
2. Open the VPN extension popup via `chrome-extension://<id>/popup.html`
3. Click Connect if not already connected, wait up to 15s for connected state
4. Close the headless context (does not affect the running subprocess window)

For **Firefox** profiles: skip VPN activation (Firefox extension APIs differ from Chromium's `chrome-extension://` popup URL scheme — not worth the complexity for an optional feature).

**Alternative considered:** `--remote-debugging-port` to attach to the running subprocess. Rejected on Windows: Brave/Chrome don't expose CDP unless launched with the flag; adding it would require relaunching browsers and complicates the subprocess approach.

**Why a separate headless context works:** Chromium profile directories support concurrent reads from multiple processes for most operations. Opening the extension popup in a temporary headless context while the user-facing subprocess window runs has been validated to work without corrupting the profile, as long as the headless context exits cleanly before the main window writes anything critical.

### 4. VPN extension IDs (Chromium)

Known Chromium extension IDs to detect:
- ProtonVPN: `jplgfhpmjnbigmhklmmbgecoobifkmpa`
- NordVPN: `fjoaledfpmneenckfbpdfhkmimnjocfa`  
- ExpressVPN: `fgddmllnllkalaagkghckoinaemmogpe`
- Windscribe: `hnmpcagpplmpfojmgmnngilcnanddlhb`

Detection: check if `sessions/<index>/Default/Extensions/<id>/` exists in the profile dir. If a folder matches, proceed to activation.

## Risks / Trade-offs

- **Profile concurrency** → Playwright headless + subprocess running simultaneously on same profile. Mitigation: headless context exits in <30s; main window hasn't had time to write conflicting data at launch.
- **VPN popup UI changes** → Connect button selector may break if VPN updates extension. Mitigation: use timeout + graceful skip; log clearly so user knows to update selectors.
- **Firefox skipped** → VPN won't auto-activate on Firefox browser slots. Mitigation: acceptable given complexity; documented in diag output ("VPN=skipped/Firefox").
- **Token in logs** → `rewards.redeem()` logs failures. Mitigation: mask token to last 6 chars in all log output.
- **Reward discovery fails** → Channel may have no rewards, or GQL is down. Mitigation: `discover()` already degrades gracefully; add explicit "TTS_REWARD_ID still blank — TTS will fall back to chat" warning after failed discovery.

## Migration Plan

1. Add `rewards.discover()` call in `main.py` (non-breaking — already exists, just not called)
2. Add fallback-logging in `tts_sender.py` and `responder.py` (non-breaking)
3. Add `activate_vpns()` to `browser_sessions.py` (new function, called after `launch_sessions()`)
4. No schema changes, no new environment variables required

## Open Questions

- Should `activate_vpns()` be guarded by a new env flag (e.g. `VPN_ACTIVATION_ENABLED`) or always run when `BROWSER_SESSIONS_ENABLED=true` and VPN extensions are detected? → **Decision**: always attempt when sessions are enabled; already gracefully skips when no VPN found. No new flag needed.
