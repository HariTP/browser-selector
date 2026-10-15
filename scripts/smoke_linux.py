"""Real Chrome routing test using temporary data only, isolated from user browsers."""
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen

from browser_selector.core import Browser, Choice, launch


def wait_for(check, message, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError(message)


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('This smoke test is Linux only')
    if not os.environ.get('DISPLAY'):
        raise SystemExit(subprocess.call(['xvfb-run', '-a', sys.executable, __file__, *sys.argv[1:]]))
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', default='google-chrome', help='Chromium-family executable, e.g. brave-browser')
    args = parser.parse_args()
    chrome = shutil.which(args.browser)
    if not chrome:
        raise SystemExit(f'{args.browser} is not installed')
    processes = []
    logs = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<title>Browser Selector routing test</title>')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='browser-selector-smoke-') as temp:
        base = Path(temp)
        try:
            for index in range(2):
                root = base / f'data-{index}'
                root.mkdir()
                profile = 'Default' if index == 0 else 'Profile 1'
                (root / profile).mkdir()
                log = (base / f'chrome-{index}.log').open('w')
                logs.append(log)
                process = subprocess.Popen([chrome, '--ozone-platform=x11', '--disable-gpu', '--no-first-run',
                                             '--disable-background-networking', '--disable-extensions',
                                             '--no-default-browser-check', '--remote-debugging-port=0',
                                             f'--user-data-dir={root}', f'--profile-directory={profile}', 'about:blank'],
                                            stdout=log, stderr=log, start_new_session=True)
                processes.append(process)
                port_file = root / 'DevToolsActivePort'
                try:
                    port = wait_for(lambda: port_file.read_text().splitlines()[0] if port_file.exists() else None,
                                    'Chrome debugging endpoint did not start')
                except RuntimeError:
                    print((base / f'chrome-{index}.log').read_text(), file=sys.stderr)
                    raise
                token = f'http://127.0.0.1:{server.server_port}/?browser-selector-test={index}#preserved'
                choice = Choice(Browser('Chrome', (chrome, '--ozone-platform=x11'), 'chromium'), profile, root, profile)
                forwarded = launch(choice, [token])
                if forwarded.wait(timeout=15) != 0:
                    raise RuntimeError('Chrome rejected the forwarded URL')
                def tabs():
                    with urlopen(f'http://127.0.0.1:{port}/json', timeout=2) as response:
                        return json.load(response)
                try:
                    wait_for(lambda: any(tab.get('url') == token for tab in tabs()), 'URL was not routed to selected profile')
                except RuntimeError:
                    print(json.dumps(tabs()), file=sys.stderr)
                    print((base / f'chrome-{index}.log').read_text(), file=sys.stderr)
                    raise
                print(f'PASS: already-running {args.browser} profile {profile} received the intact URL')
            print('PASS: two independent profile instances routed correctly')
        finally:
            server.shutdown()
            server.server_close()
            import signal
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                # Reap any browser descendants still flushing profile files.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for log in logs:
                log.close()
            # Temporary profile cleanup can race browser helpers shutting down.
            for attempt in range(20):
                try:
                    shutil.rmtree(base)
                    break
                except FileNotFoundError:
                    break
                except OSError:
                    if attempt == 19:
                        raise
                    time.sleep(.1)


if __name__ == '__main__':
    main()
