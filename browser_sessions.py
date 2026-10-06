"""
Multi-browser session manager — launches real browsers as normal processes.

Each bot account gets its own browser window opened via subprocess (not Playwright),
so Twitch sees a completely normal browser with no automation fingerprints.
Sessions are stored under sessions/<index>/ so login state persists between runs.

VPN activation runs BEFORE subprocess launch to avoid Chromium profile locking:
  1. Extension VPNs: Playwright opens the profile, navigates to the extension popup,
     clicks Connect, then closes. The connected state is saved in the profile.
  2. Built-in VPNs (Opera): Preferences JSON is patched before the subprocess starts.
"""
import json
import os
import subprocess
import sys

import config

BROWSER_CYCLE = config.BROWSER_CYCLE

# Chromium-family browsers (support --user-data-dir and extension activation)
_CHROMIUM_FAMILY = {
    "brave", "chrome", "msedge", "opera", "operagx",
    "vivaldi", "arc", "thorium", "chromium",
}

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
    "chromium": [],
}

# Known VPN extension IDs for Chromium-family browsers
_VPN_EXTENSIONS: dict[str, str] = {
    "ProtonVPN":  "jplgfhpmjnbigmhklmmbgecoobifkmpa",
    "NordVPN":    "fjoaledfpmneenckfbpdfhkmimnjocfa",
    "ExpressVPN": "fgddmllnllkalaagkghckoinaemmogpe",
    "Windscribe": "hnmpcagpplmpfojmgmnngilcnanddlhb",
    "TunnelBear": "omdakjcmkglenbhjadbccaookpfjihpa",
    "CyberGhost": "ffbkglfiilegbpioefageomalachnkjh",
    "Hola VPN":   "gkojfkhlekighikafcpjkiklfbnlmeio",
    "Browsec":    "omghfjlpggmjjaagoclmmobgdodcjboh",
}

# VPN-specific Playwright selectors: connect button and connected-state indicator
_VPN_SELECTORS: dict[str, dict[str, list[str]]] = {
    "ProtonVPN": {
        "connect":   ["button:has-text('Connect')", "button[data-testid='quickConnectButton']"],
        "connected": ["button:has-text('Disconnect')", ":text('Protected')", "[class*='connected']"],
    },
    "NordVPN": {
        "connect":   [".connection-button", "button:has-text('Quick connect')", "button:has-text('Connect')"],
        "connected": [".connection-button--disconnect", "[data-testid='disconnect-button']", "button:has-text('Disconnect')"],
    },
    "ExpressVPN": {
        "connect":   ["#powerBtn", "button:has-text('Connect')"],
        "connected": ["#powerBtn.connected", ".connected-label", "button:has-text('Disconnect')"],
    },
    "Windscribe": {
        "connect":   [".connect-button", "button:has-text('Connect')"],
        "connected": [".connection-status:has-text('Connected')", ".connect-button.connected", "button:has-text('Disconnect')"],
    },
    "TunnelBear": {
        "connect":   ["button:has-text('Connect')", ".tunnel-toggle"],
        "connected": ["button:has-text('Disconnect')", "[class*='connected']"],
    },
    "CyberGhost": {
        "connect":   ["button:has-text('Connect')", ".connect-btn"],
        "connected": ["button:has-text('Disconnect')", "[class*='connected']"],
    },
    "Hola VPN": {
        "connect":   ["button:has-text('Turn On')", "button:has-text('Connect')"],
        "connected": ["button:has-text('Turn Off')", "[class*='connected']"],
    },
    "Browsec": {
        "connect":   ["button:has-text('Protect me')", "button:has-text('Connect')"],
        "connected": ["button:has-text('Protected')", "[class*='connected']"],
    },
}

# Generic fallback selectors used when VPN-specific ones fail
_GENERIC_CONNECT = ["button:has-text('Connect')", "button:has-text('Quick Connect')", "button:has-text('Turn On')", "button:has-text('Protect')"]
_GENERIC_CONNECTED = ["button:has-text('Disconnect')", "button:has-text('Turn Off')", "[class*='connected']", "[aria-label*='connected' i]"]

