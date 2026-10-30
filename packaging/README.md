# Downloadable application package

This builder creates a reproducible **Python application ZIP**, including the
Windows and Unix launchers and the universal WebSocket dependency wheel. Python
3.10+ must already be installed; it does not manufacture a Windows executable.

From a clean committed repository, run:

```bash
python packaging/build_bundle.py --wheel-dir /path/to/verified-wheel-cache \
  --output /workspace/downloads/MIKEIZU_TradeLab_PRO_Windows.zip
python packaging/build_bundle.py --verify-only /workspace/downloads/MIKEIZU_TradeLab_PRO_Windows.zip
python packaging/verify_install.py /workspace/downloads/MIKEIZU_TradeLab_PRO_Windows.zip \
  --report /tmp/mikeizu-package-install-check.json
```

If `--wheel-dir` is omitted, the builder asks pip to download wheels with
`--require-hashes` using the existing lock and normal TLS verification. An
unverified or extra wheel fails the build. Sources come from the Git index, read
at their current working-tree contents. A final build refuses uncommitted
changes. `--allow-dirty` is available only for an explicitly labelled
development preview; `RELEASE_INFO.json` records that state.

The archive contains no `.git` metadata, databases, `.env`, credentials, token
files or virtual environment. A strict source allowlist is applied even to Git
tracked files. File hashes, normalized ZIP timestamps, and a source-content hash
make byte-identical rebuilds possible from the same checkout, wheel and
Python/zlib toolchain. Windows-reserved filenames, traversal, symlinks and
case-colliding paths are rejected. The
manifest detects accidental corruption; it is not an independent signature.

The installation verifier creates a fresh extraction and virtual environment,
installs the supplied wheel with `--no-index --require-hashes`, then invokes the
current OS launcher in a folder whose name contains spaces. It checks frontend
assets, the complete technical strategy catalog, synthetic bar persistence, a synthetic
research report, and emergency-stop/block/resume behavior. No broker connection
or purchase is attempted. Temporary state and processes are cleaned up.
This check runs on the current OS.
It does not establish that a Windows launcher or executable was run on Linux.
