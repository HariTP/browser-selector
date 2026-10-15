import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from browser_selector.core import Browser, Choice, choices_for, desktop_command, discover_linux, host_environment, launch, launch_command, validate_url


class CoreTests(unittest.TestCase):
    def test_frozen_launch_restores_system_library_environment(self):
        import sys
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {
            'LD_LIBRARY_PATH': '/bundled/lib', 'LD_LIBRARY_PATH_ORIG': '/host/lib',
            'QT_PLUGIN_PATH': '/bundled/qt', 'QT_QPA_PLATFORM_PLUGIN_PATH': '/bundled/plugins'}):
            env = host_environment()
            self.assertEqual(env['LD_LIBRARY_PATH'], '/host/lib')
            self.assertNotIn('QT_PLUGIN_PATH', env)
            self.assertNotIn('QT_QPA_PLATFORM_PLUGIN_PATH', env)

    def test_url_validation_preserves_callback(self):
        url = 'https://example.com/callback?token=a%2Fb&next=x#fragment'
        self.assertEqual(validate_url(url), url)
        for bad in ('file:///etc/passwd', '--incognito', 'https://', 'https://x:bad', 'https://x\n--flag', 'javascript:alert(1)'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_url(bad)

    def test_desktop_field_codes_and_flatpak(self):
        self.assertEqual(desktop_command('"/a path/chrome" %U %%', 'Chrome', '', Path('/x')), ('/a path/chrome', '%'))
        self.assertEqual(desktop_command('flatpak run --file-forwarding com.google.Chrome @@u %U @@', 'Chrome', '', Path('/x')),
                         ('flatpak', 'run', 'com.google.Chrome'))
        with self.assertRaises(ValueError):
            desktop_command('sh -c "chrome %u"', '', '', Path('/x'))

    def test_chromium_profiles_missing_stale_and_malformed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'Default').mkdir()
            (root / 'Profile 1').mkdir()
            (root / 'Profile 1/Preferences').write_text('{"profile":{"name":"Work"}}')
            (root / 'Local State').write_text(json.dumps({'profile': {'info_cache': {'Default': {'name': 'Personal'}, 'deleted': {}, '../escape': {}}}}))
            browser = Browser('Chrome', ('/usr/bin/chrome',), 'chromium', (root,))
            choices = choices_for(browser)
            self.assertEqual([c.name for c in choices], ['Browser default', 'Personal', 'Work'])
            command = launch_command(choices[2], ['https://example.com'])
            self.assertIn('--profile-directory=Profile 1', command)
            self.assertIn(f'--user-data-dir={root}', command)
            (root / 'Local State').write_text('{"profile":null}')
            self.assertEqual(len(choices_for(browser)), 2)
            (root / 'Profile 1').rename(root / 'gone')
            with self.assertRaises(ValueError):
                launch_command(choices[2], ['https://example.com'])

    def test_firefox_absolute_and_relative_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'work').mkdir()
            (root / 'profiles.ini').write_text('[Profile0]\nName=Work\nPath=work\nIsRelative=1\n'
                                               '[Profile1]\nName=Personal\nPath=' + str(root / 'work') + '\nIsRelative=0\n')
            browser = Browser('Firefox', ('firefox',), 'firefox', (root,))
            choices = choices_for(browser)
            self.assertEqual(len(choices), 3)
            self.assertEqual(launch_command(choices[1], ['https://example.com']),
                             ['firefox', '-profile', str(root / 'work'), 'https://example.com'])

    def test_discovery_user_override_dedup_and_self_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            user = home / 'user/applications'
            system = home / 'system/applications'
            user.mkdir(parents=True)
            system.mkdir(parents=True)
            header = '[Desktop Entry]\nType=Application\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n'
            (user / 'override.desktop').write_text(header + 'Hidden=true\n')
            (system / 'override.desktop').write_text(header + 'Name=Hidden browser\nExec=/bin/true %U\n')
            for name in ('one.desktop', 'two.desktop'):
                (user / name).write_text(header + 'Name=Test Chrome\nExec=/bin/true %U\n')
            (user / 'self.desktop').write_text(header + 'Name=Browser Selector\nExec=/bin/true -m browser_selector.app %U\n')
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(home / 'user'), 'XDG_DATA_DIRS': str(home / 'system')}):
                result = discover_linux(home, [user, system])
            self.assertEqual([b.name for b in result], ['Test Chrome'])

    def test_launch_passes_url_as_one_argument_without_shell(self):
        url = 'https://example.com/?q=$(touch%20/tmp/no)&a="x"'
        with patch('browser_selector.core.subprocess.Popen') as process:
            process.return_value.wait.return_value = 0
            launch(Choice(Browser('Test', ('browser',))), [url])
        self.assertEqual(process.call_args.args[0], ['browser', url])
        self.assertNotIn('shell', process.call_args.kwargs)

    def test_browser_rejection_is_reported(self):
        with patch('browser_selector.core.subprocess.Popen') as process:
            process.return_value.wait.return_value = 1
            with self.assertRaises(OSError):
                launch(Choice(Browser('Test', ('browser',))), ['https://example.com'])

    def test_macos_profile_launch_uses_bundle_executable(self):
        import plistlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / 'Chrome.app'
            (bundle / 'Contents').mkdir(parents=True)
            (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Chrome'}))
            (root / 'Default').mkdir()
            choice = Choice(Browser('Chrome', ('/usr/bin/open', '-a', str(bundle)), 'chromium'), 'Personal', root, 'Default')
            command = launch_command(choice, ['https://example.com'], platform='darwin')
            self.assertEqual(command[0], str(bundle / 'Contents/MacOS/Chrome'))


if __name__ == '__main__':
    unittest.main()
