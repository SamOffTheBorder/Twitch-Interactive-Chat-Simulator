## MODIFIED Requirements

### Requirement: VPN extension detection
After loading each persistent browser context, the system SHALL scan the browser's installed extensions for known VPN extensions by checking for known Chromium extension ID folders under `sessions/<index>/Default/Extensions/`. Supported VPNs SHALL include: ProtonVPN, NordVPN, ExpressVPN, and Windscribe. Detection SHALL only run for Chromium-family browsers (Brave, Chrome, Edge, Opera, Vivaldi); Firefox browser slots SHALL be skipped.

#### Scenario: Known VPN extension present
- **WHEN** a browser context is loaded and a known VPN extension folder is found under the profile's Extensions directory
- **THEN** the system SHALL print "[BrowserSessions] VPN detected: <name> in browser <index>" and proceed to activation

#### Scenario: No VPN extension present
- **WHEN** a browser context is loaded and no known VPN extension folder is found
- **THEN** the system SHALL print "[BrowserSessions] No VPN extension found for browser <index> — skipping" and continue without error

#### Scenario: Firefox browser slot
- **WHEN** the browser at index `i` is Firefox
- **THEN** the system SHALL print "[BrowserSessions] VPN activation skipped for browser <index> (Firefox not supported)" and continue

### Requirement: VPN extension activation
After detecting a VPN extension, the system SHALL launch a temporary headless Playwright Chromium context pointed at the same profile directory, navigate to the extension's popup URL (`chrome-extension://<id>/popup.html`), and attempt to activate the VPN if it is not already connected.

#### Scenario: VPN already connected
- **WHEN** the VPN extension popup shows a connected state
- **THEN** the system SHALL skip clicking Connect and print "[BrowserSessions] VPN already active for browser <index>"

#### Scenario: VPN not connected
- **WHEN** the VPN extension popup shows a disconnected state
- **THEN** the system SHALL click the Connect button and wait up to 15 seconds for the connected state to appear

#### Scenario: VPN activation timeout
- **WHEN** the VPN does not show a connected state within 15 seconds
- **THEN** the system SHALL print a warning and continue — VPN activation failure SHALL NOT prevent the browser session from being used

#### Scenario: Headless context exits after activation
- **WHEN** VPN activation completes (success, timeout, or skip)
- **THEN** the temporary headless Playwright context SHALL be closed before the next browser is processed

### Requirement: VPN activation is optional
VPN extension activation SHALL be entirely optional. If no VPN extensions are installed in any browser, the system SHALL operate normally. The feature SHALL degrade gracefully at every step.

#### Scenario: No VPN on any browser
- **WHEN** `BROWSER_SESSIONS_ENABLED=true` and no browsers have VPN extensions installed
- **THEN** the bot starts and operates identically to a run without VPN support

#### Scenario: VPN on some browsers only
- **WHEN** some browser contexts have VPN extensions and others do not
- **THEN** VPN activation runs only on the browsers where it is detected; others are unaffected

### Requirement: VPN status in diagnostics
The `diag` terminal command SHALL include VPN activation status per browser session when `BROWSER_SESSIONS_ENABLED=true`.

#### Scenario: Diag output with VPN
- **WHEN** user types `diag` and browser sessions are enabled
- **THEN** output includes a line per browser: "Browser <index> [<type>]: VPN=<name|none>, status=<connected|disconnected|unknown|skipped>"
