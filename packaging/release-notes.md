Choose a browser and profile whenever another app opens a web link.

## Downloads

- **Windows x64:** download the `windows-x86_64-setup.exe` installer. Finish setup by selecting Browser Selector for HTTP and HTTPS in Windows Default Apps. A portable ZIP is also available; keep the extracted folder in place and run `browser-selector.exe --setup`.
- **macOS:** download the DMG matching your Mac (`arm64` for Apple Silicon, `x86_64` for Intel), drag Browser Selector into Applications, then choose it as the default web browser in System Settings.
- **Linux x64:** install the `.deb` on Ubuntu 22.04+/Debian 12+, or extract the portable `.tar.gz` and keep its folder in place. Choose Browser Selector as the default browser in desktop Settings. To register a portable download or replace an earlier source installation, run `./browser-selector --setup --make-default` from the extracted folder.

Python and Qt are included in the downloads. You do not need to install Python.

This first release is a prerelease. Linux link routing has been tested with Chrome, Brave, and Firefox. Windows/macOS packages receive native build and bundled-GUI startup checks, but interactive browser routing on those systems still needs user testing. Safari profiles are not selectable.

Windows installers are unsigned; macOS bundles are ad-hoc signed, not Developer ID signed or notarized. The OS may warn or block opening them. Follow your organization's software policy; managed devices may require administrator approval.

SHA-256 checksum files are included with each platform's assets. Source code and setup instructions: https://github.com/HariTP/browser-selector
