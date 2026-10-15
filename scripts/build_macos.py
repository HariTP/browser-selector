"""Build an application bundle with HTTP(S) handling and Qt Apple-event support.

Run on macOS after: python -m pip install . pyinstaller
"""
from pathlib import Path
import plistlib
import subprocess
import sys


def main():
    if sys.platform != "darwin":
        raise SystemExit("Run this packaging script on macOS")
    entry = Path(__file__).resolve().parents[1] / "scripts/desktop_entry.py"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
                    "--name", "Browser Selector", "--osx-bundle-identifier", "local.browser-selector",
                    str(entry)], check=True)
    info = Path("dist/Browser Selector.app/Contents/Info.plist")
    content = plistlib.loads(info.read_bytes())
    content["CFBundleURLTypes"] = [{"CFBundleURLName": "Web links", "CFBundleTypeRole": "Viewer",
                                  "CFBundleURLSchemes": ["http", "https"]}]
    content["NSHighResolutionCapable"] = True
    info.write_bytes(plistlib.dumps(content))
    # Modifying Info.plist invalidates PyInstaller's ad-hoc signature.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", "dist/Browser Selector.app"], check=True)
    print("Move dist/Browser Selector.app into /Applications, launch it, then select it as the default browser in System Settings. Distribution requires signing/notarization.")


if __name__ == "__main__":
    main()
