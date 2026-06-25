## 1. Config & Environment

- [x] 1.1 Add `BROWSER_SESSIONS_ENABLED = os.getenv("BROWSER_SESSIONS_ENABLED", "false").lower() == "true"` to `config.py`
- [x] 1.2 Add `BROWSER_SESSIONS_ENABLED=false` to `.env.example` with a comment explaining the feature

## 2. Core Browser Session Manager (`browser_sessions.py`)

- [x] 2.1 Create `browser_sessions.py` with `BROWSER_CYCLE = ["chromium", "firefox", "webkit", "chrome", "msedge"]`
- [x] 2.2 Implement `_pick_browser(index)` — returns `(browser_type_name, channel_or_none)` for position `index % len(BROWSER_CYCLE)`
- [x] 2.3 Implement `_launch_context(pw, index, token)` — calls `launch_persistent_context(f"sessions/{index}", headless=False, ...)` with fallback to Chromium if system browser not found
- [x] 2.4 Implement `launch_sessions(tokens)` — loops tokens, calls `_launch_context` per account, stores contexts in module-level list, prints which browser opened for each account
- [x] 2.5 Implement `close_all()` — closes all stored contexts cleanly
- [x] 2.6 Implement `get_status()` — returns list of dicts with `index`, `browser_type`, `vpn_name`, `vpn_status` for each context (used by `diag`)

## 3. VPN Extension Activation (`browser_sessions.py`)

- [x] 3.1 Add hardcoded `_VPN_EXTENSIONS` lookup table mapping VPN name → `{chrome_id, firefox_id, connect_selector}` for ProtonVPN, NordVPN, ExpressVPN, Windscribe
- [x] 3.2 Implement `_detect_vpn(context, browser_type)` — iterates known extension IDs, tries to navigate to `chrome-extension://<id>/popup.html` (or `moz-extension://` for Firefox), returns `(vpn_name, extension_url)` or `(None, None)`. Skip entirely for WebKit.
- [x] 3.3 Implement `_activate_vpn(context, vpn_name, popup_url)` — navigates to popup, checks for connected state, clicks Connect if not connected, waits up to 15s for connected state, returns `"connected" | "already_connected" | "timeout" | "error"`
- [x] 3.4 Wire VPN detection + activation into `_launch_context` after the context is loaded — store result in per-context status dict

## 4. First-Time Setup Script (`setup_sessions.py`)

- [x] 4.1 Create `setup_sessions.py` as a standalone script (not imported by `main.py`)
- [x] 4.2 For each token index: launch headed persistent context (same profile path as runtime), navigate to `https://www.twitch.tv/login`
- [x] 4.3 Poll for successful login by checking for presence of `[data-a-target="user-menu-toggle"]` element or URL no longer being `/login`
- [x] 4.4 On login detected: print "Session saved for account <index> (<browser_type>)" and close context; move to next account
- [x] 4.5 On 3-minute timeout: print warning, close context, move to next account

## 5. Wire into `main.py`

- [x] 5.1 Import `browser_sessions` at top of `main.py` (inside `if config.BROWSER_SESSIONS_ENABLED` guard to avoid import if disabled)
- [x] 5.2 In `main()`, after `config.validate()`, call `browser_sessions.launch_sessions(config.TWITCH_TOKENS)` if `BROWSER_SESSIONS_ENABLED`
- [x] 5.3 Add `browser_sessions.close_all()` to the `stop` and `restart` command branches in `_command_loop`
- [x] 5.4 Add `browser_sessions.close_all()` to the `KeyboardInterrupt` handler in `__main__`

## 6. Diagnostics Integration

- [x] 6.1 In `_print_diag`, if `config.BROWSER_SESSIONS_ENABLED`, call `browser_sessions.get_status()` and print one line per browser: `Browser <index> [<type>]: VPN=<name|none>, status=<status>`

## 7. Docusaurus Documentation

- [x] 7.1 Create `docs/docs/browser-sessions.md` covering: what the feature does, prerequisites (Playwright install for each browser type), first-time setup with `setup_sessions.py`, `BROWSER_SESSIONS_ENABLED` config, browser cycle table, VPN extension setup (links to Chrome Web Store for each), VPN activation behavior, session expiry and re-setup, WebKit VPN limitation note
- [x] 7.2 Add `browser-sessions` to the Docusaurus sidebar (check `docs/sidebars.ts` or auto-discovery config)
