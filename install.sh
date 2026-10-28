#!/bin/bash
# Install the touch kiosk on Raspberry Pi OS Lite Bookworm or Trixie.
set -Eeuo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${PITAB_PYTHON:-python3}
SERVER=https://lwhittaker.net
SCALE=1.15
START=media
MODE=install
DRY_RUN=0
NO_START=0
APP=/opt/mnemerynne-pitab
CONF=/etc/mnemerynne-pitab
ACCOUNT=mnemerynne-pitab
UNIT=mnemerynne-pitab.service

usage() { # Explain the commands without making changes.
    cat <<'EOF'
Usage: sudo bash install.sh [https://lwhittaker.net] [options]
  --scale NUMBER       Browser scale, 1.0 to 2.0 (default 1.15)
  --start PAGE         media, remote, or home (default media)
  --dry-run            Validate settings and print the plan; change nothing
  --no-start           Install and enable for next boot, without starting now
  --check              Check the installed device and server
  --uninstall          Disable kiosk and restore tty1 console; keep settings/sign-in
EOF
}
die() { printf '%s\n' "$*" >&2; exit 1; } # Stop before continuing with an invalid operation.

while (($#)); do
    case "$1" in
        --scale|--start)
            (($# >= 2)) || die "Missing value for $1"
            if [[ $1 == --scale ]]; then SCALE=$2; else START=$2; fi
            shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-start) NO_START=1; shift ;;
        --check) MODE=check; shift ;;
        --uninstall) MODE=uninstall; shift ;;
        --help|-h) usage; exit 0 ;;
        --*) die "Unknown option: $1" ;;
        *) SERVER=$1; shift ;;
    esac
done

"$PYTHON" "$HERE/python/pitab.py" validate --server "$SERVER" --scale "$SCALE" --start "$START"
if [[ $DRY_RUN == 1 ]]; then
    printf 'Mode: %s\nServer: %s\nBrowser scale: %s\nStart page: %s\n' "$MODE" "$SERVER" "$SCALE" "$START"
    if [[ $MODE == install ]]; then
        printf '%s\n' 'Install labwc, Firefox, Squeekboard, Waybar, wtype and PipeWire with apt.' \
            "Create the dedicated $ACCOUNT account; copy source to $APP and configuration to $CONF." \
            "Enable $UNIT on tty1. Existing SSH and network configuration stay available."
        [[ $NO_START == 1 ]] || printf '%s\n' 'Start/restart the kiosk after installation.'
    else
        printf '%s\n' "Would run $MODE for $UNIT."
    fi
    exit 0
fi

[[ $(uname -s) == Linux ]] || die 'Run this installer on the Raspberry Pi, not Windows.'
[[ $EUID == 0 ]] || die 'Use sudo bash install.sh (or --dry-run without sudo).'

if [[ $MODE == uninstall ]]; then
    systemctl disable --now "$UNIT"
    systemctl start getty@tty1.service
    printf '%s\n' 'Kiosk disabled; tty1 console restored. Packages, configuration and Firefox sign-in are retained.'
    exit 0
fi
if [[ $MODE == check ]]; then
    failed=0
    systemctl --no-pager --full status "$UNIT" || failed=1
    for cmd in labwc waybar squeekboard wtype swaybg; do
        command -v "$cmd" || failed=1
    done
    if ! command -v firefox && ! command -v firefox-esr; then failed=1; fi
    /usr/bin/python3 "$APP/python/pitab.py" check-server || failed=1
    exit "$failed"
fi

# Refuse older OS images instead of attempting a distribution upgrade or installing Intel drivers.
. /etc/os-release
[[ ${ID:-} == raspbian || ${ID:-} == debian ]] || die 'This installer supports Raspberry Pi OS Lite.'
[[ ${VERSION_CODENAME:-} == bookworm || ${VERSION_CODENAME:-} == trixie ]] || \
    die 'Use Raspberry Pi OS Lite Bookworm or Trixie. This installer does not upgrade the OS.'
case $(dpkg --print-architecture) in arm64|armhf) ;; *) die 'Expected a Raspberry Pi ARM installation.' ;; esac
if systemctl is-active --quiet display-manager.service; then
    die 'A display manager is already running. This installer is for Lite without a desktop.'
fi

# First boot may share apt with OS provisioning. Wait for locks and retry temporary download errors.
export DEBIAN_FRONTEND=noninteractive
APT=(apt-get -o DPkg::Lock::Timeout=300 -o Acquire::Retries=5)
"${APT[@]}" -o APT::Update::Error-Mode=any update
FIREFOX=firefox-esr
if apt-cache policy firefox | grep -q 'Candidate: [0-9]'; then FIREFOX=firefox; fi
"${APT[@]}" install -y --no-install-recommends labwc "$FIREFOX" squeekboard waybar wtype swaybg \
    dbus-user-session libpam-systemd libglib2.0-bin python3 ca-certificates \
    fonts-dejavu-core fonts-noto-color-emoji pipewire-audio wlr-randr

if ! id "$ACCOUNT" >/dev/null 2>&1; then
    useradd --create-home --home-dir "/var/lib/$ACCOUNT" --shell /usr/sbin/nologin "$ACCOUNT"
fi
for group in video render input audio; do
    if getent group "$group" >/dev/null; then usermod -aG "$group" "$ACCOUNT"; fi
done

# Stop the old instance before replacing its files; its dedicated Firefox profile is preserved.
if systemctl is-active --quiet "$UNIT"; then systemctl stop "$UNIT"; fi
install -d -m 0755 "$APP/python" "$APP/assets" "$CONF"
if [[ $HERE != "$APP" ]]; then
    install -m 0644 "$HERE/python/pitab.py" "$APP/python/pitab.py"
    install -m 0644 "$HERE"/assets/*.css "$APP/assets/"
    install -m 0755 "$HERE/install.sh" "$APP/install.sh"
fi
/usr/bin/python3 "$APP/python/pitab.py" render --server "$SERVER" --scale "$SCALE" --start "$START" --output "$CONF"
install -m 0644 "$CONF/$UNIT" "/etc/systemd/system/$UNIT"
install -m 0644 "$CONF/pam" /etc/pam.d/mnemerynne-pitab
systemctl daemon-reload
systemctl enable "$UNIT"
if [[ $NO_START == 0 ]]; then systemctl restart "$UNIT"; fi
printf '%s\n' 'Installed. Sign in on the Pi, then choose Media or Remote from the touch bar.' \
    'Diagnostics: sudo bash /opt/mnemerynne-pitab/install.sh --check' \
    'Logs: journalctl -u mnemerynne-pitab -b'
