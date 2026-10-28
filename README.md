# Mnemerynne Pi touchscreen kiosk

A Raspberry Pi 4 Model B with a 7-inch touchscreen, running Raspberry Pi OS Lite,
opens **https://lwhittaker.net/media** at boot. A permanent touch bar provides
**Media · Remote · Ask · Back · Reload · Keyboard**. Media controls the existing
paired TVs; Remote opens the existing permitted network apps. Sign in with your
normal Mnemerynne account on the Pi. The server still enforces all permissions.

This package uses the live Erynne pages and their neon/sakura theme, with larger
touch targets and compact Media controls. Its device bar uses Erynne's neon colors.
It was prepared against `C:\Scripts\erinne`, reference commit `f456a6a`; it does not
need a new server endpoint, proxy, duplicated media implementation or server patch.

## Install on a freshly flashed SD card (no SSH needed)

This follows the `C:\Scripts\pi-router` preparation workflow: copy the package to
the card's boot partition, then append a command to Imager's cloud-init `runcmd` list.

1. Flash **Raspberry Pi OS Lite Trixie** using Raspberry Pi Imager, configuring the
   hostname, user, Wi-Fi and SSH. Use an image with `cmdline.txt` and a cloud-config
   `user-data` file on its `bootfs` partition. Raspberry Pi documents this
   [Imager/cloud-init format](https://www.raspberrypi.com/news/cloud-init-on-raspberry-pi-os/).
2. Before the card has ever booted, leave it connected to Windows. From this project
   directory, run the following, replacing **K:** with the card's **bootfs** drive:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\ps\deploy-to-sdcard.ps1 -Drive K:
   ```

   This execution-policy option applies only to that PowerShell process. To preview
   without changing the card, add `-WhatIf`. To customize the device, for example:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\ps\deploy-to-sdcard.ps1 -Drive K: -Server https://lwhittaker.net -Scale 1.25 -Start remote
   ```

3. Safely eject the card, insert it in the Pi, and power on. First boot waits for
   networking, downloads the graphical packages and installs the kiosk. Leave it
   powered while setup runs; the touchscreen opens the sign-in page when ready.

The stager preserves Imager's existing user/network settings and runcmd commands,
saves the original `user-data` as `user-data.mnemerynne-pitab.bak`, and copies only
the device's required files into `bootfs/mnemerynne-pitab/`. Repeating staging before
first boot updates the package/settings without adding a duplicate command. It never
formats the card or changes `cmdline.txt` or `network-config`.

Supported `runcmd` forms are a normal block list (including indentless lists), an
empty list `[]`, or no existing `runcmd`. Nonempty inline lists, duplicate keys and
non-cloud-config files are rejected before any writes. The original backup may be
restored manually on the unbooted card if needed.

The boot-partition settings are plain JSON (`mnemerynne-pitab/firstboot.json`), not
shell commands. The default server is **https://lwhittaker.net**, scale **1.15**, and
startup page **media**. The first-boot wrapper uses the existing installer and queues
the kiosk service without blocking cloud-init. It doesn't configure router/NAT or
Ethernet sharing; networking comes from Imager.

First-boot progress and recovery on the Pi:

```sh
sudo tail -f /var/log/mnemerynne-pitab-firstboot.log
cloud-init status --long
# After fixing a failed setup (for example Wi-Fi), retry only the kiosk installer:
sudo bash /boot/firmware/mnemerynne-pitab/firstboot.sh
```

Success creates `/var/lib/mnemerynne-pitab-firstboot.done`; later invocations leave
the completed installation alone. Failures preserve a nonzero exit status, do not
create the marker, and can be retried with the command above. This does not reset or
rerun Imager's user/network provisioning. After successful setup, use the regular
installer below for changes and updates.

**This SD-card path requires a fresh, unbooted cloud-init image.** It does not retrofit
first boot onto an already-running Pi or old `firstrun.sh` images. For those, use the
manual installation below if the installed OS version is supported.

## Install manually on a running Pi

Requires **Raspberry Pi OS Lite Bookworm or Trixie**, either ARM64 or ARMHF, with
working networking and touchscreen drivers. Check with `cat /etc/os-release`.
Older releases are rejected rather than upgraded. Keep SSH enabled for maintenance.
The installer installs the small graphical session needed by Lite; a full desktop
is not required. Internet access to the Pi's apt repositories is needed.

From Windows PowerShell, copy the packaged archive to your Pi, replacing
`YOUR_USER@YOUR_PI` with the Pi's SSH username and hostname or IP:

```powershell
scp "C:\mnemerynne pi-tab\dist\mnemerynne-pitab.tar.gz" YOUR_USER@YOUR_PI:~/
ssh YOUR_USER@YOUR_PI
```

Then, on the Pi:

```sh
tar -xzf mnemerynne-pitab.tar.gz
cd mnemerynne-pitab
bash install.sh https://lwhittaker.net --dry-run
sudo bash install.sh https://lwhittaker.net
```

The service starts immediately and on subsequent boots. It takes over tty1; SSH
continues to work. Before the server is reachable, the screen has a dark background
and the touch bar shows **Offline**. The browser opens when `/healthz` answers.
The installer doesn't change your network or boot/display configuration.

## Use it

1. Sign in on the Pi. Tap **Keyboard** if the keyboard does not appear automatically.
2. In **Media**, use **Screens** to pair a TV if needed, then choose the target in
   **Play on**. **This device** plays on the Pi itself. Choose a TV to control that TV.
3. Tap **Remote** for the network apps your account can access. Resources and their
   permissions are managed in the existing server's **Access → Remote** settings.
4. Tap **Ask** for the regular Erynne page. Use **Back** and **Reload** anywhere.
5. Use the existing Erynne menu for Files, Wiki, Preferences, and Sign out.

The Pi uses a normal signed-in browser, not the TV's `/media/screen` pairing identity.
Its dedicated profile retains sign-in until the server expires it or you sign out.
This is a personal controller with kiosk styling, not a hardened public kiosk.

## Display, keyboard and sound

The browser starts maximized with its tabs and toolbar hidden. A brief address-field
appearance during touch-bar navigation is expected. This preserves normal window
resizing when Squeekboard opens, instead of covering the bottom of a fullscreen page.
Web fullscreen is disabled so the device controls stay accessible. Links requesting
new windows normally open in the same window.

Default browser scale is **1.15**. The touch layout targets 800×480 and 1024×600
landscape screens without assuming a particular display driver or forcing resolution.
The screen model and native resolution still need checking on the physical Pi.
Change scale or the startup page by rerunning:

```sh
sudo bash /opt/mnemerynne-pitab/install.sh https://lwhittaker.net --scale 1.25 --start remote
```

Supported startup pages are `media`, `remote`, and `home`. Scale is 1.0–2.0.
Provide your desired options each time; omitted values return to the defaults.
Reconfiguration restarts the browser but preserves its profile. `--no-start`
installs and enables for the next boot without starting immediately (an existing
kiosk is stopped before its files are replaced).

Use the display manufacturer's Raspberry Pi OS instructions for orientation and
touch alignment. `wlr-randr` is installed for diagnosing output names and modes from
the graphical session. No Intel video drivers or forced hardware-decode flags are
used. PipeWire uses the system's default audio output; playback/codec performance
must be checked on the actual Pi.

## Maintenance and recovery

```sh
sudo bash /opt/mnemerynne-pitab/install.sh --check
journalctl -u mnemerynne-pitab -b --no-pager -n 100
sudo journalctl -b _UID="$(id -u mnemerynne-pitab)" --no-pager -n 100
sudo systemctl restart mnemerynne-pitab
```

If the service journal shows only a startup message and `pam_unix ... session opened`,
use the `_UID` command too: desktop child processes can be attributed to the login
session rather than the original service. An installation exit status of zero
confirms setup completed, but does not prove that the compositor or browser displayed.
For a blank screen, collect those logs along with:

```sh
sudo systemctl status mnemerynne-pitab --no-pager -l
ps -u mnemerynne-pitab -o pid,ppid,stat,args
```

Firefox, the keyboard and the touch bar are restarted if they exit. systemd restarts
the compositor/session if it exits. A running browser is not automatically refreshed
after a network interruption, to avoid discarding forms or Remote app work; tap
**Reload** if the page needs it. **Online** means the server health endpoint answers,
not that the current account has permission to every resource.

A physical keyboard can use **Ctrl+Alt+R** to restart Firefox, or **Ctrl+Alt+K** to
toggle the touch keyboard. Restarting may discard unsaved page work.

| Symptom | Check |
| --- | --- |
| Offline bar, no browser | Wi-Fi/DNS, system clock, TLS certificate, and `https://lwhittaker.net/healthz` from the Pi. Redirects and non-200 responses do not count as healthy. |
| Media or Remote unavailable | Sign in; confirm the account's server permissions and that the feature is enabled. |
| Keyboard doesn't appear automatically | Tap Keyboard; if that also fails, inspect the journal for Squeekboard errors. |
| Bar changes but page does not navigate | Inspect journal for wtype errors; confirm Firefox is the active window. |
| Browser controls unexpectedly visible | Restart the service after checking the dedicated profile's `user.js` and `chrome/` files. |
| Display or touch rotated incorrectly | Use the screen manufacturer's display and touch configuration for your OS. |
| Black display without the bar | Check service logs for labwc, seat access or display-driver failures. |

Apply OS/browser security updates through the normal Raspberry Pi OS apt workflow.
To update this package, copy a new release and rerun its installer with your options.

To return tty1 to the console:

```sh
sudo bash /opt/mnemerynne-pitab/install.sh --uninstall
```

This disables the kiosk and restores the console. It retains packages, configuration,
the dedicated account and browser profile, including sign-in cookies, for reinstall.

## Files on the Pi

| Path | Purpose |
| --- | --- |
| `/opt/mnemerynne-pitab/` | Installer, Python runtime, and CSS assets |
| `/etc/mnemerynne-pitab/` | Server/scale/start settings; generated labwc, bar and browser configuration |
| `/etc/systemd/system/mnemerynne-pitab.service` | Dedicated graphical session on tty1 |
| `/etc/pam.d/mnemerynne-pitab` | Login session for GPU and touch access |
| `/var/lib/mnemerynne-pitab/firefox/` | Dedicated browser profile and sign-in cookies |
| `/boot/firmware/mnemerynne-pitab/` | SD-card first-boot payload and `firstboot.json` settings |
| `/var/log/mnemerynne-pitab-firstboot.log` | First-boot package/install progress and final exit status |
| `/var/lib/mnemerynne-pitab-firstboot.done` | Successful first-boot installation marker |

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the validation performed and the remaining
physical-device checks. See [CONTRIBUTOR_GUIDE.md](CONTRIBUTOR_GUIDE.md) for architecture.

The OS keyboard approach follows [Raspberry Pi's Touch Display documentation](https://www.raspberrypi.com/documentation/accessories/display.html).
Session configuration follows the [labwc manual](https://labwc.github.io/labwc-config.5.html),
and the touch bar follows [Waybar's configuration documentation](https://github.com/Alexays/Waybar/wiki/Configuration).