# Browsers with free built-in VPN — dot-separated Preferences key paths to set
_BUILTIN_VPN_PREFS: dict[str, dict[str, object]] = {
    "opera":   {
        "browser.vpn_popup.enabled": True,
        "opera.feature_vpn": True,
    },
    "operagx": {
        "browser.vpn_popup.enabled": True,
        "opera.feature_vpn": True,
    },
    # Vivaldi built-in VPN (free, enabled via Vivaldi settings panel)
    # Preference keys follow Vivaldi's Chromium-based storage layout
    "vivaldi": {
        "vivaldi.vpn.enabled": True,
        "vivaldi.vpn.auto_connect": True,
    },
}

# Module-level state
_processes: list[dict] = []
_vpn_states: dict[int, dict] = {}  # index → {name, status}


# ── Registry / path helpers ──────────────────────────────────────────────────

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
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            return pw.chromium.executable_path
    except Exception:
        return None


# ── VPN detection ────────────────────────────────────────────────────────────

def _detect_vpn_extension(profile_dir: str) -> tuple[str, str] | None:
    """Check profile's Extensions dir for any known VPN extension. Returns (name, id) or None."""
    ext_dir = os.path.join(profile_dir, "Default", "Extensions")
    if not os.path.isdir(ext_dir):
        return None
    for vpn_name, ext_id in _VPN_EXTENSIONS.items():
        if os.path.isdir(os.path.join(ext_dir, ext_id)):
            return (vpn_name, ext_id)
    return None


def _has_builtin_vpn(browser_name: str) -> bool:
    return browser_name in _BUILTIN_VPN_PREFS and bool(_BUILTIN_VPN_PREFS[browser_name])


# ── VPN activation ───────────────────────────────────────────────────────────

