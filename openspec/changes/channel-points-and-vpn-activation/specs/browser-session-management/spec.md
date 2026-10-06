## MODIFIED Requirements

### Requirement: Post-launch VPN activation hook
After `launch_sessions()` completes and all subprocess browser windows are open, the system SHALL call `browser_sessions.activate_vpns()` to run the VPN activation phase. This phase is separate from the subprocess launch and uses a temporary Playwright headless context per Chromium-family browser.

#### Scenario: VPN activation runs after all browsers open
- **WHEN** `BROWSER_SESSIONS_ENABLED=true` and `main.py` starts
- **THEN** `launch_sessions()` opens all browser windows first, then `activate_vpns()` runs sequentially per browser slot before the bot begins listening

#### Scenario: VPN activation failure does not block startup
- **WHEN** `activate_vpns()` encounters an error on any browser slot
- **THEN** the error is logged and startup continues — bots connect and begin listening regardless

### Requirement: Browser session toggle
The system SHALL support a `BROWSER_SESSIONS_ENABLED` environment variable. When set to `true`, the system SHALL launch and manage persistent browser sessions for each bot account, then run VPN activation. When `false` or unset, the system SHALL skip all browser session logic entirely.

#### Scenario: Sessions disabled by default
- **WHEN** `BROWSER_SESSIONS_ENABLED` is not set in `.env`
- **THEN** the bot starts without launching any browsers or running VPN activation

#### Scenario: Sessions enabled at startup
- **WHEN** `BROWSER_SESSIONS_ENABLED=true` and `main.py` starts
- **THEN** the system launches one browser window per token in `TWITCH_TOKENS`, runs VPN activation, then the bot begins listening
