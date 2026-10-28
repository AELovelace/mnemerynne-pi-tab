"""Create the transfer archives from an explicit list of project files."""

from pathlib import Path
import tarfile
import zipfile


def main() -> None:
    """Package source and guides without caches, profiles, test output or credentials."""
    root = Path(__file__).resolve().parent.parent
    output = root / 'dist'
    output.mkdir(exist_ok=True)
    files = [root / name for name in ('install.sh', 'firstboot.sh', 'firstboot.json', 'README.md',
                                    'CONTRIBUTOR_GUIDE.md', 'TESTING_GUIDE.md')]
    files += sorted((root / 'assets').glob('*.css'))
    files += [root / 'python' / name for name in ('pitab.py', 'firstboot.py', 'test_pitab.py',
                                                'test_firstboot.py', 'build_package.py')]
    files += sorted((root / 'ps').glob('*.ps1'))
    with zipfile.ZipFile(output / 'mnemerynne-pitab.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'mnemerynne-pitab/' + path.relative_to(root).as_posix())
    with tarfile.open(output / 'mnemerynne-pitab.tar.gz', 'w:gz') as archive:
        for path in files:
            archive.add(path, arcname='mnemerynne-pitab/' + path.relative_to(root).as_posix())
    for name in ('mnemerynne-pitab.zip', 'mnemerynne-pitab.tar.gz'):
        print(output / name)  # Show the exact artifacts to transfer to the Pi.


if __name__ == '__main__':
    main()
