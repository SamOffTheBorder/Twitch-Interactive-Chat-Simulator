## Context

The bot currently manages channel point redemptions via direct GQL API calls using each bot's OAuth token — no browsers involved. The README/docs reference Playwright browser sessions but this was never implemented. Previous manual testing showed that running all accounts through one Chromium instance caused session collisions and login conflicts.

The fix: give each bot account its own persistent browser profile stored under `sessions/<index>/`, spread across different browser engines so they are fully isolated. A security phase activates any VPN browser extensions found in each browser before the session is used.

Playwright is already listed as a dependency in `requirements.txt` and referenced in the README, so no new dependency approval is needed.

## Goals / Non-Goals

**Goals:**
- One isolated persistent browser context per bot account
- Browser types cycle across Chromium, Firefox, WebKit, Chrome (system), Edge (system)
- Login state persists — user logs in once via `setup_sessions.py`, never again unless session expires
- VPN extensions detected and activated automatically per browser (optional, degrades gracefully)
- `BROWSER_SESSIONS_ENABLED` toggle so the feature is off by default
- VPN status visible in `diag` output
- Docusaurus `browser-sessions.md` page documents the feature

**Non-Goals:**
- Assigning specific VPNs to specific accounts (detection is best-effort per what's installed)
- Supporting VPN extensions not in the known list (ProtonVPN, NordVPN, ExpressVPN, Windscribe)
- Replacing the existing GQL redemption path — browsers are for visual testing/monitoring only
- Headless mode — browsers open headed so the user can watch

## Decisions

### Decision: Playwright persistent contexts over regular browser launch
**Chosen**: `launch_persistent_context(user_data_dir, headless=False)`  
**Why**: Persistent contexts write cookies, localStorage, and IndexedDB back to disk automatically. Regular `launch()` + `new_context()` would require manual cookie serialization. Persistent contexts are the idiomatic Playwright pattern for saving login state.  
**Alternative considered**: Selenium with profile directories — rejected because Playwright is already the declared dependency and supports all five browser types with one API.

### Decision: Cycle order: Chromium → Firefox → WebKit → Chrome → Edge
**Chosen**: Fixed cycle in that order  
**Why**: Chromium, Firefox, and WebKit are Playwright-bundled and always available. Chrome and Edge require system installation, so they go last in the cycle — if only 3 accounts exist, no system browsers are required.  
**Alternative considered**: Random assignment — rejected because deterministic assignment makes debugging easier (account 0 is always Chromium, etc.).

### Decision: System browsers via Playwright `channel` parameter
**Chosen**: `chromium.launch_persistent_context(..., channel="chrome")` for Chrome, `channel="msedge"` for Edge  
**Why**: Playwright's channel param uses the system-installed browser binary but still manages the context. No need for separate WebDriver setup.  
**Fallback**: Try/except around channel-based launch; if `Error: browser not found` is raised, fall back to bundled Chromium.

### Decision: VPN activation via extension popup URL
**Chosen**: Navigate to `chrome-extension://<id>/popup.html` (or Firefox equivalent) and interact with the DOM  
**Why**: No VPN provider exposes a programmatic connect API. The popup is the only controllable surface.  
**Known VPN extension IDs** (hardcoded lookup table in `browser_sessions.py`):
| VPN | Chrome/Edge ID | Firefox Add-on |
|---|---|---|
| ProtonVPN | `jplgfhpmjnbigmhklmmbgecoobifkmpa` | `proton-vpn-firefox-extension` |
| NordVPN | `fjoaledfpmneenckfbpdfhkmimnjocfa` | `nordvpn` |
| ExpressVPN | `fgddmllnllkalaagkghckoinaemmogpe` | `expressvpn` |
| Windscribe | `hnmpcagpplmpfojmgmnngilcnanddlhb` | `windscribe` |

WebKit does not support browser extensions — skip VPN step for WebKit contexts.

### Decision: VPN failure is non-blocking
**Chosen**: Warn and continue if VPN activation times out or fails  
**Why**: The primary purpose of the browser sessions is visual testing. A VPN that doesn't connect shouldn't block the bot from starting.

### Decision: `browser_sessions.py` is a standalone module, not integrated into `rewards.py`
**Chosen**: New `browser_sessions.py` handles all browser lifecycle  
**Why**: Keeps `rewards.py` clean (GQL only). The browser module is optional and toggled separately.

## Risks / Trade-offs

- **VPN extension DOM changes** → VPN providers update their extension UIs. Mitigation: wrap each VPN's connect logic in its own function with a `try/except`; if DOM selectors break, that VPN silently skips.
- **WebKit has no extension support** → VPN activation always skipped for WebKit contexts. Documented in Docusaurus. Not a regression — WebKit is the third browser in the cycle and most users won't have 3+ accounts.
- **System browsers not installed** → Graceful fallback to Chromium printed as a warning. No crash.
- **Session expiry** → Twitch sessions do expire eventually. User re-runs `setup_sessions.py` for affected accounts. Documented.
- **`sessions/` on OneDrive** → User's project is on OneDrive. Large browser profiles may cause sync conflicts. Mitigation: note in docs that `sessions/` should be excluded from OneDrive sync or the repo moved off OneDrive.

## Open Questions

- Should `setup_sessions.py` run all accounts sequentially (one at a time) or in parallel? Sequential is safer for first-time users to avoid confusion about which window belongs to which account. Recommend sequential.
- Should the Docusaurus page also cover the VPN extension installation steps, or just the activation behavior? Recommend covering both — link to each VPN's Chrome Web Store page.
