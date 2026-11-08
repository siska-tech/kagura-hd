#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the selected demo artifact, frozen build inputs and current FPGA sources."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
release = root / 'releases/pcm-stream-qspi'  # selected 2026-11-08; pcm2-qspi-final superseded


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    metadata = json.loads((release / 'manifest.json').read_text(encoding='utf-8'))
    artifact = release / metadata['artifact']
    assert sha(artifact) == metadata['sha256'], 'Selected artifact changed'
    assert artifact.stat().st_size == metadata['size_bytes'], 'Artifact size changed'
    listed = set()
    for line in (release / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert name not in listed, f'Duplicate checksum: {name}'
        listed.add(name)
        assert sha(release / name) == digest, name
    actual = {p.relative_to(release).as_posix() for p in release.rglob('*')
              if p.is_file() and p.name != 'SHA256SUMS'}
    assert listed == actual, 'Package file inventory differs from SHA256SUMS'
    sources = json.loads((release / 'source-input-manifest.json').read_text())
    for name, digest in sources.items():
        assert sha(release / 'build-inputs' / name) == digest, name
        if name.startswith(('rtl/', 'boards/', 'third_party/')):
            assert (root / name).read_bytes().replace(b'\r\n', b'\n') == (release / 'build-inputs' / name).read_bytes().replace(b'\r\n', b'\n'), f'Current source differs: {name}'
    catalog = json.loads((root / 'releases/candidates.json').read_text(encoding='utf-8'))
    for name in catalog['release_assets']:
        if name.endswith('.fs'):
            path = (root / 'releases' / name).resolve()
            assert path.is_relative_to(root / 'artifacts/validated'), 'Experimental release asset'
    experimental = root / 'artifacts/experimental/spi-sta-fail'
    assert (experimental / 'DO_NOT_PROGRAM.txt').read_text().startswith('DO NOT PROGRAM')
    assert catalog['spi']['status'] == 'quarantined_sta_fail'
    for line in (experimental / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert sha(experimental / name) == digest, name
    print(f'PASS: selected bitstream, package checksums and {len(sources)} frozen inputs')


if __name__ == '__main__':
    main()
