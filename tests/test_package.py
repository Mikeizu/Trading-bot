"""Release integrity/security tests; fixtures contain no application credentials."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1]/'packaging/build_bundle.py'
SPEC = importlib.util.spec_from_file_location('tradelab_bundle_builder', MODULE)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mikeizu-package-test-')
        self.root = Path(self.temporary.name)
        self.source = self.root/'source'
        self.source.mkdir()
        self.wheels = self.root/'wheels'
        self.wheels.mkdir()
        self.wheel = self.wheels/'fixture-1.0-py3-none-any.whl'
        self.wheel.write_bytes(b'deterministic wheel fixture; installation is tested separately')
        self.lock = ('fixture==1.0 --hash=sha256:'+bundle.digest(self.wheel.read_bytes())+'\n').encode()
        files = {
            'LICENSE': b'MIT fixture\n', 'README.md': b'# Package fixture\n',
            'requirements.lock': self.lock, 'requirements.txt': b'fixture==1.0\n',
            'START_WINDOWS.bat': b'@echo fixture\n', 'START_MAC_LINUX.sh': b'#!/bin/sh\ntrue\n',
            'deriv_server.py': b'# fixture\n', 'static/index.html': b'<!doctype html>\n',
            'docs/SAFE.md': b'No secrets in this fixture.\n',
            '.env.example': b'# empty nonsecret example\n',
            '.env': b'private fixture must never ship\n',
            'tradelab.db': b'private runtime fixture\n',
            'data/state.json': b'{"private":"fixture"}\n',
            'docs/credentials.json': b'{"private":"fixture"}\n',
            'docs/.env.production': b'private fixture\n',
        }
        for name, blob in files.items():
            path = self.source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        self.git('init', '-q')
        self.commit()
        self.output = self.root/'release.zip'

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.source), *arguments],
                              check=True, capture_output=True, text=True)

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Package Fixture', '-c', 'user.email=package-fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'Fixture state')

    def build(self):
        return bundle.build_bundle(self.source, self.output, self.wheels)

    def mutate_zip(self, change):
        original = self.root/'original.zip'
        self.output.replace(original)
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(self.output, 'w') as destination:
            for info in source.infolist():
                data = source.read(info.filename)
                replacement = change(info.filename, data)
                if replacement is not None:
                    destination.writestr(info, replacement)

    def test_build_is_reproducible_and_all_members_verify(self):
        first = self.build()
        saved = self.output.read_bytes()
        second = self.build()
        self.assertEqual(saved, self.output.read_bytes())
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertTrue(bundle.verify_bundle(self.output)['verified'])
        self.assertFalse(first['working_tree_changes_at_build'])
        self.assertEqual(self.output.with_suffix('.zip.sha256').read_text().split()[0], first['sha256'])

    def test_tracked_runtime_and_credentials_are_excluded(self):
        self.build()
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            self.assertIn(bundle.PREFIX+'/.env.example', names)
            for private in ('.env', 'tradelab.db', 'data/state.json',
                            'docs/credentials.json', 'docs/.env.production'):
                self.assertNotIn(bundle.PREFIX+'/'+private, names)
            self.assertIn(bundle.PREFIX+'/vendor/wheels/'+self.wheel.name, names)

    def test_dirty_sources_require_explicit_preview_flag(self):
        (self.source/'README.md').write_text('Uncommitted change\n')
        with self.assertRaisesRegex(ValueError, 'Commit the release'):
            self.build()
        info = bundle.build_bundle(self.source, self.output, self.wheels, allow_dirty=True)
        self.assertTrue(info['working_tree_changes_at_build'])

    def test_unverified_or_missing_wheel_is_rejected(self):
        self.wheel.write_bytes(b'changed fixture')
        with self.assertRaisesRegex(ValueError, 'not verified'):
            self.build()
        self.assertFalse(self.output.exists())
        self.wheel.unlink()
        with self.assertRaisesRegex(ValueError, 'No hash-verified'):
            self.build()

    def test_non_zip_output_cannot_overwrite_source(self):
        with self.assertRaisesRegex(ValueError, 'ZIP file'):
            bundle.build_bundle(self.source, self.source/'deriv_server.py', self.wheels)
        self.assertEqual((self.source/'deriv_server.py').read_bytes(), b'# fixture\n')

    def test_tracked_symlink_is_never_followed(self):
        target = self.root/'outside.md'
        target.write_text('outside source\n')
        try:
            (self.source/'docs/link.md').symlink_to(target)
        except OSError as exc:
            self.skipTest('Symlink creation unavailable: '+str(exc))
        self.commit()
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            self.build()

    def test_changed_member_is_detected(self):
        self.build()
        self.mutate_zip(lambda name, data: b'changed\n' if name.endswith('/README.md') else data)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            bundle.verify_bundle(self.output)

    def test_unmanifested_source_is_detected(self):
        self.build()
        with zipfile.ZipFile(self.output, 'a') as archive:
            archive.writestr(bundle.PREFIX+'/docs/extra.md', b'extra\n')
        with self.assertRaisesRegex(ValueError, 'unmanifested'):
            bundle.verify_bundle(self.output)

    def test_injected_runtime_file_is_rejected_before_manifest(self):
        self.build()
        with zipfile.ZipFile(self.output, 'a') as archive:
            archive.writestr(bundle.PREFIX+'/tradelab.db', b'private\n')
        with self.assertRaisesRegex(ValueError, 'Private or unexpected'):
            bundle.verify_bundle(self.output)

    def test_windows_ambiguous_and_traversal_names_are_rejected(self):
        for name in ('../evil.py', 'docs/CON.txt', 'docs/readme.md ', 'docs/a:b.py',
                     'docs/a\\b.py', 'docs/./foo.py', 'docs//foo.py', 'docs/line\nbreak.md'):
            with self.subTest(name=name):
                self.assertFalse(bundle.safe_relative(name))
                bad = self.root/'bad.zip'
                with zipfile.ZipFile(bad, 'w') as archive:
                    archive.writestr(bundle.PREFIX+'/'+name, b'bad\n')
                with self.assertRaises(ValueError):
                    bundle.verify_bundle(bad)

    def test_case_collisions_are_rejected(self):
        bad = self.root/'bad.zip'
        with zipfile.ZipFile(bad, 'w') as archive:
            archive.writestr(bundle.PREFIX+'/static/app.js', b'a\n')
            archive.writestr(bundle.PREFIX+'/static/App.js', b'b\n')
        with self.assertRaisesRegex(ValueError, 'case-colliding'):
            bundle.verify_bundle(bad)

    def test_archive_symlink_is_rejected(self):
        bad = self.root/'bad.zip'
        info = zipfile.ZipInfo(bundle.PREFIX+'/docs/link.md')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(bad, 'w') as archive:
            archive.writestr(info, '../outside\n')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            bundle.verify_bundle(bad)


if __name__ == '__main__':
    unittest.main()
