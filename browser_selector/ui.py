"""Grouped, keyboard-accessible browser chooser with native theme tracking."""
from __future__ import annotations

from urllib.parse import urlsplit
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFrame, QHBoxLayout, QLabel,
                              QToolButton, QStyle, QStyledItemDelegate,
                              QTreeWidget, QTreeWidgetItem, QVBoxLayout)
from .core import choices_for
from .theme import LIGHT, SystemTheme

CHOICE_ROLE = Qt.ItemDataRole.UserRole
COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
BROWSER_ROLE = Qt.ItemDataRole.UserRole + 3


class BrowserRows(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
        self.colors = LIGHT

    def sizeHint(self, option, index):
        return QSize(440, 66 if index.data(CHOICE_ROLE) is not None else 56)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.colors
        r = option.rect.adjusted(4, 2, -4, -2)
        choice = index.data(CHOICE_ROLE)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c["selected"] if selected else c["hover"] if hovered else c["surface"]))
        painter.drawRoundedRect(QRectF(r), 10, 10)
        if choice is None:
            icon = index.data(Qt.ItemDataRole.DecorationRole)
            if isinstance(icon, QIcon) and not icon.isNull():
                icon.paint(painter, r.x() + 12, r.y() + 15, 26, 26)
            else:
                painter.setBrush(QColor(c["avatar"]))
                painter.drawEllipse(QRectF(r.x() + 12, r.y() + 15, 26, 26))
                painter.setPen(QColor(c["muted"]))
                painter.drawText(QRectF(r.x() + 12, r.y() + 15, 26, 26), Qt.AlignmentFlag.AlignCenter, str(index.data())[:1])
            font = QFont(option.font)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(c["text"]))
            text = painter.fontMetrics().elidedText(str(index.data()), Qt.TextElideMode.ElideRight, r.width() - 155)
            painter.drawText(r.adjusted(48, 0, -100, 0), Qt.AlignmentFlag.AlignVCenter, text)
            count = index.data(COUNT_ROLE)
            painter.setFont(option.font)
            painter.setPen(QColor(c["muted"]))
            painter.drawText(r.adjusted(0, 0, -42, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{count} profile{'s' if count != 1 else ''}" if count else "Open browser")
            painter.setPen(QPen(QColor(c["accent"] if hovered or selected else c["muted"]), 1.8))
            x, y = r.right() - 22, r.center().y()
            expanded = self.parent().itemFromIndex(index).isExpanded()
            points = [QPointF(x - 4, y - 2), QPointF(x, y + 2), QPointF(x + 4, y - 2)] if expanded else [QPointF(x - 2, y - 4), QPointF(x + 2, y), QPointF(x - 2, y + 4)]
            painter.drawPolyline(points)
        else:
            x = r.x() + 28
            painter.setBrush(QColor(c["selected"] if selected else c["avatar"]))
            painter.drawEllipse(QRectF(x, r.y() + 15, 32, 32))
            painter.setPen(QColor(c["accent"] if selected else c["muted"]))
            font = QFont(option.font)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(x, r.y() + 15, 32, 32), Qt.AlignmentFlag.AlignCenter, choice.name[:1].upper())
            title = choice.name
            painter.setPen(QColor(c["text"]))
            text = painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, r.width() - 124)
            painter.drawText(r.adjusted(74, 9, -40, -30), Qt.AlignmentFlag.AlignVCenter, text)
            font.setBold(False)
            font.setPointSizeF(max(9, option.font.pointSizeF() - 1))
            painter.setFont(font)
            painter.setPen(QColor(c["muted"]))
            painter.drawText(r.adjusted(74, 32, -40, -7), Qt.AlignmentFlag.AlignVCenter,
                             "Open in this profile")
            if selected:
                painter.setPen(QColor(c["accent"]))
                painter.drawText(r.adjusted(0, 0, -17, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "↵")
                painter.setPen(QPen(QColor(c["accent"]), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(r), 10, 10)
        painter.restore()


class BrowserTree(QTreeWidget):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.currentItem():
            self.itemActivated.emit(self.currentItem(), 0)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            direction = 1 if event.key() == Qt.Key.Key_Down else -1
            rows = []
            for i in range(self.topLevelItemCount()):
                group = self.topLevelItem(i)
                if not group.isHidden():
                    rows.append(group)
                    if group.isExpanded():
                        rows.extend(group.child(j) for j in range(group.childCount()) if not group.child(j).isHidden())
            if rows:
                current = self.currentItem()
                position = rows.index(current) if current in rows else (-1 if direction == 1 else len(rows))
                item = rows[max(0, min(len(rows) - 1, position + direction))]
                self.setCurrentItem(item)
                self.scrollToItem(item)
            event.accept()
            return
        super().keyPressEvent(event)


class Chooser(QDialog):
    def __init__(self, app, urls, discover, open_choice):
        super().__init__()
        self.app, self.urls = app, list(urls)
        self.discover, self.open_choice = discover, open_choice
        self.setWindowTitle("Open link with…")
        self.setMinimumSize(460, 360)
        self.resize(640, 580)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(15)
        title = QLabel("Choose browser and profile")
        title.setObjectName("title")
        layout.addWidget(title)
        card = QFrame()
        card.setObjectName("linkCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)
        link_text = QVBoxLayout()
        link_text.setSpacing(4)
        self.domain = QLabel()
        self.domain.setObjectName("domain")
        self.domain.setTextFormat(Qt.TextFormat.PlainText)
        link_text.addWidget(self.domain)
        self.address = QLabel()
        self.address.setObjectName("muted")
        self.address.setTextFormat(Qt.TextFormat.PlainText)
        self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        link_text.addWidget(self.address)
        card_layout.addLayout(link_text, 1)
        self.copy = QToolButton()
        self.copy.setObjectName("copyLink")
        self.copy.setToolTip("Copy link")
        self.copy.setAccessibleName("Copy link")
        self.copy.setFixedSize(34, 34)
        self.copy.setIconSize(QSize(20, 20))
        self.copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copied = False
        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.setInterval(2500)
        self.copy_timer.timeout.connect(self.reset_copy)
        self.copy.clicked.connect(self.copy_link)
        card_layout.addWidget(self.copy)
        layout.addWidget(card)
        self.tree = BrowserTree()
        self.tree.setMinimumHeight(320)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setMouseTracking(True)
        self.tree.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tree.setAccessibleName("Browsers and their profiles")
        self.delegate = BrowserRows(self.tree)
        self.tree.setItemDelegate(self.delegate)
        self.tree.itemActivated.connect(self.open_selected)
        self.tree.itemClicked.connect(self.open_selected)
        layout.addWidget(self.tree, 1)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.theme = SystemTheme(app, self, self.apply_theme)
        self.refresh()
        self.update_address()
        self.tree.setFocus()

    def apply_theme(self, c):
        self.setProperty("appearance", "dark" if c["background"] == "#151820" else "light")
        self.delegate.colors = c
        self.update_copy_icon()
        self.setStyleSheet(f"""
            QDialog {{ background: {c['background']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; background: transparent; font-size: 13px; }}
            QLabel#title {{ font-size: 25px; font-weight: 700; }}
            QLabel#eyebrow {{ color: {c['muted']}; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
            QLabel#muted {{ color: {c['muted']}; font-size: 12px; }}
            QLabel#domain {{ font-weight: 600; }}
            QFrame#linkCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
            QTreeWidget {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
                           border-radius: 12px; padding: 6px; outline: none; }}
            QTreeWidget::branch {{ background: transparent; }}
            QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; }}
            QToolButton:hover {{ background: {c['hover']}; border-color: {c['border']}; }}
            QToolButton:focus {{ border-color: {c['accent']}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 1px; }}
            QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QToolTip {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 6px; }}
        """)
        self.tree.viewport().update()

    def copy_link(self):
        self.app.clipboard().setText("\n".join(self.urls))
        self.copied = True
        self.copy.setToolTip("Copied!")
        self.copy.setAccessibleName("Link copied")
        self.update_copy_icon()
        self.copy_timer.start()

    def reset_copy(self):
        self.copied = False
        self.copy.setToolTip("Copy link")
        self.copy.setAccessibleName("Copy link")
        self.update_copy_icon()

    def update_copy_icon(self):
        c = self.delegate.colors
        pixmap = QPixmap(40, 40)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.copied:
            painter.setPen(QPen(QColor(c["accent"]), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline([QPointF(4, 10), QPointF(8, 14), QPointF(16, 6)])
        else:
            painter.setPen(QPen(QColor(c["muted"]), 1.5))
            painter.drawRoundedRect(QRectF(7, 3, 10, 11), 2, 2)
            painter.setBrush(QColor(c["surface"]))
            painter.drawRoundedRect(QRectF(3, 7, 10, 11), 2, 2)
        painter.end()
        self.copy.setIcon(QIcon(pixmap))

    def update_address(self):
        self.domain.setText(urlsplit(self.urls[0]).hostname if self.urls else "Ready for your next link")
        text = self.urls[0] if self.urls else "Open a link from another app to choose its destination."
        if len(self.urls) > 1:
            self.domain.setText(self.domain.text() + f"  ·  {len(self.urls)} links")
        self.address.setToolTip(text)
        self.address.setText(self.address.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, max(160, self.width() - 138)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "address"):
            self.update_address()

    def add_url(self, url):
        self.urls.append(url)
        self.update_address()
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self):
        self.tree.clear()
        for browser in self.discover():
            choices = [choice for choice in choices_for(browser) if choice.profile is not None]
            group = QTreeWidgetItem(self.tree, [browser.name])
            group.setIcon(0, QIcon.fromTheme(browser.icon, QIcon.fromTheme("web-browser")))
            group.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            group.setData(0, COUNT_ROLE, len(choices))
            group.setData(0, BROWSER_ROLE, browser)
            group.setToolTip(0, "Click to show profiles" if choices else "Open this browser")
            group.setExpanded(False)
            for choice in choices:
                item = QTreeWidgetItem(group, [choice.name])
                item.setData(0, CHOICE_ROLE, choice)
                item.setToolTip(0, choice.label)
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.status.setText("Click a browser to show its profiles  ·  Esc to close" if self.tree.topLevelItemCount() else
                            "No browsers found. Install a browser, then reopen this window.")

    def open_current(self):
        if self.tree.currentItem():
            self.open_selected(self.tree.currentItem())

    def open_selected(self, item, *_):
        choice = item.data(0, CHOICE_ROLE)
        if choice is None:
            if not item.childCount():
                from .core import Choice
                choice = Choice(item.data(0, BROWSER_ROLE))
                if self.urls:
                    self.open_choice(choice, self.urls, self)
                return
            item.setExpanded(not item.isExpanded())
            if item.isExpanded():
                visible = [item.child(i) for i in range(item.childCount()) if not item.child(i).isHidden()]
                self.tree.setCurrentItem(visible[0] if visible else None)
            elif self.tree.currentItem() and self.tree.currentItem().parent() is item:
                self.tree.setCurrentItem(item)
            return
        if not self.urls:
            self.status.setText("Open an external web link to choose its destination.")
            return
        self.open_choice(choice, self.urls, self)
