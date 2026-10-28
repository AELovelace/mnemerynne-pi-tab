# Contributing to the Pi kiosk

This workspace contains the Pi device package. The existing Mnemerynne server is
in `C:\Scripts\erinne` and was read as a reference; there are no server edits here.
Keep the Pi a client of its existing authenticated `/media`, `/remote`, and `/` pages.
Do not use the anonymous/paired `/media/screen` route for the controller.

## Structure

- `install.sh`: OS/package checks, dedicated user, installation, service and recovery.
- `ps/deploy-to-sdcard.ps1`: Windows staging onto an unbooted Imager boot partition;
  preserves existing cloud-config and inserts one runcmd entry.
- `firstboot.sh`, `firstboot.json`, `python/firstboot.py`: logged first-boot installation,
  validated settings, error propagation and success marker.
- `python/pitab.py`: strict settings validation, config rendering, process supervision,
  Squeekboard controls and local navigation. All subprocesses use argument lists.
- `assets/`: Firefox chrome, server-scoped touch CSS and native bar styling.
- `python/test_pitab.py`: portable configuration and recovery checks.
- `python/test_firstboot.py`, `ps/test-sdcard.ps1`: bootstrap failure handling and
  SD-card staging tests against isolated workspace fixtures.
- `python/build_package.py`: explicit archive allowlist; excludes profiles and caches.

All Python scripts belong in `python/`. Put any future PowerShell scripts in `ps/`.
Use LF line endings for Linux scripts. Add comments at OS integration points and
explain functions so maintainers can follow the hardware-facing behavior.

## Design decisions

labwc provides the Wayland session. Firefox is a maximized, undecorated browser with
hidden chrome, rather than exclusive fullscreen: the top bar and Squeekboard need
reserved space. Waybar invokes small fixed actions. wtype sends browser navigation
shortcuts to the active window. Squeekboard uses its session-bus `sm.puri.OSK0`
interface for manual visibility. The compositor session uses a dedicated D-Bus bus.

The server origin is validated before installation and encoded for JSON/CSS. Browser
touch CSS applies only to the selected origin, leaving embedded third-party apps to
their own styling. Authentication, CSRF, permissions and remote connections remain
the existing server's responsibility. Browser TLS verification remains enabled.

Firefox stores credentials only in its dedicated user profile; the device config
does not contain passwords. New windows are redirected into the current browser
window when Firefox supports that request. OS/browser updates remain managed by apt.

The process supervisor retries offline startup without requiring the network-online
target, restarts exited components, and gracefully terminates Firefox for recovery.
It deliberately does not reload an active browser merely because networking returned.
If the supervisor ends, the autostart wrapper exits labwc so systemd can restart it.

## First-boot staging

The reference is `C:\Scripts\pi-router`'s `deploy-to-sdcard.ps1` and `firstboot.sh`.
Our equivalent stages files into `/boot/firmware/mnemerynne-pitab` and appends a
cloud-init list-form command invoking Bash. It supports the ordinary Imager block
list forms, retaining indentation, comments and other top-level fields; unsupported
forms fail before staging. No YAML library or Python installation is required on
the Windows machine. PowerShell scripts stay under `ps/`.

Staging uses an explicit file allowlist, rejects reparse-point paths, never recursively
deletes a destination, writes UTF-8 without BOM/LF, and keeps the original user-data
backup. Test changes against blank lines, comments, multiline commands, indentless
lists, repeated staging and -WhatIf. Do not print user-data: it can contain credentials.

The first-boot wrapper preserves the installer's exit code and writes its completion
marker only after success. Installation passes `--no-start`, followed by an explicit
`systemctl --no-block start`, to avoid waiting for another unit during cloud-final.
apt runs noninteractively with lock waits and bounded download retries. Failed setup
is manually retryable without rerunning the rest of cloud-init; successful setup
is not run again. Network configuration remains Imager's responsibility.

## Before shipping

Run the portable tests and shell syntax/dry-run checks in TESTING_GUIDE.md. Inspect
the generated unit, labwc XML and Waybar JSON. Run the physical touch checklist when
changing focus handling, keyboard integration, browser chrome or CSS. A mocked
process test does not validate a real Wayland session or Pi graphics driver.

Build with `python3 python/build_package.py` (Windows: `py -3.11 python/build_package.py`).
Keep README.md and TESTING_GUIDE.md aligned with actual supported behavior. This is
a device project, so game editor, quest, dialogue and generation guides do not apply.
