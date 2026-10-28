#!/usr/bin/env python3
"""Render and run the Pi touch kiosk; uses only Python's standard library."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

SOURCE = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path('/etc/mnemerynne-pitab')
INSTALL_DIR = Path('/opt/mnemerynne-pitab')
USER = 'mnemerynne-pitab'
ROUTES = {'media': '/media', 'remote': '/remote', 'home': '/'}


def clean_origin(value: str) -> str:
    """Accept only an HTTP(S) server origin, never credentials or a command fragment."""
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('The server address must not contain whitespace.')
    if '://' not in value:
        value = 'https://' + value  # A bare hostname uses verified HTTPS by default.
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http', 'https') or parsed.username is not None or parsed.password is not None:
        raise ValueError('Use an http:// or https:// address without a username or password.')
    if parsed.path not in ('', '/') or parsed.query or parsed.fragment or '?' in value or '#' in value:
        raise ValueError('Give only the server address, without a page path, query, or fragment.')
    host = parsed.hostname
    if not host or '%' in host:
        raise ValueError('The server needs a valid hostname or IP address.')
    try:
        address = ipaddress.ip_address(host)
        host = '[' + str(address) + ']' if address.version == 6 else str(address)
    except ValueError:
        host = host.encode('idna').decode('ascii').lower()
        if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                                     for label in host.split('.')):
            raise ValueError('The server hostname is not valid.') from None
    port = parsed.port  # urlsplit checks that the port is numeric and within range.
    if port == 0 or parsed.netloc.endswith(':'):
        raise ValueError('The server port must be between 1 and 65535.')
    return f'{parsed.scheme}://{host}' + (f':{port}' if port else '')


def make_config(server: str, scale: float, start: str) -> dict:
    """Validate user options before the installer changes any system files."""
    if not 1.0 <= scale <= 2.0:
        raise ValueError('Scale must be between 1.0 and 2.0.')
    if start not in ROUTES:
        raise ValueError('Start page must be media, remote, or home.')
    return {'server': clean_origin(server), 'scale': scale, 'start': start}


def read_config() -> dict:
    """Read only the three supported settings from the installed JSON file."""
    raw = json.loads((CONFIG_DIR / 'config.json').read_text(encoding='utf-8'))
    return make_config(raw['server'], float(raw['scale']), raw['start'])


def render(config: dict, destination: Path) -> None:
    """Write device configuration; this can also render into a temporary review folder."""
    def write(relative: str, content: str) -> None:
        target = destination / relative  # All relative names below are fixed by this program.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')

    command = f'/usr/bin/python3 {INSTALL_DIR}/python/pitab.py'
    write('config.json', json.dumps(config, indent=2) + '\n')
    write('labwc/autostart', f'#!/bin/sh\n{command} run\nlabwc --exit\n')
    write('labwc/environment', 'MOZ_ENABLE_WAYLAND=1\nGTK_IM_MODULE=wayland\nXDG_CURRENT_DESKTOP=labwc\n')
    write('labwc/rc.xml', f'''<?xml version="1.0"?>
<labwc_config>
  <core><decoration>server</decoration></core>
  <theme><cornerRadius>0</cornerRadius></theme>
  <keyboard>
    <!-- Recovery and keyboard controls remain available with a physical keyboard. -->
    <keybind key="C-A-r"><action name="Execute" command="{escape(command)} action restart" /></keybind>
    <keybind key="C-A-k"><action name="Execute" command="{escape(command)} action keyboard" /></keybind>
  </keyboard>
  <windowRules>
    <windowRule identifier="firefox*" serverDecoration="no">
      <action name="Maximize" />
    </windowRule>
  </windowRules>
</labwc_config>
''')
    bar = {'layer': 'top', 'position': 'top', 'height': 52, 'exclusive': True,
           'modules-left': [f'custom/{key}' for key in ('media', 'remote', 'home', 'back', 'reload', 'keyboard')],
           'modules-right': ['custom/status']}
    for key, label in [('media', 'Media'), ('remote', 'Remote'), ('home', 'Ask'),
                       ('back', 'Back'), ('reload', 'Reload'), ('keyboard', 'Keyboard')]:
        bar[f'custom/{key}'] = {'format': label, 'tooltip': False, 'on-click': f'{command} action {key}'}
    bar['custom/status'] = {'exec': f'{command} status', 'return-type': 'json', 'interval': 10}
    write('waybar.json', json.dumps(bar, indent=2) + '\n')
    write('bar.css', (SOURCE / 'assets/bar.css').read_text(encoding='utf-8'))
    preferences = {
        'toolkit.legacyUserProfileCustomizations.stylesheets': True,
        'layout.css.devPixelsPerPx': str(config['scale']),
        'browser.tabs.inTitlebar': 0,
        'browser.link.open_newwindow': 1,
        'browser.link.open_newwindow.restriction': 0,
        'browser.sessionstore.resume_from_crash': False,
        'browser.shell.checkDefaultBrowser': False,
        'browser.aboutwelcome.enabled': False,
        'browser.startup.homepage_override.mstone': 'ignore',
        'browser.startup.page': 0,
        'browser.translations.automaticallyPopup': False,
        'datareporting.policy.dataSubmissionEnabled': False,
        'signon.rememberSignons': False,
        'browser.backspace_action': 2,  # Backspace must edit text, not leave the page.
        'full-screen-api.enabled': False,  # Keep the device controls available during media playback.
    }
    write('user.js', '// Device preferences, copied into the dedicated profile at startup.\n' +
          ''.join(f'user_pref({json.dumps(k)}, {json.dumps(v)});\n' for k, v in preferences.items()))
    write('userChrome.css', (SOURCE / 'assets/userChrome.css').read_text(encoding='utf-8'))
    touch = (SOURCE / 'assets/touch.css').read_text(encoding='utf-8')
    write('userContent.css', f'@-moz-document url-prefix({json.dumps(config["server"] + "/")}) {{\n{touch}\n}}\n')
    write('mnemerynne-pitab.service', f'''[Unit]
Description=Mnemerynne Pi touchscreen kiosk
After=systemd-user-sessions.service systemd-logind.service dbus.socket getty@tty1.service
Wants=systemd-logind.service dbus.socket
Conflicts=getty@tty1.service
ConditionPathExists=/dev/tty1
StartLimitIntervalSec=0

[Service]
Type=simple
User={USER}
PAMName=mnemerynne-pitab
WorkingDirectory=/var/lib/{USER}
ExecStart=/usr/bin/dbus-run-session -- /usr/bin/labwc -C {CONFIG_DIR}/labwc
Restart=always
RestartSec=5
TimeoutStopSec=20
UMask=0077
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardInput=tty-fail
StandardOutput=journal
StandardError=journal
UtmpIdentifier=tty1
UtmpMode=user
Environment=XDG_SESSION_TYPE=wayland
Environment=MOZ_ENABLE_WAYLAND=1

[Install]
WantedBy=multi-user.target
''')
    write('pam', '# A dedicated local graphical session; no desktop auto-login is required.\n'
          'auth required pam_unix.so\naccount required pam_unix.so\n'
          'session required pam_loginuid.so\nsession required pam_unix.so\nsession required pam_systemd.so\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # A redirect to a login portal must not count as a healthy server.


def server_ready(server: str) -> bool:
    """Check the existing health endpoint, keeping normal TLS certificate verification."""
    request = urllib.request.Request(server + '/healthz', headers={'User-Agent': 'Mnemerynne-PiTab/1'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=4) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False  # Offline startup retries rather than opening an unhelpful browser error page.


def runtime_dir() -> Path:
    """Keep command coordination inside the logged-in user's private runtime directory."""
    path = Path(os.environ['XDG_RUNTIME_DIR']) / 'mnemerynne-pitab'
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def toggle_keyboard() -> None:
    """Read Squeekboard's actual visibility, then show or hide it over the session bus."""
    base = ['gdbus', 'call', '--session', '--dest', 'sm.puri.OSK0', '--object-path', '/sm/puri/OSK0']
    state = subprocess.run(base + ['--method', 'org.freedesktop.DBus.Properties.Get', 'sm.puri.OSK0', 'Visible'],
                           check=True, capture_output=True, text=True, timeout=5).stdout
    show = 'false' if re.search(r'\btrue\b', state) else 'true'
    subprocess.run(base + ['--method', 'sm.puri.OSK0.SetVisible', show], check=True, timeout=5)


