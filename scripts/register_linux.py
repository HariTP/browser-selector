"""Install a per-user desktop entry. --default opts into changing HTTP(S) defaults."""
import argparse
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
from browser_selector.core import host_environment


def quote(value):
    # Desktop Entry escaping (including literal percent field-code escaping).
    value = str(value).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + value + '"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--default", action="store_true")
    parser.add_argument("--restore", action="store_true", help="Restore saved HTTP(S) defaults")
    args = parser.parse_args()
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    app_dir = base / "applications"
    state_dir = base / "browser-selector"
    backup = state_dir / "previous-defaults.json"
    if args.restore:
        state = json.loads(backup.read_text())
        for mime, desktop in state.items():
            if desktop:
                subprocess.run(["xdg-mime", "default", desktop, mime], check=True, env=host_environment())
            else:
                # xdg-mime cannot unset: remove our entry from the user overrides.
                config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
                for target in list(config.glob("*mimeapps.list")) + list(app_dir.glob("*mimeapps.list")):
                    cfg = configparser.ConfigParser(interpolation=None, strict=False)
                    cfg.read(target)
                    if cfg.has_option("Default Applications", mime):
                        current = cfg.get("Default Applications", mime).split(";")
                        remaining = [x for x in current if x and x != "browser-selector.desktop"]
                        if remaining:
                            cfg.set("Default Applications", mime, ";".join(remaining) + ";")
                        else:
                            cfg.remove_option("Default Applications", mime)
                        with target.open("w") as output:
                            cfg.write(output)
        print("Previous HTTP(S) defaults restored. The chooser remains installed.")
        return
    executable = Path(sys.executable) if getattr(sys, "frozen", False) else Path(sys.executable).parent / "browser-selector"
    if not executable.is_file():
        raise SystemExit("Install first: .venv/bin/python -m pip install -e .")
    mimes = ["x-scheme-handler/http", "x-scheme-handler/https"]
    # Capture before writing the desktop entry: installing a handler can change
    # the desktop's fallback even before explicit default associations are set.
    if args.default:
        state_dir.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            state = {mime: subprocess.check_output(["xdg-mime", "query", "default", mime], text=True, env=host_environment()).strip() for mime in mimes}
            backup.write_text(json.dumps(state, indent=2))
    app_dir.mkdir(parents=True, exist_ok=True)
    desktop = app_dir / "browser-selector.desktop"
    desktop.write_text("[Desktop Entry]\nType=Application\nName=Browser Selector\n"
                       "Comment=Choose a browser and profile for web links\n"
                       f"Exec={quote(executable)} %U\nIcon=web-browser\nTerminal=false\n"
                       "Categories=Network;WebBrowser;\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n")
    subprocess.run(["update-desktop-database", str(app_dir)], check=False, env=host_environment())
    if args.default:
        for mime in mimes:
            subprocess.run(["xdg-mime", "default", desktop.name, mime], check=True, env=host_environment())
    print(f"Installed {desktop}. " + ("HTTP(S) defaults enabled." if args.default else "Use --default to route external links through the chooser."))


if __name__ == "__main__":
    main()
