from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from .core import choices_for, discover, launch, launch_command, validate_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Choose a browser and profile for external links")
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--list", action="store_true", help="Print detected browsers and profiles")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned command instead of opening a browser")
    parser.add_argument("--version", action="version", version="Browser Selector 0.1.0")
    parser.add_argument("--setup", action="store_true", help="Register this installation as an available browser")
    parser.add_argument("--make-default", action="store_true", help="With --setup, enable HTTP(S) defaults on Linux")
    parser.add_argument("--restore-defaults", action="store_true", help="With --setup, restore previous Linux defaults")
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if (options.make_default or options.restore_defaults) and not options.setup:
        parser.error("--make-default and --restore-defaults require --setup")
    if options.setup:
        if sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", "x-apple.systempreferences:com.apple.Desktop-Settings.extension"], check=True)
            return 0
        import runpy
        base = Path(sys._MEIPASS) / "registration" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1] / "scripts"
        script = base / ("register_windows.py" if sys.platform == "win32" else "register_linux.py")
        original = sys.argv
        sys.argv = [str(script)]
        if sys.platform.startswith("linux"):
            if options.make_default:
                sys.argv.append("--default")
            if options.restore_defaults:
                sys.argv.append("--restore")
        try:
            runpy.run_path(str(script), run_name="__main__")
        finally:
            sys.argv = original
        return 0
    if options.self_test:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from .ui import Chooser
        application = QApplication([sys.argv[0]])
        window = Chooser(application, ["https://example.com"], discover, lambda *args: None)
        window.show()
        application.processEvents()
        assert window.windowTitle() and window.tree is not None
        window.close()
        return 0
    try:
        urls = [validate_url(u) for u in options.urls]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if options.list:
        print(json.dumps([{"browser": b.name, "command": b.command, "family": b.family,
                           "profiles": [{"name": c.name, "path": str(c.root) if c.root else None,
                                         "profile": c.profile} for c in choices_for(b)]} for b in discover()], indent=2))
        return 0
    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .ui import Chooser

    class Application(QApplication):
        def __init__(self, args):
            self.window = None
            self.pending_urls = []
            super().__init__(args)

        def event(self, event):
            if event.type() == QEvent.Type.FileOpen:
                try:
                    url = validate_url(event.url().toString())
                    if self.window is None:
                        self.pending_urls.append(url)
                    else:
                        self.window.add_url(url)
                except ValueError as exc:
                    QMessageBox.warning(self.window, "Unsupported link", str(exc))
                return True
            return super().event(event)

    def open_choice(choice, urls, window):
        try:
            if options.dry_run:
                print(json.dumps(launch_command(choice, urls)), flush=True)
            else:
                launch(choice, urls)
            window.accept()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(window, "Could not open link", str(exc))

    app = Application([sys.argv[0]])
    app.setApplicationName("Browser Selector")
    app.setOrganizationName("Browser Selector")
    window = Chooser(app, urls, discover, open_choice)
    app.window = window
    for url in app.pending_urls:
        window.add_url(url)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
