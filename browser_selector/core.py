"""Browser discovery and launch planning. No browser data is modified."""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Browser:
    name: str
    command: tuple[str, ...]
    family: str = "generic"
    roots: tuple[Path, ...] = ()
    icon: str = "web-browser"


@dataclass(frozen=True)
class Choice:
    browser: Browser
    name: str = "Browser default"
    root: Path | None = None
    profile: str | None = None

    @property
    def label(self) -> str:
        return f"{self.browser.name} — {self.name}"


def validate_url(url: str) -> str:
    # Keep the original URL intact, including auth callbacks and fragments.
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("URLs cannot contain control characters")
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only absolute HTTP and HTTPS links are supported")
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid web URL: {exc}") from exc
    return url


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def family_for(text: str) -> str:
    text = text.lower()
    if any(n in text for n in ("firefox", "librewolf", "floorp", "zen-browser")):
        return "firefox"
    if any(n in text for n in ("chrome", "chromium", "brave", "edge", "vivaldi")):
        return "chromium"
    return "generic"


def data_roots(text: str, platform: str = sys.platform, home: Path | None = None) -> tuple[Path, ...]:
    home = home or Path.home()
    text = text.lower()
    if platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
        roaming = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming")))
        pairs = {"chrome": local / "Google/Chrome/User Data", "chromium": local / "Chromium/User Data",
                 "brave": local / "BraveSoftware/Brave-Browser/User Data", "edge": local / "Microsoft/Edge/User Data",
                 "vivaldi": local / "Vivaldi/User Data", "firefox": roaming / "Mozilla/Firefox",
                 "librewolf": roaming / "librewolf"}
    elif platform == "darwin":
        base = home / "Library/Application Support"
        pairs = {"chrome": base / "Google/Chrome", "chromium": base / "Chromium",
                 "brave": base / "BraveSoftware/Brave-Browser", "edge": base / "Microsoft Edge",
                 "vivaldi": base / "Vivaldi", "firefox": base / "Firefox", "librewolf": base / "librewolf"}
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
        pairs = {"chrome": base / "google-chrome", "chromium": base / "chromium",
                 "brave": base / "BraveSoftware/Brave-Browser", "edge": base / "microsoft-edge",
                 "vivaldi": base / "vivaldi", "firefox": home / ".mozilla/firefox",
                 "librewolf": home / ".librewolf", "floorp": home / ".floorp", "zen-browser": home / ".zen"}
    roots = [path for key, path in pairs.items() if key in text]
    if platform.startswith("linux"):
        if "firefox" in text:
            roots += [home / "snap/firefox/common/.mozilla/firefox", home / ".var/app/org.mozilla.firefox/.mozilla/firefox"]
        if "chromium" in text:
            roots += [home / "snap/chromium/common/chromium", home / ".var/app/org.chromium.Chromium/config/chromium"]
        if "chrome" in text:
            roots += [home / ".var/app/com.google.Chrome/config/google-chrome"]
        if "brave" in text:
            roots += [home / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"]
        # A sandboxed installation must not receive a native installation's profile.
        if "flatpak" in text:
            roots = [p for p in roots if ".var/app/" in str(p)]
        elif "snap" in text:
            roots = [p for p in roots if "/snap/" in str(p)]
        else:
            roots = [p for p in roots if ".var/app/" not in str(p) and "/snap/" not in str(p)]
    return tuple(dict.fromkeys(roots))


def desktop_command(value: str, name: str, icon: str, path: Path) -> tuple[str, ...]:
    # Desktop Exec is not shell code. Expand only defined field codes.
    parts = shlex.split(value)
    out = []
    for part in parts:
        if part in {"@@", "@@u", "--file-forwarding"}:
            continue
        if part in {"%u", "%U", "%f", "%F"}:
            continue
        if part == "%i":
            if icon:
                out.extend(["--icon", icon])
            continue
        part = part.replace("%c", name).replace("%k", str(path)).replace("%%", "\0")
        if re.search(r"%[A-Za-z]", part):
            raise ValueError("Unsupported desktop field code")
        out.append(part.replace("\0", "%"))
    if not out or Path(out[0]).name in {"sh", "bash", "dash", "xdg-open", "gio", "browser-selector"}:
        raise ValueError("Not a direct browser command")
    return tuple(out)


def discover_linux(home: Path | None = None, directories: list[Path] | None = None) -> list[Browser]:
    home = home or Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    dirs = [data / "applications"] + [Path(p) / "applications" for p in os.environ.get(
        "XDG_DATA_DIRS", "/usr/local/share:/usr/share:/var/lib/flatpak/exports/share:/var/lib/snapd/desktop").split(":")]
    dirs += [home / ".local/share/flatpak/exports/share/applications"]
    dirs += [Path("/var/lib/flatpak/exports/share/applications"), Path("/var/lib/snapd/desktop/applications")]
    if directories is not None:
        dirs = directories
    seen_ids, browsers = set(), []
    for directory in dirs:
        for path in sorted(directory.glob("*.desktop")):
            if path.name in seen_ids:
                continue
            seen_ids.add(path.name)
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
                if entry.get("Hidden", "false").lower() == "true" or entry.get("Type") != "Application":
                    continue
                if "x-scheme-handler/http" not in entry.get("MimeType", ""):
                    continue
                name, icon = entry.get("Name", path.stem), entry.get("Icon", "web-browser")
                cmd = desktop_command(entry["Exec"], name, icon, path)
                executable = shutil.which(cmd[0])
                if not executable:
                    continue
                if entry.get("TryExec") and not shutil.which(entry["TryExec"]):
                    continue
                text = f"{name} {' '.join(cmd)}"
                if "browser-selector" in text.lower() or "browser_selector" in text.lower():
                    continue
                cmd = (executable, *cmd[1:])
                browser = Browser(name, cmd, family_for(text), data_roots(text, home=home), icon)
                # Duplicate distro/vendor entries often point to the same wrapper.
                key = (str(Path(executable).resolve()), cmd[1:])
                if not any((str(Path(b.command[0]).resolve()), b.command[1:]) == key for b in browsers):
                    browsers.append(browser)
            except (OSError, KeyError, ValueError, configparser.Error):
                continue
    return browsers


def discover_windows() -> list[Browser]:
    import winreg
    result = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Clients\StartMenuInternet", 0, winreg.KEY_READ | view) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        sub = winreg.EnumKey(key, i)
                        try:
                            with winreg.OpenKey(key, sub) as client:
                                name = winreg.QueryValue(client, None)
                                raw = winreg.QueryValue(client, r"shell\open\command")
                            # Browser registration normally supplies a quoted executable.
                            match = re.match(r'^\s*"([^"]+)"', raw)
                            executable = match[1] if match else raw.strip()
                            if not Path(executable).is_file() or "browser-selector" in executable.lower():
                                continue
                            text = f"{name} {executable}"
                            if not any(b.command == (executable,) for b in result):
                                result.append(Browser(name, (executable,), family_for(text), data_roots(text)))
                        except OSError:
                            continue
            except OSError:
                continue
    return result


def discover_macos() -> list[Browser]:
    import plistlib
    result = []
    for base in (Path("/Applications"), Path.home() / "Applications", Path("/System/Applications")):
        for bundle in sorted(base.glob("*.app")):
            try:
                info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
                schemes = {s for row in info.get("CFBundleURLTypes", []) for s in row.get("CFBundleURLSchemes", [])}
                if "http" not in schemes or info.get("CFBundleIdentifier") == "local.browser-selector":
                    continue
                name = info.get("CFBundleDisplayName", info.get("CFBundleName", bundle.stem))
                text = f"{name} {bundle}"
                result.append(Browser(name, ("/usr/bin/open", "-a", str(bundle)), family_for(text), data_roots(text)))
            except (OSError, ValueError, TypeError):
                continue
    return result


def discover() -> list[Browser]:
    browsers = discover_windows() if sys.platform == "win32" else discover_macos() if sys.platform == "darwin" else discover_linux()
    return sorted(browsers, key=lambda b: b.name.casefold())


def choices_for(browser: Browser) -> list[Choice]:
    choices = [Choice(browser)]
    for root in browser.roots:
        if browser.family == "chromium":
            state = read_json(root / "Local State")
            profile_state = state.get("profile", {})
            cache = profile_state.get("info_cache", {}) if isinstance(profile_state, dict) else {}
            if not isinstance(cache, dict):
                cache = {}
            candidates = set(cache)
            try:
                candidates.update(p.name for p in root.iterdir() if p.is_dir() and (p / "Preferences").is_file())
            except OSError:
                continue
            for directory in sorted(candidates):
                if not isinstance(directory, str) or directory in {".", "..", "System Profile", "Guest Profile"} or "/" in directory or "\\" in directory:
                    continue
                if not (root / directory).is_dir():
                    continue
                details = cache.get(directory, {})
                if not isinstance(details, dict):
                    details = {}
                preferences = read_json(root / directory / "Preferences")
                profile_preferences = preferences.get("profile", {})
                name = details.get("name") or (profile_preferences.get("name") if isinstance(profile_preferences, dict) else None) or directory
                choices.append(Choice(browser, str(name), root, directory))
        elif browser.family == "firefox":
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(root / "profiles.ini", encoding="utf-8")
                for section in parser.sections():
                    if not section.startswith("Profile"):
                        continue
                    row = parser[section]
                    path = Path(row["Path"])
                    if row.get("IsRelative", "1") == "1":
                        path = root / path
                    if path.is_dir():
                        choices.append(Choice(browser, row.get("Name", path.name), path.resolve(), str(path.resolve())))
            except (OSError, KeyError, configparser.Error):
                continue
    return choices


def launch_command(choice: Choice, urls: list[str], platform: str = sys.platform) -> list[str]:
    if not urls:
        raise ValueError("No URL supplied")
    urls = [validate_url(u) for u in urls]
    cmd = list(choice.browser.command)
    args = []
    if choice.profile:
        if not choice.root or not choice.root.is_dir():
            raise ValueError("This profile no longer exists. Refresh the browser list.")
        if choice.browser.family == "chromium":
            if not (choice.root / choice.profile).is_dir():
                raise ValueError("This profile no longer exists. Refresh the browser list.")
            args = [f"--user-data-dir={choice.root}", f"--profile-directory={choice.profile}"]
        elif choice.browser.family == "firefox":
            # Do not use --no-remote: it prevents reuse of an already-running profile.
            args = ["-profile", choice.profile]
    if platform == "darwin" and args:
        # LaunchServices may discard --args for an already-running app. Invoke the
        # bundle's executable to let the browser's own instance routing handle it.
        import plistlib
        bundle = Path(cmd[2])
        info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
        cmd = [str(bundle / "Contents/MacOS" / info["CFBundleExecutable"])]
    return cmd + args + urls


def launch(choice: Choice, urls: list[str]) -> subprocess.Popen:
    process = subprocess.Popen(launch_command(choice, urls), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=sys.platform != "win32")
    try:
        code = process.wait(timeout=.2)
        if code != 0:
            raise OSError(f"{choice.browser.name} rejected the launch (exit {code}). Try Browser default or another profile.")
    except subprocess.TimeoutExpired:
        pass  # A newly launched browser remains running after the picker closes.
    return process
