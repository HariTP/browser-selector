"""Cold and warm Firefox profile routing, using temporary project-local profiles."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from browser_selector.core import Browser, Choice, launch


def main():
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        raise SystemExit('Run this test from an active desktop terminal (DISPLAY or WAYLAND_DISPLAY required). Snap Firefox cannot reliably use a virtual X11 display.')
    requests = set()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.add(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<title>Firefox profile routing test</title>')

        def log_message(self, *args):
            pass

    def wait(path):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if path in requests:
                return
            time.sleep(.1)
        raise RuntimeError(f'Firefox did not open {path}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    process = None
    # Snap Firefox has a private /tmp; project-local paths remain visible.
    with tempfile.TemporaryDirectory(prefix='.firefox-test-', dir=Path(__file__).resolve().parents[1]) as temp:
        root = Path(temp)
        (root / 'user.js').write_text('user_pref("browser.shell.checkDefaultBrowser", false);\n'
                                    'user_pref("browser.aboutwelcome.enabled", false);\n'
                                    'user_pref("browser.startup.homepage_override.mstone", "ignore");\n')
        log = (root / 'test.log').open('w')
        choice = Choice(Browser('Firefox', ('firefox',), 'firefox'), 'Test', root, str(root))
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            # Capture startup errors; equivalent to the chooser's launch plan.
            from browser_selector.core import launch_command
            process = subprocess.Popen(launch_command(choice, [url + '/cold']), stdout=log, stderr=log,
                                       start_new_session=True)
            wait('/cold')
            print('PASS: cold Firefox launch opened the selected temporary profile')
            forwarded = launch(choice, [url + '/warm?token=a%2Fb#keep'])
            result = forwarded.wait(timeout=15)
            if result:
                raise RuntimeError(f'Firefox rejected warm launch with exit {result}')
            wait('/warm?token=a%2Fb')
            print('PASS: already-running Firefox profile received the next URL')
        except BaseException:
            print('Requests received: ' + repr(requests), file=sys.stderr)
            print((root / 'test.log').read_text(), file=sys.stderr)
            raise
        finally:
            server.shutdown()
            server.server_close()
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            log.close()


if __name__ == '__main__':
    main()
