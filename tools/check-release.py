#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the release bitstreams, their packages, frozen build inputs and current FPGA sources.

QSPI and SPI are build-time exclusive configurations with independent packages:
releases/pcm-stream-qspi (selected 2026-11-08) and releases/pcm-stream-spi.
Each package is checked on its own; a failure names the package.
"""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
PACKAGES = {
    # name: (package, source prefixes compared with the working tree)
    'qspi': ('releases/pcm-stream-qspi', ('rtl/', 'boards/', 'third_party/')),
    'spi': ('releases/pcm-stream-spi', ('rtl/', 'boards/', 'third_party/', 'tools/build-fb.tcl')),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_text(a, b):
    return a.read_bytes().replace(b'\r\n', b'\n') == b.read_bytes().replace(b'\r\n', b'\n')


def check_package(name, relative, compared):
    release = root / relative
    def check(condition, message):
        assert condition, f'[{name}] {message}'
    metadata = json.loads((release / 'manifest.json').read_text(encoding='utf-8'))
    artifact = (release / metadata['artifact']).resolve()
    check(artifact.is_relative_to(root / 'artifacts/validated'), 'artifact is not in artifacts/validated')
    check(sha(artifact) == metadata['sha256'], 'artifact changed')
    check(artifact.stat().st_size == metadata['size_bytes'], 'artifact size changed')
    validated = dict(reversed(line.split('  ', 1)) for line in (root / 'artifacts/validated/SHA256SUMS').read_text().splitlines())
    check(validated.get(artifact.name) == metadata['sha256'], 'artifacts/validated/SHA256SUMS disagrees')
    listed = set()
    for line in (release / 'SHA256SUMS').read_text().splitlines():
        digest, file = line.split('  ', 1)
        check(file not in listed, f'duplicate checksum: {file}')
        listed.add(file)
        check(sha(release / file) == digest, f'checksum: {file}')
    actual = {p.relative_to(release).as_posix() for p in release.rglob('*')
              if p.is_file() and p.name != 'SHA256SUMS'}
    check(listed == actual, 'package file inventory differs from SHA256SUMS')
    sources = json.loads((release / 'source-input-manifest.json').read_text())
    for file, digest in sources.items():
        check(sha(release / 'build-inputs' / file) == digest, f'frozen input: {file}')
        if file.startswith(compared):
            check(same_text(root / file, release / 'build-inputs' / file), f'current source differs: {file}')
    return len(sources)


def main():
    counts = {name: check_package(name, *spec) for name, spec in PACKAGES.items()}
    # The SPI overlay is complete in the SPI package and never part of the QSPI inputs.
    qspi_inputs = json.loads((root / PACKAGES['qspi'][0] / 'source-input-manifest.json').read_text())
    spi_inputs = json.loads((root / PACKAGES['spi'][0] / 'source-input-manifest.json').read_text())
    overlay = {p.relative_to(root).as_posix() for p in (root / 'rtl/spi').glob('*.sv')}
    assert overlay and overlay <= set(spi_inputs), '[spi] rtl/spi overlay missing from the package'
    assert not any(f.startswith('rtl/spi/') for f in qspi_inputs), '[qspi] overlay leaked into QSPI inputs'
    catalog = json.loads((root / 'releases/candidates.json').read_text(encoding='utf-8'))
    direct = dict(reversed(line.split('  ', 1)) for line in (root / 'releases/SHA256SUMS').read_text().splitlines())
    for asset in catalog['release_assets']:
        if asset.endswith('.fs'):
            path = (root / 'releases' / asset).resolve()
            assert path.is_relative_to(root / 'artifacts/validated'), f'experimental release asset: {asset}'
            assert direct.get(path.name) == sha(path), f'releases/SHA256SUMS disagrees: {path.name}'
    for key in ('qspi_pcm_stream', 'spi_pcm_stream'):
        assert catalog[key]['status'] == 'selected', key
    experimental = root / 'artifacts/experimental/spi-sta-fail'
    assert (experimental / 'DO_NOT_PROGRAM.txt').read_text().startswith('DO NOT PROGRAM')
    assert catalog['spi_pcm2_sta_fail']['status'] == 'quarantined_sta_fail'
    for line in (experimental / 'SHA256SUMS').read_text().splitlines():
        digest, file = line.split('  ', 1)
        assert sha(experimental / file) == digest, file
    print(f"PASS: QSPI package ({counts['qspi']} frozen inputs), SPI package ({counts['spi']} frozen inputs), "
          f"validated bitstreams and release asset checksums")


if __name__ == '__main__':
    main()
