"""Follow native appearance hints, including Linux's desktop appearance portal."""
from __future__ import annotations

import sys
from PySide6.QtCore import QObject, Qt, Slot, SLOT
from PySide6.QtGui import QPalette
try:
    from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusVariant
except ImportError:
    # Native Qt appearance hints still work on builds without Linux D-Bus.
    QDBusConnection = None
    QDBusVariant = object


LIGHT = {
    "background": "#f6f7fb", "surface": "#ffffff", "text": "#172033",
    "muted": "#667085", "border": "#e2e6ef", "hover": "#eef1f8",
    "selected": "#edeaff", "accent": "#6250d5", "avatar": "#e9edf6",
}
DARK = {
    "background": "#151820", "surface": "#1e222d", "text": "#f1f3fa",
    "muted": "#9da6bb", "border": "#333949", "hover": "#282e3c",
    "selected": "#302a4e", "accent": "#b5a6ff", "avatar": "#303747",
}


class SystemTheme(QObject):
    def __init__(self, app, window, changed):
        super().__init__(window)
        self.app, self.window, self.changed = app, window, changed
        self.portal_preference = 0
        self.colors = None
        app.styleHints().colorSchemeChanged.connect(self.update)
        app.paletteChanged.connect(self.update)
        if sys.platform.startswith("linux") and QDBusConnection is not None:
            bus = QDBusConnection.sessionBus()
            bus.connect("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                        "org.freedesktop.portal.Settings", "SettingChanged", self,
                        SLOT("portal_changed(QString,QString,QDBusVariant)"))
            message = QDBusMessage.createMethodCall(
                "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Settings", "Read")
            message.setArguments(["org.freedesktop.appearance", "color-scheme"])
            # A missing portal must not hold up opening the chooser.
            reply = bus.call(message, timeout=300)
            if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
                self.portal_preference = self.unpack(reply.arguments()[0])
        self.update()

    @staticmethod
    def unpack(value):
        while hasattr(value, "variant"):
            value = value.variant()
        return value if value in (0, 1, 2) else 0

    @Slot(str, str, QDBusVariant)
    def portal_changed(self, namespace, key, value):
        if namespace == "org.freedesktop.appearance" and key == "color-scheme":
            self.portal_preference = self.unpack(value)
            self.update()

    def update(self, *_):
        scheme = self.app.styleHints().colorScheme()
        if self.portal_preference in (1, 2):
            dark = self.portal_preference == 1
        elif scheme != Qt.ColorScheme.Unknown:
            dark = scheme == Qt.ColorScheme.Dark
        else:
            dark = self.app.palette().color(QPalette.ColorRole.Window).lightness() < 128
        colors = DARK if dark else LIGHT
        if colors == self.colors:
            return
        self.colors = colors
        self.changed(colors)