def _patch_preferences(profile_dir: str, key_paths: dict[str, object]) -> bool:
    """Write dot-separated keys into the Chromium Preferences JSON file."""
    pref_file = os.path.join(profile_dir, "Default", "Preferences")
    if not os.path.exists(pref_file):
        return False
    try:
        with open(pref_file, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        for key_path, value in key_paths.items():
            node = prefs
            keys = key_path.split(".")
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = value
        with open(pref_file, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
        return True
    except Exception as e:
        print(f"[BrowserSessions] Preferences patch failed: {e}")
        return False


def _click_vpn_popup(profile_dir: str, vpn_name: str, ext_id: str, browser_name: str = "") -> str:
    """
    Open the VPN extension popup via Playwright, click Connect, wait for connected state.
    Must run BEFORE the subprocess browser opens (profile lock).

    Uses the ACTUAL browser executable (not Playwright's bundled Chromium) so that
    installed extensions are correctly loaded from the profile.

    Returns: 'connected' | 'already_connected' | 'timeout' | 'no_button' | 'error'
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        selectors = _VPN_SELECTORS.get(vpn_name, {})
        connect_sels = selectors.get("connect", []) + _GENERIC_CONNECT
        connected_sels = selectors.get("connected", []) + _GENERIC_CONNECTED

        # Use the real browser exe so its extensions load (Playwright Chromium can't load them)
        exe = None
        if browser_name and browser_name in _CHROMIUM_FAMILY and browser_name != "chromium":
            exe = _find_executable(browser_name)
            if exe:
                print(f"[BrowserSessions] VPN popup: using {browser_name} at {exe}")
            else:
                print(f"[BrowserSessions] VPN popup: {browser_name} exe not found, falling back to bundled Chromium")

        with sync_playwright() as pw:
            launch_kwargs: dict = dict(
                headless=False,
                args=[
                    "--window-size=1,1",
                    "--window-position=-32000,0",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            if exe:
                launch_kwargs["executable_path"] = exe
            ctx = pw.chromium.launch_persistent_context(profile_dir, **launch_kwargs)
            try:
                page = ctx.new_page()
                page.goto(
                    f"chrome-extension://{ext_id}/popup.html",
                    wait_until="domcontentloaded",
                    timeout=10_000,
                )

                # Check if already connected
                for sel in connected_sels:
                    try:
                        if page.locator(sel).first.is_visible(timeout=800):
                            return "already_connected"
                    except Exception:
                        pass

                # Try to click Connect
                clicked = False
                for sel in connect_sels:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=800):
                            btn.click()
                            clicked = True
                            break
                    except Exception:
                        pass

                if not clicked:
                    return "no_button"

                # Wait for connected state (up to 15s)
                for sel in connected_sels:
                    try:
                        page.wait_for_selector(sel, timeout=15_000)
                        return "connected"
                    except PWTimeout:
                        pass

                return "timeout"
            finally:
                ctx.close()

    except Exception as e:
        print(f"[BrowserSessions] VPN popup error ({vpn_name}): {e}")
        return "error"


def activate_vpns() -> None:
    """
    Activate VPNs for all account profiles BEFORE launching subprocess browsers.

    - Extension VPNs: Playwright opens each profile, navigates to extension popup,
      clicks Connect, closes. State persists in profile for the real browser.
    - Built-in VPNs (Opera): Preferences JSON patched to enable VPN on startup.
    """
    count = len(config.TWITCH_TOKENS)
    print(f"[BrowserSessions] VPN activation starting for {count} account(s)...")
    for i in range(count):
        browser_name = BROWSER_CYCLE[i % len(BROWSER_CYCLE)].lower()
        profile_dir = os.path.abspath(os.path.join("sessions", str(i)))

        if browser_name == "firefox":
            print(f"[BrowserSessions] Browser {i} (Firefox) — VPN activation skipped (not supported)")
            _vpn_states[i] = {"name": "none", "status": "skipped"}
            continue

        if browser_name not in _CHROMIUM_FAMILY:
            print(f"[BrowserSessions] Browser {i} ({browser_name}) — VPN activation skipped (unknown browser)")
            _vpn_states[i] = {"name": "none", "status": "skipped"}
            continue

        if not os.path.isdir(profile_dir):
            print(f"[BrowserSessions] Browser {i} — no profile yet, skipping VPN (run setup_sessions.py first)")
            _vpn_states[i] = {"name": "none", "status": "no_profile"}
            continue

        # 1. Extension-based VPN
        found = _detect_vpn_extension(profile_dir)
        if found:
            vpn_name, ext_id = found
            print(f"[BrowserSessions] Browser {i} — {vpn_name} extension detected, activating...")
            result = _click_vpn_popup(profile_dir, vpn_name, ext_id, browser_name)
            status_label = {
                "connected":         "connected",
                "already_connected": "already connected",
                "timeout":           "timeout (may still connect)",
                "no_button":         "connect button not found",
                "error":             "error",
            }.get(result, result)
            print(f"[BrowserSessions] Browser {i} [{browser_name}]: {vpn_name} → {status_label}")
            _vpn_states[i] = {"name": vpn_name, "status": result}
            continue

        # 2. Built-in VPN (Opera etc.)
        if _has_builtin_vpn(browser_name):
            prefs = _BUILTIN_VPN_PREFS[browser_name]
            ok = _patch_preferences(profile_dir, prefs)
            status = "configured" if ok else "no_profile"
            label = "built-in VPN enabled" if ok else "no Preferences file (will apply after first launch)"
            print(f"[BrowserSessions] Browser {i} [{browser_name}]: built-in VPN → {label}")
            _vpn_states[i] = {"name": f"{browser_name}-builtin", "status": status}
            continue

        print(f"[BrowserSessions] Browser {i} [{browser_name}] — no VPN found, skipping")
        _vpn_states[i] = {"name": "none", "status": "none"}

    print("[BrowserSessions] VPN activation complete")


# ── Browser launch ───────────────────────────────────────────────────────────

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
            "vpn_name": _vpn_states.get(e["index"], {}).get("name", "none"),
            "vpn_status": _vpn_states.get(e["index"], {}).get("status", "unknown"),
        }
        for e in _processes
    ]
