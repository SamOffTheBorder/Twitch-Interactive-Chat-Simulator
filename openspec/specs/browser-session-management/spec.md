# Spec: Browser Session Management

## Purpose

Manages persistent browser sessions for bot accounts using Playwright. Each account is assigned a browser type via a fixed cycle, sessions are stored on disk for login persistence between runs, and all sessions are closed cleanly on shutdown.

## Requirements

### Requirement: Browser session toggle
The system SHALL support a `BROWSER_SESSIONS_ENABLED` environment variable. When set to `true`, the system SHALL launch and manage persistent browser sessions for each bot account. When `false` or unset, the system SHALL skip all browser session logic entirely.

#### Scenario: Sessions disabled by default
- **WHEN** `BROWSER_SESSIONS_ENABLED` is not set in `.env`
- **THEN** the bot starts without launching any browsers

#### Scenario: Sessions enabled at startup
- **WHEN** `BROWSER_SESSIONS_ENABLED=true` and `main.py` starts
- **THEN** the system launches one browser window per token in `TWITCH_TOKENS` before the bot begins listening

### Requirement: Multi-browser cycling
The system SHALL distribute bot accounts across browser types in a fixed cycle: Chromium, Firefox, WebKit, Chrome (system), Edge (system). Each bot account at index `i` SHALL use browser type `BROWSER_CYCLE[i % len(BROWSER_CYCLE)]`.

#### Scenario: Five or fewer accounts
- **WHEN** there are 5 or fewer tokens in `TWITCH_TOKENS`
- **THEN** each account uses a distinct browser type with no repetition

#### Scenario: More accounts than browser types
- **WHEN** there are more than 5 tokens
- **THEN** the cycle repeats from the beginning (account 5 uses Chromium, account 6 uses Firefox, etc.)

#### Scenario: System browser not installed
- **WHEN** Chrome or Edge is selected by the cycle but is not installed on the machine
- **THEN** the system SHALL fall back to Chromium for that account and print a warning

### Requirement: Persistent browser profiles
The system SHALL use Playwright `launch_persistent_context` for each account, storing the profile under `sessions/<index>/`. Login state SHALL persist between runs without requiring re-authentication.

#### Scenario: First run with no saved session
- **WHEN** `setup_sessions.py` is run and no session exists at `sessions/<index>/`
- **THEN** the browser opens headed, navigates to `https://www.twitch.tv/login`, and waits for the user to log in

#### Scenario: Subsequent runs with saved session
- **WHEN** `main.py` starts with `BROWSER_SESSIONS_ENABLED=true` and a session exists at `sessions/<index>/`
- **THEN** the browser window opens headed and the account is already logged in with no user action required

#### Scenario: Session folder gitignored
- **WHEN** `sessions/` exists
- **THEN** it SHALL NOT be committed to git (already covered by `.gitignore`)

### Requirement: Graceful shutdown
The system SHALL close all browser contexts cleanly when the bot stops via the `stop` command, `restart` command, or `KeyboardInterrupt`.

#### Scenario: Stop command issued
- **WHEN** user types `stop` in the terminal
- **THEN** all browser contexts are closed before the process exits

#### Scenario: Keyboard interrupt
- **WHEN** user presses Ctrl+C
- **THEN** all browser contexts are closed before the process exits

### Requirement: Setup script for first-time login
The system SHALL provide `setup_sessions.py` as a standalone script for one-time browser login setup. It SHALL open each browser in turn, navigate to Twitch login, detect successful login, confirm to the user, and save the session automatically.

#### Scenario: Successful login detected
- **WHEN** the user completes login in the browser window opened by `setup_sessions.py`
- **THEN** the script prints "Session saved for account <index>" and closes that browser before opening the next

#### Scenario: Login timeout
- **WHEN** the user does not complete login within 3 minutes
- **THEN** the script prints a warning and moves to the next account