def action(name: str, config: dict) -> None:
    """Translate a touch-bar action into a bounded local desktop operation."""
    import fcntl  # Linux only; rendering and configuration tests also run on Windows.

    with (runtime_dir() / 'action.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # Ignore overlapping taps so one URL cannot be typed into another.
        if name == 'keyboard':
            toggle_keyboard()
        elif name == 'restart':
            (runtime_dir() / 'restart').touch()  # The supervisor owns its browser process and restarts it.
        elif name in ROUTES:
            url = config['server'] + ROUTES[name]
            subprocess.run(['wtype', '-M', 'ctrl', '-k', 'l', '-m', 'ctrl', '-s', '150', url],
                           check=True, timeout=5)
            subprocess.run(['wtype', '-k', 'Return'], check=True, timeout=5)
        elif name in ('back', 'reload'):
            keys = ['-M', 'alt', '-k', 'Left', '-m', 'alt'] if name == 'back' else ['-k', 'F5']
            subprocess.run(['wtype', *keys], check=True, timeout=5)
        else:
            raise ValueError('Unknown device action.')


def stop_process(process: subprocess.Popen) -> None:
    """Give a managed program time to save its state before forced termination."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_session(config: dict) -> None:
    """Supervise the touch bar, keyboard and browser inside the labwc login session."""
    profile = Path.home() / 'firefox'
    profile.mkdir(mode=0o700, exist_ok=True)
    (profile / 'chrome').mkdir(mode=0o700, exist_ok=True)
    for name in ('user.js', 'userChrome.css', 'userContent.css'):
        target = profile / name if name == 'user.js' else profile / 'chrome' / name
        shutil.copyfile(CONFIG_DIR / name, target)  # Existing sign-in cookies remain in the dedicated profile.
    browser = shutil.which('firefox') or shutil.which('firefox-esr')
    if not browser:
        raise RuntimeError('Firefox is missing. Run the installer again.')
    commands = {
        'bar': ['waybar', '-c', str(CONFIG_DIR / 'waybar.json'), '-s', str(CONFIG_DIR / 'bar.css')],
        'keyboard': ['squeekboard'],
        'background': ['swaybg', '-c', '#12031f'],
    }
    children: dict[str, subprocess.Popen] = {}
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True  # The finally block shuts down every child on service stop.

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    restart = runtime_dir() / 'restart'
    restart.unlink(missing_ok=True)
    try:
        while not stopping:
            for name, argv in commands.items():
                if name not in children or children[name].poll() is not None:
                    children[name] = subprocess.Popen(argv)
            if restart.exists():
                restart.unlink(missing_ok=True)
                if 'browser' in children:
                    stop_process(children.pop('browser'))
            if 'browser' not in children or children['browser'].poll() is not None:
                if server_ready(config['server']):
                    children['browser'] = subprocess.Popen(
                        [browser, '--no-remote', '--profile', str(profile), '--new-window',
                         config['server'] + ROUTES[config['start']]])
                else:
                    print('Waiting for the Mnemerynne server; retrying in five seconds.', flush=True)
            time.sleep(5)
    finally:
        for process in children.values():
            stop_process(process)


def main() -> int:
    """Expose the install, diagnostic and desktop entry points without shell evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'render'):
        child = sub.add_parser(name)
        child.add_argument('--server', default='https://lwhittaker.net')
        child.add_argument('--scale', type=float, default=1.15)
        child.add_argument('--start', choices=ROUTES, default='media')
        if name == 'render':
            child.add_argument('--output', type=Path, required=True)
    sub.add_parser('run')
    sub.add_parser('status')
    sub.add_parser('check-server')
    child = sub.add_parser('action')
    child.add_argument('name', choices=[*ROUTES, 'back', 'reload', 'keyboard', 'restart'])
    args = parser.parse_args()
    try:
        if args.command in ('validate', 'render'):
            config = make_config(args.server, args.scale, args.start)
            if args.command == 'render':
                render(config, args.output)
            else:
                print(json.dumps(config))
            return 0
        config = read_config()
        if args.command == 'run':
            run_session(config)
        elif args.command == 'action':
            action(args.name, config)
        else:
            online = server_ready(config['server'])
            if args.command == 'status':
                print(json.dumps({'text': 'Online' if online else 'Offline', 'class': 'online' if online else 'offline',
                                  'tooltip': 'Server reachable' if online else 'Waiting for server /healthz; check Wi-Fi and server address.'}))
            else:
                print('Server health endpoint: ' + ('OK' if online else 'unreachable or not HTTP 200'))
                return 0 if online else 1
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(f'Pi kiosk: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
