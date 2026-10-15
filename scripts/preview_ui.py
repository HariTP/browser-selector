"""Render the real chooser without opening URLs or changing system appearance."""
import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtDBus import QDBusVariant
from PySide6.QtWidgets import QApplication
from browser_selector.core import discover
from browser_selector.ui import Chooser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--theme', choices=['system', 'light', 'dark'], default='system')
    parser.add_argument('--output', required=True)
    options = parser.parse_args()
    app = QApplication([sys.argv[0]])
    window = Chooser(app, ['https://example.com/a/link?source=desktop'], discover, lambda *args: None)
    if options.theme != 'system':
        window.theme.portal_changed('org.freedesktop.appearance', 'color-scheme', QDBusVariant(1 if options.theme == 'dark' else 2))
    window.show()
    def capture():
        if not window.grab().save(options.output):
            app.exit(1)
            return
        print('Rendered appearance:', window.property('appearance'))
        app.quit()
    QTimer.singleShot(250, capture)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
