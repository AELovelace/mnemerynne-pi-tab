# Pi kiosk validation

## Portable checks

Run from the project root:

```sh
python3 -m unittest discover -s python -p 'test_*.py' -v
bash -n install.sh
bash -n firstboot.sh
bash install.sh https://lwhittaker.net --dry-run
bash firstboot.sh --dry-run
python3 python/pitab.py render --output .test-output/rendered
python3 python/build_package.py
```

On Windows, use `py -3.11` instead of `python3`. Git for Windows Bash can check the
shell script. For a dry run, set `PITAB_PYTHON` to the full Windows Python executable
path (forward slashes are accepted), and set `PITAB_BASH` to Git's `bash.exe` for a
first-boot dry run. No system installation occurs during a dry run.

Test SD-card staging on Windows, without a physical card:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ps/test-sdcard.ps1
```

The script creates isolated fake boot partitions under `.test-output/` and retains
them for inspection. It checks command insertion, blank/comment/multiline preservation,
indentless and empty lists, backup preservation, repeat staging, settings overrides,
UTF-8/LF, unchanged network/kernel config, -WhatIf, and rejecting unsupported input
before writing. It never enumerates, formats or writes a physical SD drive.

Automated tests cover valid/invalid origins, unusable scale values, configuration
formats, server-only CSS scope, the dedicated user/service, health failure and
redirect handling, keyboard visibility toggling, and graceful/hung-process shutdown.
First-boot tests check settings validation before subprocess launch, deferred service
startup and propagation of installer failure codes.
These checks do not claim to exercise apt, systemd, GPU, touch or Firefox on the Pi.

Development validation on 2026-10-27: all 12 portable Python tests and 12 PowerShell
SD-card staging scenarios passed. Git Bash accepted both shell scripts; the
first-boot dry run reached the regular installer with startup deferred. Generated
JSON and labwc XML parsed successfully, and generated Linux files use LF endings.

## Physical acceptance checklist — pending

- Confirm OS codename and actual screen resolution/orientation before installation.
- On a fresh cloud-init card customized by Imager, stage the package from Windows.
  Boot once and verify installation, the first-boot log and success marker, and the
  touchscreen sign-in page. Confirm Imager's user, hostname and network settings survive.
- For a deliberately failed first-boot setup, verify cloud-init reports the failure,
  the marker is absent, and the documented manual retry works after fixing the cause.
- After successful provisioning, reboot and verify setup is not repeated. Reinvoking
  firstboot.sh should also leave the completed installation alone.
- Install over SSH and verify tty1 opens the bar and Firefox without a desktop login.
- Check that the visible browser has no tab row or titlebar and fills the space below the bar.
- If the service log stops at the PAM session-open message, also read
  `sudo journalctl -b _UID="$(id -u mnemerynne-pitab)" --no-pager -n 100`.
  Session child-process messages may not appear under `journalctl -u mnemerynne-pitab`.
- Sign in using only touch. Type into username, password and search fields; show/hide
  Keyboard manually and confirm the focused field remains reachable by scrolling.
- Tap Media, Remote and Ask repeatedly, including from inside an embedded Remote app.
  Confirm navigation lands on the correct page and the URL is never typed into a form.
- Confirm Back and Reload work, and external links don't strand the user behind a hidden tab.
- In Media, select a paired TV in Play on; verify play/pause, volume and item selection
  affect that TV. Also verify This device plays on the Pi when selected.
- Open an authorized Remote resource and verify denied resources remain denied.
- Check layout at the screen's native resolution (targets: 800×480 / 1024×600), with
  and without the keyboard, and in both Erynne themes.
- Boot with server/network unavailable: verify the Offline bar is visible, then
  restore connectivity and verify the browser opens without intervention.
- Interrupt networking after login, restore it, and use Reload if needed; verify no
  automatic navigation discards ongoing work.
- Close Firefox; verify it restarts. Test Ctrl+Alt+R and Ctrl+Alt+K with a keyboard.
- Restart the service and reboot normally; verify sign-in persists as allowed by the server.
- Verify sound on the intended output; check media performance and temperature on the Pi.
- Run `sudo bash /opt/mnemerynne-pitab/install.sh --uninstall` and verify tty1 console
  and SSH access. Reinstall and confirm configuration/profile files remain usable.

The Pi is not connected to this development workspace. Device acceptance must be
completed on the hardware before treating this package as deployment-verified.
