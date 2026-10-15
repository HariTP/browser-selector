"""Register an installed chooser for the current user; Windows owns default selection."""
import os
from pathlib import Path
import sys
import winreg


def set_value(path, name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def main():
    executable = Path(sys.executable).parent / "browser-selector.exe"
    if not executable.is_file():
        raise SystemExit("Install first: python -m pip install .")
    command = f'"{executable}" "%1"'
    prog = r"Software\Classes\BrowserSelector.URL"
    set_value(prog, "", "Browser Selector URL")
    set_value(prog, "URL Protocol", "")
    set_value(prog + r"\shell\open\command", "", command)
    base = r"Software\Clients\StartMenuInternet\BrowserSelector"
    set_value(base, "", "Browser Selector")
    set_value(base + r"\shell\open\command", "", f'"{executable}"')
    set_value(base + r"\Capabilities", "ApplicationName", "Browser Selector")
    set_value(base + r"\Capabilities", "ApplicationDescription", "Choose a browser and profile for external web links")
    for scheme in ("http", "https"):
        set_value(base + r"\Capabilities\URLAssociations", scheme, "BrowserSelector.URL")
    set_value(r"Software\RegisteredApplications", "Browser Selector", base + r"\Capabilities")
    import ctypes
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    os.startfile("ms-settings:defaultapps")
    print("Choose Browser Selector for HTTP and HTTPS in Windows Default Apps.")


if __name__ == "__main__":
    main()
