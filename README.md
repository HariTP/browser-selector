# Browser Selector

A desktop popup for external HTTP/HTTPS links. Choose a browser or a specific
profile, copy the URL, or close the popup. Links inside browsers keep their
normal behavior. No browser extensions or background service are needed.

The popup starts with collapsed, clickable browser rows with chevrons. Click a
browser to reveal only its named profiles; browsers without discoverable profiles
open directly. An icon beside the URL copies the full link. Keyboard navigation
and closing with Escape are supported. It follows the system's light/dark appearance, including
changes while the popup is open. On Linux it reads the desktop appearance portal,
with native Qt appearance/palette hints as a fallback. New links use the updated
UI immediately; already-open chooser windows need to be closed and reopened.

## Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/browser-selector --list
.venv/bin/browser-selector 'https://example.com'
.venv/bin/python scripts/register_linux.py --default
```

The registration is per-user; it needs no root privileges. Keep this checkout and
its virtual environment at the installed path. Run the registration script again
after moving them. Omit `--default` to register without changing defaults.
On Debian/Ubuntu X11 desktops, Qt also requires `libxcb-cursor0` (install using
`sudo apt install libxcb-cursor0`). Wayland sessions use Qt's Wayland backend.

To restore your previous HTTP/HTTPS defaults:

```bash
.venv/bin/python scripts/register_linux.py --restore
```

Other apps must use the system default browser. Apps with a built-in webview or an
explicit browser preference can bypass the chooser. This app only handles HTTP
and HTTPS, not HTML files or custom protocols. Separate simultaneous invocations
produce separate chooser windows; multiple links received together share a picker.

## Browser/profile support

- Registered Linux browsers are discovered from desktop entries, including Snap
  and Flatpak exports. Duplicate registrations are collapsed.
- Chrome, Chromium, Brave, Edge and Vivaldi: profiles are read from local metadata
  and selected with explicit data-directory and profile-directory arguments.
- Firefox and compatible browsers: profiles listed in `profiles.ini` are selected
  by their absolute path. New profile managers or forks with different storage
  layouts may need adapters. Containers are not profiles and are not supported.
- Safari and browsers without a supported profile adapter appear as browser-only
  choices. Safari chooses its profile using its own rules.
- Browsers without discoverable profiles use the browser's normal behavior; this
  is not a guarantee of a particular last-used profile.

Discovery is limited to standard paths and current-user profiles. Portable/custom
data directories and browser channels may need future adapters. Browser metadata
is read only; no cookies, passwords or browsing history are read. URLs are passed
as process arguments, without invoking a shell, and are neither logged nor sent
to a service. Missing executables and immediate browser errors keep the picker
open; a browser's later internal error may require retrying the link.

## Windows (implemented, unverified)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install .
.venv\Scripts\python scripts\register_windows.py
```

Select Browser Selector for HTTP and HTTPS in the Settings page that opens.
Discovery uses current-user and machine browser registrations. No protected
default-association registry values are changed. Keep the virtual environment in
place. Windows builds and runtime behavior have not been tested here.

## macOS (implemented, unverified)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install . pyinstaller
.venv/bin/python scripts/build_macos.py
```

Move `dist/Browser Selector.app` into `/Applications`, launch it, then choose it as
the default web browser in System Settings. The bundle receives URL Apple events
through Qt. Discovery scans `/Applications`, `~/Applications`, and system apps.
Profile-specific launches invoke the browser executable so its own instance
routing can handle an already-running browser. Safari profile selection is not
implemented. Packaging, Apple-event delivery, and runtime behavior are unverified.
Public distribution requires developer signing and notarization.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest tests.test_gui -v
```

`--dry-run` opens the real chooser but prints the selected launch command instead
of opening a browser. The Linux smoke-test script starts Chrome with temporary
profiles on a virtual display and checks that URLs reach the selected profile;
it does not touch your existing browser profiles. Run the Firefox check from an
active desktop terminal; Snap Firefox may not be able to access a virtual X11
display:

```bash
.venv/bin/python scripts/smoke_linux.py
.venv/bin/python scripts/smoke_linux.py --browser brave-browser
.venv/bin/python scripts/smoke_firefox.py
```

Verified on the development Linux machine: real Chrome and Brave profile routing
on X11, cold/warm Snap Firefox routing on Wayland, chooser rendering on the actual
Wayland desktop, and HTTP/HTTPS default-handler delivery through `xdg-open`.
Windows/macOS implementation is not runtime-verified. Other Linux distributions,
Flatpak variants, and multiple simultaneous Firefox profiles still need testing.
