import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux desktop registration')
class RegistrationTests(unittest.TestCase):
    def test_register_default_restore_in_isolated_xdg_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data, config = root / 'data', root / 'config'
            config.mkdir()
            env = dict(os.environ, XDG_DATA_HOME=str(data), XDG_CONFIG_HOME=str(config),
                       XDG_CURRENT_DESKTOP='', DE='generic')
            script = Path(__file__).resolve().parents[1] / 'scripts/register_linux.py'
            def run(*args):
                return subprocess.run([sys.executable, str(script), *args], env=env, text=True, capture_output=True, check=True)
            def query():
                return subprocess.check_output(['xdg-mime', 'query', 'default', 'x-scheme-handler/https'], env=env, text=True).strip()
            before = query()
            run('--default')
            desktop = (data / 'applications/browser-selector.desktop').read_text()
            self.assertIn('Exec="', desktop)
            self.assertEqual(query(), 'browser-selector.desktop')
            backup = data / 'browser-selector/previous-defaults.json'
            original = backup.read_text()
            run('--default')
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(json.loads(original)['x-scheme-handler/https'], before)
            run('--restore')
            self.assertEqual(query(), before)


if __name__ == '__main__':
    unittest.main()
