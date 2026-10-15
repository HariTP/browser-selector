"""Record real chooser/browser footage on an isolated X11 desktop.

Uses temporary XDG configuration and browser profiles. Never records the user's
desktop or changes their default browser. FFmpeg adds zooms and caption overlays.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1920, 1080


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def launcher():
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
    app = QApplication([])
    window = QWidget()
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    window.setGeometry(0, 0, WIDTH, HEIGHT)
    window.setObjectName('desktop')
    window.setStyleSheet('''
        QWidget#desktop { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101523,stop:1 #242038); }
        QFrame#card { background:#1d2434; border:1px solid #384155; border-radius:22px; }
        QLabel { color:#f3f4fb; border:0; background:transparent; font-family:"Noto Sans"; }
        QPushButton { background:#7563eb; color:white; border:0; border-radius:12px; padding:20px; font-size:22px; }
        QPushButton:hover { background:#8c7bf5; }
    ''')
    brand = QLabel('BROWSER SELECTOR', window)
    brand.setStyleSheet('font-size:20px; letter-spacing:5px; color:#b2a8ec;')
    brand.setGeometry(90, 65, 600, 45)
    tagline = QLabel('Your links. Your choice.', window)
    tagline.setStyleSheet('font-size:46px; font-weight:600;')
    tagline.setGeometry(90, 120, 1000, 80)
    card = QFrame(window)
    card.setObjectName('card')
    card.setGeometry(590, 335, 740, 360)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(38, 32, 38, 34)
    label = QLabel('A link from another app')
    label.setStyleSheet('font-size:28px; font-weight:600;')
    layout.addWidget(label)
    note = QLabel('Open a website without committing to one browser.')
    note.setStyleSheet('font-size:18px; color:#aeb8ce;')
    layout.addWidget(note)
    button = QPushButton('Open example.com  ↗')
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    def open_link():
        def clear_background():
            for widget in (card, brand, tagline, caption):
                widget.hide()
        QTimer.singleShot(1000, clear_background)
        log = open(os.environ['SELECTOR_DEMO_LOG'], 'a')
        log.write('Opening external link through xdg-open\n')
        log.flush()
        subprocess.Popen(['xdg-open', 'https://example.com'], stdout=log, stderr=log)
    button.clicked.connect(open_link)
    layout.addWidget(button)
    caption = QLabel('DEMO LAUNCHER  ·  TEMPORARY PROFILES', window)
    caption.setStyleSheet('font-size:14px; letter-spacing:2px; color:#78859f;')
    caption.setGeometry(90, 970, 900, 35)
    window.show()
    app.processEvents()
    point = button.mapToGlobal(button.rect().center())
    Path(os.environ['SELECTOR_DEMO_SOURCE']).write_text(json.dumps({'button': [point.x(), point.y()]}))
    return app.exec()


def chooser(urls):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from browser_selector.app import main
    original = QApplication.exec
    def event_loop(self):
        window = self.window
        window.move(640, 220)
        def save():
            def point(widget, rect):
                value = widget.mapToGlobal(rect.center())
                return [value.x(), value.y()]
            groups = {}
            for index in range(window.tree.topLevelItemCount()):
                group = window.tree.topLevelItem(index)
                groups[group.text(0)] = {'position': point(window.tree.viewport(), window.tree.visualItemRect(group)),
                                        'profiles': {group.child(j).text(0): point(window.tree.viewport(), window.tree.visualItemRect(group.child(j))) for j in range(group.childCount())}}
            Path(os.environ['SELECTOR_DEMO_STATE']).write_text(json.dumps({'groups': groups, 'copy': point(window.copy, window.copy.rect())}))
        timer = QTimer(window)
        timer.timeout.connect(save)
        timer.start(100)
        return original()
    sys.argv = ['browser-selector', *urls]
    with patch.object(QApplication, 'exec', event_loop):
        return main()


def captions(folder):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    phrases = ['A link opens. You choose where.', 'Your browsers, in one place.',
               'Expand a browser. Choose your profile.', 'Copy a link. Get instant feedback.',
               'Pick Work. Keep your sessions separate.', 'The website opens in your chosen profile.']
    for index, phrase in enumerate(phrases):
        image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont('Noto Sans', 23, QFont.Weight.Medium))
        width = painter.fontMetrics().horizontalAdvance(phrase) + 84
        rectangle = QRectF((WIDTH-width)/2, 938, width, 78)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 20, 33, 238))
        painter.drawRoundedRect(rectangle, 18, 18)
        painter.setPen(QColor('#f2f4ff'))
        painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, phrase)
        painter.end()
        image.save(str(folder/f'caption-{index}.png'))


def record(destination):
    destination.mkdir(parents=True, exist_ok=True)
    checks = ROOT/'build/demo-checks'
    checks.mkdir(parents=True, exist_ok=True)
    processes = []
    with tempfile.TemporaryDirectory(prefix='browser-selector-demo-') as task:
        base = Path(task)
        config, data = base/'config', base/'data'
        apps = data/'applications'
        apps.mkdir(parents=True)
        config.mkdir()
        env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data),
                   XDG_DATA_DIRS=str(data), XDG_CURRENT_DESKTOP='X-Generic', DE='generic',
                   QT_QPA_PLATFORM='xcb', QT_STYLE_OVERRIDE='Fusion',
                   SELECTOR_DEMO_STATE=str(base/'chooser.json'), SELECTOR_DEMO_SOURCE=str(base/'source.json'),
                   SELECTOR_DEMO_LOG=str(checks/'recording.log'))
        for key in ('WAYLAND_DISPLAY', 'QT_QPA_PLATFORMTHEME', 'BROWSER'):
            env.pop(key, None)
        read_fd, write_fd = os.pipe()
        xvfb = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '1920x1080x24', '-nolisten', 'tcp', '-ac'], pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        processes.append(xvfb)
        os.close(write_fd)
        display = os.read(read_fd, 30).decode().strip()
        os.close(read_fd)
        env['DISPLAY'] = ':' + display
        def spawn(args, **kwargs):
            process = subprocess.Popen([str(a) for a in args], env=env, start_new_session=True, **kwargs)
            processes.append(process)
            return process
        def wait_json(file):
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                try:
                    return json.loads(file.read_text())
                except (OSError, ValueError):
                    time.sleep(.1)
            raise RuntimeError(f'Timed out waiting for {file.name}')
        def click(position):
            x, y = position
            current = subprocess.check_output(['xdotool', 'getmouselocation', '--shell'], env=env, text=True)
            coordinates = dict(line.split('=', 1) for line in current.splitlines())
            start_x, start_y = int(coordinates['X']), int(coordinates['Y'])
            for step in range(1, 13):
                fraction = (1-math.cos(math.pi*step/12))/2
                run('xdotool', 'mousemove', '--sync', round(start_x+(x-start_x)*fraction), round(start_y+(y-start_y)*fraction), env=env)
                time.sleep(.015)
            time.sleep(.25)
            run('xdotool', 'click', '1', env=env)
        def screenshot(name):
            run('ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'x11grab', '-video_size', '1920x1080', '-i', env['DISPLAY'], '-frames:v', '1', '-y', checks/name, env=env)
        flags = '--ozone-platform=x11 --no-first-run --no-default-browser-check --disable-sync --disable-extensions --disable-features=Translate --password-store=basic --window-size=1740,840 --window-position=90,100'
        for filename, name, executable, root_name, profiles in [
            ('chrome.desktop', 'Google Chrome', '/usr/bin/google-chrome', 'google-chrome', ['Personal']),
            ('brave.desktop', 'Brave', '/usr/bin/brave-browser', 'BraveSoftware/Brave-Browser', ['Personal', 'Work'])]:
            root = config/root_name
            cache = {}
            for index, profile in enumerate(profiles):
                directory = 'Default' if index == 0 else f'Profile {index}'
                (root/directory).mkdir(parents=True)
                (root/directory/'Preferences').write_text(json.dumps({'profile': {'name': profile}, 'browser': {'check_default_browser': False}, 'signin': {'allowed': False}, 'translate': {'enabled': False}}))
                cache[directory] = {'name': profile, 'user_name': '', 'is_using_default_name': False}
            (root/'Local State').write_text(json.dumps({'profile': {'info_cache': cache, 'last_used': 'Profile 1' if len(profiles)>1 else 'Default'}}))
            icon = '/opt/google/chrome/product_logo_256.png' if name == 'Google Chrome' else '/opt/brave.com/brave/product_logo_256.png'
            (apps/filename).write_text(f'[Desktop Entry]\nType=Application\nName={name}\nExec={executable} {flags} %U\nIcon={icon}\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n')
        (apps/'firefox_firefox.desktop').write_text('[Desktop Entry]\nType=Application\nHidden=true\n')
        command = f'{sys.executable} {Path(__file__).resolve()} --chooser %U'
        (apps/'browser-selector.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=Browser Selector\nExec={command}\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n')
        (config/'mimeapps.list').write_text('[Default Applications]\nx-scheme-handler/http=browser-selector.desktop\nx-scheme-handler/https=browser-selector.desktop\n')
        handler = subprocess.check_output(['xdg-mime', 'query', 'default', 'x-scheme-handler/https'], env=env, text=True).strip()
        if handler != 'browser-selector.desktop':
            raise RuntimeError(f'Unexpected isolated URL handler: {handler}')
        chrome_log = (base/'chrome.log').open('w')
        browser = spawn(['/usr/bin/brave-browser', *flags.split(), f'--user-data-dir={config/"BraveSoftware/Brave-Browser"}', '--profile-directory=Profile 1', 'https://example.com'], stdout=chrome_log, stderr=chrome_log)
        capture = None
        try:
            time.sleep(6)
            screenshot('demo-browser-check.png')
            source = spawn([sys.executable, __file__, '--launcher'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            source_state = wait_json(base/'source.json')
            run('xdotool', 'search', '--pid', str(source.pid), 'windowraise', 'windowfocus', env=env)
            time.sleep(.6)
            screenshot('demo-launcher-check.png')
            raw = base/'capture.mkv'
            capture = spawn(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-progress', 'pipe:1', '-stats_period', '0.1', '-f', 'x11grab', '-framerate', '30', '-video_size', '1920x1080', '-draw_mouse', '1', '-i', env['DISPLAY'], '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-threads', '4', '-crf', '16', '-y', raw], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            started = threading.Event()
            def read_progress():
                for line in capture.stdout:
                    if line.startswith(b'frame='):
                        started.set()
            reader = threading.Thread(target=read_progress, daemon=True)
            reader.start()
            if not started.wait(10):
                capture.send_signal(signal.SIGINT)
                capture.wait(timeout=5)
                raise RuntimeError('Screen capture did not start: ' + capture.stderr.read().decode())
            began = time.monotonic()
            def until(seconds):
                time.sleep(max(0, seconds-(time.monotonic()-began)))
            def moment():
                return round(time.monotonic()-began, 2)
            until(2.5)
            click(source_state['button'])
            state = wait_json(base/'chooser.json')
            markers = {'chooser': moment()}
            run('xdotool', 'search', '--name', 'Open link with', 'windowraise', env=env)
            until(markers['chooser']+2)
            click(state['groups']['Brave']['position'])
            time.sleep(.6)
            markers['expanded'] = moment()
            screenshot('demo-chooser-check.png')
            until(markers['expanded']+2)
            state = wait_json(base/'chooser.json')
            click(state['copy'])
            markers['copied'] = moment()
            time.sleep(.5)
            screenshot('demo-copied-check.png')
            until(markers['copied']+3)
            state = wait_json(base/'chooser.json')
            click(state['groups']['Brave']['profiles']['Work'])
            markers['selected'] = moment()
            time.sleep(1.5)
            run('xdotool', 'search', '--onlyvisible', '--class', 'brave-browser', 'windowraise', env=env)
            markers['browser'] = moment()
            time.sleep(2)
            screenshot('demo-result-check.png')
            until(markers['browser']+5)
            capture.stdin.write(b'q')
            capture.stdin.flush()
            capture.wait(timeout=15)
            reader.join(timeout=2)
            capture = None
            markers['duration'] = moment()
            (checks/'timing.json').write_text(json.dumps(markers, indent=2))
            print(json.dumps(markers), flush=True)
            captions(base)
            c, e, k, s, b = [markers[key] for key in ('chooser', 'expanded', 'copied', 'selected', 'browser')]
            zoom = f'if(lt(on,{c*30}),1,if(lt(on,{(c+1.3)*30}),1+0.25*(1-cos(PI*(on-{c*30})/39))/2,if(lt(on,{s*30}),1.25,if(lt(on,{b*30}),1.25-0.25*(1-cos(PI*(on-{s*30})/{(b-s)*30}))/2,1))))'
            filters = [f"[0:v]zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps=30[v0]"]
            ranges = [(0,c),(c,e),(e,k),(k,s-.6),(s-.6,b),(b,markers['duration'])]
            for index, (start,end) in enumerate(ranges):
                filters.append(f"[v{index}][{index+1}:v]overlay=0:0:enable='between(t,{start},{end})'[v{index+1}]")
            inputs = ['ffmpeg','-hide_banner','-loglevel','error','-i',raw]
            for index in range(6):
                inputs += ['-loop','1','-i',base/f'caption-{index}.png']
            run(*inputs, '-filter_complex', ';'.join(filters), '-map','[v6]', '-t', str(markers['duration']), '-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-an','-y',destination/'demo.mp4')
            run('ffmpeg','-hide_banner','-loglevel','error','-i',destination/'demo.mp4','-vf','fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3','-loop','0','-y',destination/'demo.gif')
            run('ffmpeg','-hide_banner','-loglevel','error','-ss',str(e+.3),'-i',destination/'demo.mp4','-frames:v','1','-y',destination/'demo-poster.png')
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=8)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(.3)
            chrome_log.close()


if __name__ == '__main__':
    if '--launcher' in sys.argv:
        raise SystemExit(launcher())
    if '--chooser' in sys.argv:
        raise SystemExit(chooser(sys.argv[sys.argv.index('--chooser')+1:]))
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs/media')
    args = parser.parse_args()
    record(args.output_dir.resolve())
