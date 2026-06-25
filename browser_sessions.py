"""
Multi-browser session manager — launches real browsers as normal processes.

Each bot account gets its own browser window opened via subprocess (not Playwright),
so Twitch sees a completely normal browser with no automation fingerprints.
Sessions are stored under sessions/<index>/ so login state persists between runs.
"""
import os
import subprocess
import sys

import config

BROWSER_CYCLE = config.BROWSER_CYCLE

# Maps friendly names to their Windows registry exe name
_BROWSER_EXE_NAMES: dict[str, str] = {
    "brave":   "brave.exe",
    "opera":   "opera.exe",
    "operagx": "opera.exe",
    "vivaldi": "vivaldi.exe",
    "arc":     "arc.exe",
    "thorium": "thorium.exe",
    "chrome":  "chrome.exe",
    "msedge":  "msedge.exe",
}

# Fallback hardcoded paths if registry lookup fails
_FALLBACK_PATHS: dict[str, list[str]] = {
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "opera": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
    ],
    "vivaldi": [
        os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe"),
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "chromium": [],  # Playwright-bundled only, handled separately
}

# Module-level state
_processes: list[dict] = []  # each: {index, browser_type, process}


def _registry_lookup(exe_name: str) -> str | None:
    try:
        import winreg
        key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    path, _ = winreg.QueryValueEx(key, "")
                    if path and os.path.exists(path):
                        return path
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return None


def _find_executable(name: str) -> str | None:
    """Find browser exe via registry first, then fallback paths."""
    exe_name = _BROWSER_EXE_NAMES.get(name)
    if exe_name:
        path = _registry_lookup(exe_name)
        if path:
            return path
    for path in _FALLBACK_PATHS.get(name, []):
        if os.path.exists(path):
            return path
    return None


def _playwright_chromium_exe() -> str | None:
    """Find Playwright's bundled Chromium executable."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            return pw.chromium.executable_path
    except Exception:
        return None


def _launch_browser(index: int, url: str) -> dict | None:
    """Launch a browser as a normal subprocess for the given account index."""
    name = BROWSER_CYCLE[index % len(BROWSER_CYCLE)].lower()
    profile_dir = os.path.abspath(os.path.join("sessions", str(index)))
    os.makedirs(profile_dir, exist_ok=True)

    if name == "firefox":
        exe = _find_executable("firefox")
        if not exe:
            print(f"[BrowserSessions] Firefox not found — falling back to Chromium for account {index}")
            name = "chromium"
        else:
            firefox_profile = os.path.join(profile_dir, "firefox-profile")
            os.makedirs(firefox_profile, exist_ok=True)
            proc = subprocess.Popen([exe, "--profile", firefox_profile, "--no-remote", url])
            print(f"[BrowserSessions] Account {index} → Firefox")
            return {"index": index, "browser_type": "firefox", "process": proc}

    if name == "chromium":
        exe = _playwright_chromium_exe()
        if not exe:
            print(f"[BrowserSessions] Playwright Chromium not found for account {index} — skipping")
            return None
    else:
        exe = _find_executable(name)
        if not exe:
            print(f"[BrowserSessions] {name} not found — falling back to Chromium for account {index}")
            exe = _playwright_chromium_exe()
            name = "chromium"
            if not exe:
                print(f"[BrowserSessions] Chromium also not found — skipping account {index}")
                return None

    # All Chromium-family browsers use --user-data-dir
    proc = subprocess.Popen(
        [exe, f"--user-data-dir={profile_dir}", url],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    print(f"[BrowserSessions] Account {index} → {name}")
    return {"index": index, "browser_type": name, "process": proc}


def launch_sessions(tokens: list[str], url: str = "https://www.twitch.tv") -> None:
    """Launch one browser per token, opening to the given URL."""
    _processes.clear()
    for i in range(len(tokens)):
        try:
            entry = _launch_browser(i, url)
            if entry:
                _processes.append(entry)
        except Exception as e:
            print(f"[BrowserSessions] Failed to launch browser for account {i}: {e}")
    print(f"[BrowserSessions] {len(_processes)}/{len(tokens)} browser(s) running")


def close_all() -> None:
    """Terminate all browser processes."""
    for entry in _processes:
        try:
            entry["process"].terminate()
        except Exception:
            pass
    _processes.clear()
    print("[BrowserSessions] All browsers closed")


def get_status() -> list[dict]:
    """Return status list for diag output."""
    return [
        {
            "index": e["index"],
            "browser_type": e["browser_type"],
            "vpn_name": "none",
            "vpn_status": "—",
        }
        for e in _processes
    ]
