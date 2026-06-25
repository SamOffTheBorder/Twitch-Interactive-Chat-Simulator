"""
First-time browser session setup.

Opens each browser as a normal process (not automated), navigates to Twitch login,
and waits for you to log in manually. Sessions are saved to sessions/<index>/
so you only need to do this once per account.

Usage:
    python setup_sessions.py
"""
import os
import sys

import config
from browser_sessions import BROWSER_CYCLE, _find_executable, _playwright_chromium_exe

LOGIN_URL = "https://www.twitch.tv/login"


def setup_all(tokens: list[str]) -> None:
    print(f"[Setup] Setting up sessions for {len(tokens)} account(s)...\n")

    for i, _token in enumerate(tokens):
        name = BROWSER_CYCLE[i % len(BROWSER_CYCLE)].lower()
        profile_dir = os.path.abspath(os.path.join("sessions", str(i)))
        os.makedirs(profile_dir, exist_ok=True)

        if name == "firefox":
            exe = _find_executable("firefox")
            if not exe:
                print(f"[Setup] Firefox not found — falling back to Chromium for account {i}")
                name = "chromium"
            else:
                firefox_profile = os.path.join(profile_dir, "firefox-profile")
                os.makedirs(firefox_profile, exist_ok=True)
                import subprocess
                print(f"[Setup] Account {i} → Firefox  (profile: {profile_dir})")
                print(f"[Setup] Log in to Twitch as bot account #{i+1}, then press Enter here...")
                proc = subprocess.Popen([exe, "--profile", firefox_profile, "--no-remote", LOGIN_URL])
                input()
                proc.terminate()
                print(f"[Setup] ✓ Session saved for account {i} (firefox)\n")
                continue

        if name == "chromium":
            exe = _playwright_chromium_exe()
            if not exe:
                print(f"[Setup] Playwright Chromium not found — skipping account {i}")
                continue
        else:
            exe = _find_executable(name)
            if not exe:
                print(f"[Setup] {name} not found — falling back to Chromium for account {i}")
                exe = _playwright_chromium_exe()
                name = "chromium"
                if not exe:
                    print(f"[Setup] Chromium also not found — skipping account {i}")
                    continue

        import subprocess
        print(f"[Setup] Account {i} → {name}  (profile: {profile_dir})")
        print(f"[Setup] Log in to Twitch as bot account #{i+1}, then press Enter here...")
        proc = subprocess.Popen(
            [exe, f"--user-data-dir={profile_dir}", LOGIN_URL],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        input()
        proc.terminate()
        print(f"[Setup] ✓ Session saved for account {i} ({name})\n")

    print("[Setup] Done. Set BROWSER_SESSIONS_ENABLED=true in .env and run python main.py")


if __name__ == "__main__":
    config.validate()
    if not config.TWITCH_TOKENS:
        print("[Setup] No TWITCH_TOKENS found in .env")
    else:
        setup_all(config.TWITCH_TOKENS)
