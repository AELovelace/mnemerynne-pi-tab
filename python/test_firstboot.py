"""Check boot-partition settings and error propagation without touching the host OS."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import firstboot


class FirstBootTests(unittest.TestCase):
    def test_valid_settings_defer_service_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'firstboot.json').write_text(json.dumps(
                {'server': 'lwhittaker.net', 'scale': 1.25, 'start': 'remote'}))
            command = firstboot.installer_command(root)
            self.assertIn('https://lwhittaker.net', command)
            self.assertIn('--no-start', command)
            self.assertEqual(command[command.index('--start') + 1], 'remote')
            self.assertIn('--dry-run', firstboot.installer_command(root, dry_run=True))

    def test_invalid_boot_config_never_launches_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'firstboot.json').write_text(json.dumps(
                {'server': 'https://host;reboot', 'scale': 1.15, 'start': 'media'}))
            with patch.object(firstboot, 'SOURCE', root), patch('sys.argv', ['firstboot.py']), \
                    patch('firstboot.subprocess.run') as run:
                self.assertEqual(firstboot.main(), 1)
                run.assert_not_called()

    def test_failure_status_is_preserved(self):
        with patch('firstboot.installer_command', return_value=['bash', 'install.sh']), \
                patch('firstboot.subprocess.run') as run, patch('sys.argv', ['firstboot.py']):
            run.return_value.returncode = 42
            self.assertEqual(firstboot.main(), 42)
            self.assertFalse(run.call_args.kwargs['check'])
            self.assertNotIn('shell', run.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
