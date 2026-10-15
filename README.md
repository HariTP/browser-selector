# Browser Selector

Choose which browser and profile opens a link from another app. Links clicked
inside a browser keep their normal behavior. No browser extensions or background
service are needed.

[![Browser Selector demo: open a link and choose a browser profile](docs/media/demo.gif)](docs/media/demo.mp4)

[Watch the full demo](docs/media/demo.mp4)

## Install

Download Browser Selector from [GitHub Releases](https://github.com/HariTP/browser-selector/releases).
No Python installation is needed. After installing, set Browser Selector as your
default browser so links from other apps open the chooser.

### Windows

Download the `windows-x86_64-setup.exe` installer and run it. At the end of setup,
select Browser Selector for HTTP and HTTPS in Windows Default Apps.
Installation does not require administrator privileges.

For the portable ZIP, extract the entire folder to a permanent location and run
`browser-selector.exe --setup` to register it and open Default Apps. Keep its
`_internal` folder beside the executable.

Windows downloads are currently unsigned, so Windows may display a security warning.

### macOS

Download `macos-arm64.dmg` for Apple Silicon or `macos-x86_64.dmg` for Intel.
Drag Browser Selector into Applications, launch it, and select it as the default
web browser in System Settings.

The app is not Developer ID signed or notarized, so macOS may warn or block it.

### Linux

For Ubuntu 22.04+/Debian 12+, download the `.deb` and install it through your
software installer or run:

```bash
sudo apt install ./browser-selector-*.deb
```

Then select Browser Selector as the default web browser in desktop Settings.

For the portable `.tar.gz`, extract the entire folder to a permanent location and
run `./browser-selector --setup --make-default` inside it. Keep the `_internal`
folder beside the executable. Portable builds require system desktop libraries;
the `.deb` installs these dependencies through your package manager.

To restore your previously saved HTTP/HTTPS defaults, run:

```bash
browser-selector --setup --restore-defaults
```

## Supported browsers and profiles

- Chrome, Chromium, Brave, Edge, and Vivaldi: choose individual profiles.
- Firefox and compatible browsers: choose detected profiles. Firefox containers
  are not supported.
- Safari: open links in Safari, but choosing a specific Safari profile is not supported.
- Other detected browsers: open links using the browser's normal behavior.

Only current-user profiles in standard locations are detected. Portable browsers
and custom profile locations may not appear. When profiles cannot be detected,
the browser decides which profile to use.

## Privacy and limitations

Browser Selector does not read your cookies, passwords, or browsing history.
Links are passed directly to your chosen browser, not logged or sent to a service.

Only HTTP and HTTPS links are handled. Apps with built-in browsers or their own
browser preference may bypass your system default and will not show the chooser.
