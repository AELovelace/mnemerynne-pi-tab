"""Regression checks for installation safety, generated configuration and recovery."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import xml.etree.ElementTree as ET

import pitab


class ConfigurationTests(unittest.TestCase):
    def test_valid_origins(self):
        for supplied, expected in [('lwhittaker.net', 'https://lwhittaker.net'),
                                   ('https://LWHITTAKER.net/', 'https://lwhittaker.net'),
                                   ('http://192.168.1.5:38200', 'http://192.168.1.5:38200'),
                                   ('http://[::1]:38200', 'http://[::1]:38200')]:
            with self.subTest(supplied=supplied):
                self.assertEqual(pitab.clean_origin(supplied), expected)

    def test_rejects_unsafe_or_ambiguous_addresses(self):
        for value in ['https://user:password@host', 'https://host/media', 'https://host?x=1',
                      'https://host#x', 'https://host?', 'https://host:70000', 'https://host:0',
                      'https://host:', 'javascript:alert(1)', 'https://host\n', 'https://host;reboot',
                      'https://$(id)', 'https://host/../remote', 'https://host\\other', 'https://-bad']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pitab.clean_origin(value)

    def test_rejects_unusable_scaling_and_routes(self):
        for scale in [0, .5, 3, float('nan'), float('inf')]:
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                pitab.make_config('lwhittaker.net', scale, 'media')
        with self.assertRaises(ValueError):
            pitab.make_config('lwhittaker.net', 1.15, '/media/screen')

    def test_rendered_settings_and_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            config = pitab.make_config('lwhittaker.net', 1.15, 'remote')
            pitab.render(config, output)
            self.assertEqual(json.loads((output / 'config.json').read_text()), config)
            root = ET.parse(output / 'labwc/rc.xml').getroot()
            self.assertEqual(root.find('./windowRules/windowRule/action').attrib['name'], 'Maximize')
            bar = json.loads((output / 'waybar.json').read_text())
            self.assertTrue(bar['exclusive'])
            for name in ('media', 'remote', 'keyboard'):
                self.assertIn('action ' + name, bar['custom/' + name]['on-click'])
            css = (output / 'userContent.css').read_text()
            self.assertTrue(css.startswith('@-moz-document url-prefix("https://lwhittaker.net/")'))
            unit = (output / 'mnemerynne-pitab.service').read_text()
            self.assertIn('User=mnemerynne-pitab', unit)
            self.assertNotIn('User=root', unit)
            self.assertIn('Conflicts=getty@tty1.service', unit)
            self.assertTrue((output / 'labwc/autostart').read_text().endswith('labwc --exit\n'))
            for path in output.rglob('*'):
                if path.is_file():
                    self.assertNotIn(b'\r', path.read_bytes(), str(path))


class RuntimeTests(unittest.TestCase):
    def test_offline_and_non_success_are_not_healthy(self):
        opener = MagicMock()
        with patch('pitab.urllib.request.build_opener', return_value=opener):
            opener.open.side_effect = urllib.error.URLError('offline')
            self.assertFalse(pitab.server_ready('https://lwhittaker.net'))
            opener.open.side_effect = None
            response = opener.open.return_value.__enter__.return_value
            for status, expected in [(200, True), (302, False), (403, False), (503, False)]:
                response.status = status
                self.assertEqual(pitab.server_ready('https://lwhittaker.net'), expected)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://lwhittaker.net/healthz')

    def test_redirect_to_login_is_not_followed(self):
        self.assertIsNone(pitab.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other/'))

    def test_keyboard_toggle_reads_actual_state(self):
        for current, expected in [('(<true>,)', 'false'), ('(<false>,)', 'true')]:
            with self.subTest(current=current), patch('pitab.subprocess.run') as run:
                run.return_value.stdout = current
                pitab.toggle_keyboard()
                self.assertEqual(run.call_args.args[0][-1], expected)
                self.assertTrue(run.call_args.kwargs['check'])

    def test_stopping_browser_waits_for_profile_flush(self):
        process = MagicMock()
        process.poll.return_value = None
        pitab.stop_process(process)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=8)
        process.kill.assert_not_called()

    def test_hung_browser_is_killed_after_grace_period(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('firefox', 8), 0]
        pitab.stop_process(process)
        process.kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
