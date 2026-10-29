#!/usr/bin/env python3
"""Build a reproducible, verified Python application ZIP with offline wheels.

The source selection comes from Git's index. Final builds require a clean
checkout. This is a Python application distribution, not a standalone .exe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
import zipfile

PREFIX = 'MIKEIZU_TradeLab_PRO'
DENIED_PARTS = {'.git', '.venv', 'venv', '__pycache__', '.cache', '.pytest_cache',
                'node_modules', 'data', 'dist', 'test-results', 'playwright-report'}
DENIED_SUFFIXES = {'.db', '.db-shm', '.db-wal', '.pyc', '.pyo', '.token', '.log',
                   '.sqlite', '.sqlite3', '.zip', '.p12', '.pfx', '.key', '.pem'}
ROOT_FILES = {'LICENSE', 'README.md', 'DOWNLOAD_README.txt', 'requirements.txt',
              'requirements.lock', '.python-version', '.env.example',
              'START_WINDOWS.bat', 'START_MAC_LINUX.sh', '.gitignore'}
SOURCE_DIRS = {'static', 'docs', 'tests', 'packaging', '.github'}
WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1, 10)),
                    *('LPT'+str(n) for n in range(1, 10))}


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def safe_relative(name: str) -> bool:
    """Reject traversal and ambiguous names on Windows as well as POSIX."""
    path = PurePosixPath(name)
    return bool(name and path.as_posix() == name and not path.is_absolute() and not any(ord(c) < 32 for c in name)
                and '\\' not in name and ':' not in name
                and all(part not in ('.', '..', '') and not part.endswith((' ', '.'))
                        and part.split('.')[0].upper() not in WINDOWS_RESERVED
                        for part in path.parts))


def selected_path(name: str) -> bool:
    """An allowlist plus private-file exclusions, applied to indexed paths."""
    path = PurePosixPath(name)
    if not safe_relative(name) or any(part in DENIED_PARTS for part in path.parts):
        return False
    low = path.name.lower()
    if (low == '.env' or (low.startswith('.env.') and name != '.env.example')
            or low.startswith(('credentials', 'secret', 'token'))):
        return False
    if any(low.endswith(suffix) for suffix in DENIED_SUFFIXES):
        return False
    if name in ROOT_FILES:
        return True
    if len(path.parts) == 1:
        return path.suffix in {'.py', '.md'}
    return path.parts[0] in SOURCE_DIRS and path.suffix in {
        '.py', '.md', '.txt', '.cjs', '.js', '.css', '.html', '.svg',
        '.webmanifest', '.yml', '.yaml', '.json'}


def git_output(source: Path, *arguments: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(source), *arguments],
                                   stderr=subprocess.DEVNULL)


def source_files(source: Path) -> dict[str, bytes]:
    source = source.resolve()
    if git_output(source, 'ls-files', '--unmerged'):
        raise ValueError('Resolve Git merge conflicts before packaging')
    files: dict[str, bytes] = {}
    names = git_output(source, 'ls-files', '-z', '--cached').decode().split('\0')
    for name in sorted(filter(selected_path, names)):
        path = source / name
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError(f'Release source cannot contain symlinks: {name}')
        if not path.is_file():
            raise ValueError(f'Indexed release source is missing: {name}')
        files[name] = path.read_bytes()
    required = {'LICENSE', 'README.md', 'requirements.lock', 'START_WINDOWS.bat',
                'START_MAC_LINUX.sh', 'deriv_server.py', 'static/index.html'}
    if required - files.keys():
        raise ValueError('Required app files must be staged: ' + ', '.join(sorted(required - files.keys())))
    return files


def verified_wheels(directory: Path, lock: bytes) -> dict[str, bytes]:
    expected = {value.decode().lower() for value in
                re.findall(rb'--hash=sha256:([a-fA-F0-9]{64})', lock)}
    if not expected:
        raise ValueError('Dependency lock does not contain SHA-256 hashes')
    wheels = {}
    for path in sorted(directory.glob('*.whl')):
        if path.is_symlink():
            raise ValueError('Wheel cannot be a symlink')
        blob = path.read_bytes()
        if digest(blob) not in expected:
            raise ValueError(f'Wheel is not verified by requirements.lock: {path.name}')
        wheels['vendor/wheels/' + path.name] = blob
    if not wheels:
        raise ValueError('No hash-verified dependency wheels were supplied')
    return wheels


def build_bundle(source: Path, output: Path, wheels_dir: Path, *, allow_dirty=False) -> dict:
    source, output = source.resolve(), output.resolve()
    if output.suffix.lower() != '.zip':
        raise ValueError('The output must be a ZIP file')
    dirty = bool(git_output(source, 'status', '--porcelain=v1', '--untracked-files=all'))
    if dirty and not allow_dirty:
        raise ValueError('Commit the release first, or use --allow-dirty for a labelled development preview')
    files = source_files(source)
    source_hashes = {name: digest(blob) for name, blob in files.items()}
    source_digest = digest(json.dumps(source_hashes, sort_keys=True, separators=(',', ':')).encode())
    wheels = verified_wheels(wheels_dir, files['requirements.lock'])
    files.update(wheels)
    head = git_output(source, 'rev-parse', '--verify', 'HEAD').decode().strip()
    info = {
        'application': 'MIKEIZU TradeLab PRO', 'distribution': 'Python source application',
        'platforms': ['Windows', 'macOS', 'Linux'], 'python_requirement': 'Python 3.10+',
        'source_commit': head, 'working_tree_changes_at_build': dirty,
        'source_files_sha256': source_digest,
        'dependency_wheels': {name: digest(blob) for name, blob in wheels.items()},
        'live_execution': 'disabled',
        'note': 'No bundled Python runtime or standalone executable. Broker access is not proven by package validation.',
    }
    files['RELEASE_INFO.json'] = (json.dumps(info, indent=2, sort_keys=True) + '\n').encode()
    hashes = {name: digest(blob) for name, blob in files.items()}
    files['SHA256SUMS.txt'] = ''.join(f'{value}  {name}\n' for name, value in sorted(hashes.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.mikeizu-release-', suffix='.zip',
                                     dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, blob in sorted(files.items()):
                entry = zipfile.ZipInfo(PREFIX + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, blob, compresslevel=9)
        result = verify_bundle(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    result.update({'path': str(output), 'bytes': output.stat().st_size,
                   'sha256': digest(output.read_bytes()), 'source_commit': head})
    output.with_suffix(output.suffix + '.sha256').write_text(
        f"{result['sha256']}  {output.name}\n", encoding='ascii')
    return result


def verify_bundle(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) > 2000 or sum(item.file_size for item in archive.infolist()) > 50_000_000:
            raise ValueError('Unexpected release size')
        if len(names) != len({name.casefold() for name in names}):
            raise ValueError('Duplicate or case-colliding archive paths')
        for name in names:
            relative = PurePosixPath(name)
            if not safe_relative(name) or not relative.parts or relative.parts[0] != PREFIX:
                raise ValueError('Unsafe archive path')
            app_name = '/'.join(relative.parts[1:])
            generated = app_name in ('SHA256SUMS.txt', 'RELEASE_INFO.json')
            wheel = app_name.startswith('vendor/wheels/') and len(relative.parts) == 4 and app_name.endswith('.whl')
            if not (selected_path(app_name) or generated or wheel):
                raise ValueError('Private or unexpected archive member: ' + app_name)
            if (archive.getinfo(name).external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive contains a symlink')
        if archive.testzip() is not None:
            raise ValueError('Corrupt archive')
        root = PREFIX + '/'
        manifest_name = root + 'SHA256SUMS.txt'
        manifest = archive.read(manifest_name).decode('ascii')
        listed = set()
        for line in manifest.splitlines():
            expected, name = line.split('  ', 1)
            full = root + name
            if not re.fullmatch('[a-f0-9]{64}', expected) or full in listed:
                raise ValueError('Invalid checksum manifest')
            if digest(archive.read(full)) != expected:
                raise ValueError(f'Package checksum mismatch: {name}')
            listed.add(full)
        if listed | {manifest_name} != set(names):
            raise ValueError('Package contains unmanifested files')
        info = json.loads(archive.read(root + 'RELEASE_INFO.json'))
        allowed = {value.decode().lower() for value in re.findall(
            rb'--hash=sha256:([a-fA-F0-9]{64})', archive.read(root + 'requirements.lock'))}
        declared_wheels = info['dependency_wheels']
        actual_wheels = {name.removeprefix(root) for name in names
                         if name.startswith(root + 'vendor/wheels/') and name.endswith('.whl')}
        if not declared_wheels or set(declared_wheels) != actual_wheels:
            raise ValueError('Missing or undeclared offline dependency wheel')
        for name, expected in declared_wheels.items():
            if digest(archive.read(root + name)) != expected or expected not in allowed:
                raise ValueError('Dependency manifest mismatch')
        source_hashes = {name.removeprefix(root): digest(archive.read(name)) for name in names
                         if name not in {manifest_name, root + 'RELEASE_INFO.json'}
                         and not name.startswith(root + 'vendor/wheels/')}
        source_digest = digest(json.dumps(source_hashes, sort_keys=True, separators=(',', ':')).encode())
        if source_digest != info['source_files_sha256']:
            raise ValueError('Source content identity mismatch')
        return {'verified': True, 'files': len(names), 'source_commit': info['source_commit'],
                'working_tree_changes_at_build': info['working_tree_changes_at_build']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('/workspace/downloads/MIKEIZU_TradeLab_PRO_Windows.zip'))
    parser.add_argument('--wheel-dir', type=Path, help='Cached wheels; each wheel is checked against the lock')
    parser.add_argument('--verify-only', type=Path)
    parser.add_argument('--allow-dirty', action='store_true', help='Label a development preview; never use for a final release')
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_bundle(args.verify_only), sort_keys=True))
        return
    if args.wheel_dir:
        result = build_bundle(args.source, args.output, args.wheel_dir, allow_dirty=args.allow_dirty)
    else:
        with tempfile.TemporaryDirectory(prefix='mikeizu-release-wheels-') as temporary:
            directory = Path(temporary)
            subprocess.run([sys.executable, '-m', 'pip', 'download', '--require-hashes',
                            '--only-binary=:all:', '--no-deps', '-r',
                            str(args.source / 'requirements.lock'), '--dest', str(directory)], check=True)
            result = build_bundle(args.source, args.output, directory, allow_dirty=args.allow_dirty)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
