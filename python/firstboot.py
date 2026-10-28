#!/usr/bin/env python3
"""Validate the SD-card configuration and invoke the existing installer without a shell string."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from pitab import make_config

SOURCE = Path(__file__).resolve().parent.parent


def installer_command(source: Path, dry_run: bool = False) -> list[str]:
    """Build an argument list from validated JSON; boot-partition data is never sourced as shell code."""
    raw = json.loads((source / 'firstboot.json').read_text(encoding='utf-8'))
    config = make_config(raw['server'], float(raw['scale']), raw['start'])
    command = [os.environ.get('PITAB_BASH', 'bash'), str(source / 'install.sh'), config['server'], '--scale', str(config['scale']),
               '--start', config['start'], '--no-start']
    if dry_run:
        command.append('--dry-run')  # The dry-run path never writes logs or success markers on the Pi.
    return command


def main() -> int:
    """Forward installer failures unchanged so cloud-init and the first-boot log agree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        return subprocess.run(installer_command(SOURCE, args.dry_run), check=False).returncode
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'First-boot setup: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
