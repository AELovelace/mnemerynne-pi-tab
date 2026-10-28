#!/usr/bin/env bash
# cloud-init invokes this from the boot partition; setup progress stays on the Pi.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${PITAB_PYTHON:-python3}

if [[ ${1:-} == --dry-run && $# == 1 ]]; then
    exec "$PYTHON" "$HERE/python/firstboot.py" --dry-run
fi
[[ $# == 0 ]] || { printf '%s\n' 'Usage: sudo bash firstboot.sh [--dry-run]' >&2; exit 1; }
[[ $EUID == 0 ]] || { printf '%s\n' 'First-boot setup must run as root.' >&2; exit 1; }

LOG=/var/log/mnemerynne-pitab-firstboot.log
STAMP=/var/lib/mnemerynne-pitab-firstboot.done
exec >>"$LOG" 2>&1
finish() { # Preserve the failing exit code so cloud-init reports an installation failure.
    local result=$?
    trap - EXIT
    printf '\n=== Pi kiosk setup finished with exit status %s: %s\n' "$result" "$(date -Is)"
    if ((result != 0)); then
        printf 'After fixing the problem, retry: sudo bash %s/firstboot.sh\n' "$HERE"
    fi
    exit "$result"
}
trap finish EXIT
printf '\n=== Pi kiosk first boot: %s\n' "$(date -Is)"
if [[ -f $STAMP ]]; then
    printf '%s\n' 'Setup already completed; leaving the existing installation alone.'
    exit 0
fi

# Imager configures Wi-Fi or Ethernet. Wait for either, without altering its network setup.
if command -v nm-online >/dev/null 2>&1; then
    if ! nm-online --quiet --timeout=180; then
        printf '%s\n' 'Network wait timed out; apt will retry downloads and report any remaining problem.'
    fi
fi
"$PYTHON" "$HERE/python/firstboot.py"

# Queue startup without blocking cloud-final on another unit in the same boot transaction.
systemctl --no-block start mnemerynne-pitab.service
date -Is >"$STAMP"                       # Only successful installation and startup scheduling mark completion.
printf '%s\n' 'Installation complete; kiosk startup queued. Sign in on the touchscreen when it opens.'
