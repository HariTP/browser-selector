"""Exercise the real Qt chooser, grouped navigation, copying and launch planning."""
import os
import subprocess
import sys
import unittest


class GuiTests(unittest.TestCase):
    def test_profile_groups_and_live_appearance_changes(self):
        code = r'''
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtDBus import QDBusVariant
from unittest.mock import patch
from browser_selector.core import Browser, Choice
from browser_selector.ui import Chooser
app = QApplication([])
chrome = Browser('Chrome', ('chrome',))
firefox = Browser('Firefox', ('firefox',))
def choices(b):
    return [Choice(b), Choice(b, 'Personal', profile='Default'), Choice(b, 'Work', profile='Profile 1')] if b == chrome else [Choice(b)]
with patch('browser_selector.ui.choices_for', choices):
    window = Chooser(app, ['https://example.com/' + 'x'*2000], lambda: [chrome, firefox], lambda *args: None)
    window.show()
    app.processEvents()
    group = window.tree.topLevelItem(0)
    assert group.childCount() == 2
    assert group.flags() & Qt.ItemFlag.ItemIsSelectable
    assert not group.isExpanded()
    assert not window.tree.topLevelItem(1).isExpanded()
    assert not window.findChildren(QLineEdit)
    assert not window.findChildren(QPushButton)
    assert window.copy.text() == ''
    assert not window.copy.icon().isNull()
    assert [group.child(i).text(0) for i in range(group.childCount())] == ['Personal', 'Work']
    rect = window.tree.visualItemRect(group)
    QTest.mouseClick(window.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert group.isExpanded()
    assert window.tree.currentItem() == group.child(0)
    QTest.mouseClick(window.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.topRight() + QPoint(-12, rect.height() // 2))
    assert not group.isExpanded()
    assert window.tree.currentItem() == group, 'collapsed profiles must not remain keyboard launch targets'
    assert window.width() == 640, 'long URL must not stretch the popup'
    window.copy.click()
    assert window.copied and window.copy.toolTip() == 'Copied!'
    assert app.clipboard().text() == window.urls[0]
    assert window.copy_timer.interval() == 2500
    QTest.qWait(1500)
    window.copy.click()
    QTest.qWait(1300)
    assert window.copied, 'copying again must restart the feedback timer'
    QTest.qWait(1500)
    assert not window.copied and window.copy.toolTip() == 'Copy link'
    window.theme.portal_changed('org.freedesktop.appearance', 'color-scheme', QDBusVariant(1))
    app.processEvents()
    assert window.property('appearance') == 'dark'
    assert window.delegate.colors['text'] == '#f1f3fa'
    window.theme.portal_changed('org.freedesktop.appearance', 'color-scheme', QDBusVariant(2))
    app.processEvents()
    assert window.property('appearance') == 'light'
    assert window.delegate.colors['text'] == '#172033'
    window.close()
'''
        result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True,
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_url_event_copy_launch_failure_and_retry(self):
        code = r'''
import sys
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QTreeWidget, QMessageBox
from browser_selector.core import Browser, Choice
from browser_selector import app
original_exec = QApplication.exec
errors = []
def exercise():
    try:
        window = QApplication.activeWindow()
        QApplication.sendEvent(QApplication.instance(), QFileOpenEvent(QUrl('https://example.com/?callback=a%2Fb#keep')))
        assert len(window.urls) == 1
        QApplication.sendEvent(QApplication.instance(), QFileOpenEvent(QUrl('file:///etc/passwd')))
        assert len(window.urls) == 1
        window.copy.click()
        assert QApplication.clipboard().text() == window.urls[0]
        item = window.findChild(QTreeWidget).topLevelItem(0).child(0)
        window.open_selected(item.parent())
        window.open_selected(item)
        assert window.isVisible(), 'launch failure must keep picker open'
        window.open_selected(item)
    except BaseException as exc:
        errors.append(repr(exc))
        QApplication.instance().quit()
def run_loop(self):
    QTimer.singleShot(100, exercise)
    QTimer.singleShot(5000, self.quit)
    return original_exec()
sys.argv = ['browser-selector']
with patch.object(app, 'discover', return_value=[Browser('Firefox', ('firefox',))]), patch('browser_selector.ui.choices_for', side_effect=lambda b: [Choice(b), Choice(b, 'Personal', profile='default')]), patch.object(app, 'launch', side_effect=[OSError('test launch failure'), None]) as launch, patch.object(QMessageBox, 'warning') as warning, patch.object(QApplication, 'exec', run_loop):
    app.main()
    assert launch.call_count == 2
    assert warning.call_count == 2
    assert launch.call_args.args[1] == ['https://example.com/?callback=a%2Fb#keep']
assert not errors, errors
'''
        result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True,
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_collapsed_browser_keyboard_selection(self):
        code = r'''
import sys
from unittest.mock import patch
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTreeWidget
from browser_selector.core import Browser
from browser_selector import app

original_exec = QApplication.exec
errors = []
def exercise():
    try:
        window = QApplication.activeWindow()
        assert window is not None
        choices = window.findChild(QTreeWidget)
        assert choices.topLevelItemCount() == 2
        choices.setFocus()
        QTest.keyClick(choices, Qt.Key.Key_Down)
        assert choices.currentItem() == choices.topLevelItem(1)
        QTest.keyClick(choices, Qt.Key.Key_Return)
    except BaseException as exc:
        errors.append(repr(exc))
        QApplication.instance().quit()

def run_loop(self):
    QTimer.singleShot(100, exercise)
    QTimer.singleShot(5000, self.quit)
    return original_exec()

sys.argv = ['browser-selector', '--dry-run', 'https://example.com/?x=1&y=2#keep']
with patch.object(app, 'discover', return_value=[Browser('Chrome', ('chrome',)), Browser('Firefox', ('firefox',))]), patch.object(QApplication, 'exec', run_loop):
    app.main()
assert not errors, errors
'''
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('["firefox", "https://example.com/?x=1&y=2#keep"]', result.stdout)


if __name__ == '__main__':
    unittest.main()
