# SPDX-License-Identifier: Apache-2.0
"""Prepared RAM-only, one-case diagnostics. Importing this file does no I/O.

Caller supplies an exclusively owned Device and synchronous durable log callback.
No serial connection, GPIO constructor, retry, reset, firmware/file/Flash write.
Never call another case after an exception without separately reviewing the fault.
"""


def pattern(address, length, case_id):
    # Absolute address and case identify data; 32/64B halves differ.
    return bytes(((address + i) * 37 + ((address + i) >> 8) * 17 + case_id * 29) & 255
                 for i in range(length))


def _record(emit, stage, address, expected, actual, case_id):
    emit({'case_id': case_id, 'stage': stage, 'address': address,
          'length': len(expected), 'expected': bytes(expected).hex(),
          'actual': bytes(actual).hex(), 'match': bytes(expected) == bytes(actual)})
    if bytes(expected) != bytes(actual):
        raise ValueError('PSRAM diagnostic mismatch at ' + stage + '; STOP, no replay')


def window_only(gpu, emit, case_id=0):
    """64B host upload echo, no PSRAM command. Destructively uses staging RAM."""
    data = pattern(300000, 64, case_id)
    gpu._idle()
    gpu._write(25, 0)
    gpu.transport.write(24, False, data)
    gpu._write(25, 0)
    actual = gpu.transport.read(24, False, 64)
    _record(emit, 'host_window_64_no_psram', 0, data, actual, case_id)


def run_one(gpu, emit, address, words, case_id):
    """One selected case; not a sweep. Logs complete read before comparing.

    Scratch only (300000..300159). Tests whole transfer then independent 4B
    probes including guards. A short same-start wrap roundtrip can falsely pass;
    the independent probes expose wrong absolute placement.
    """
    if words not in (1, 2, 4, 8, 16) or address % 4:
        raise ValueError('word-aligned 1/2/4/8/16-word case required')
    length = words * 4
    first = (address // 32) * 32
    end = ((address + length + 31) // 32) * 32
    if first < 300000 or end > 300160:
        raise ValueError('outside disposable diagnostic region')
    # Seed and verify entire touched wrap envelope via isolated 1-word commands.
    for at in range(first, end, 4):
        data = pattern(at, 4, case_id + 128)
        emit({'case_id': case_id, 'stage': 'seed_write_intent', 'address': at, 'data': data.hex()})
        gpu.write_bytes(at, data)
        _record(emit, 'seed_4B', at, data, gpu.read_bytes(at, 4), case_id)
    data = pattern(address, length, case_id)
    emit({'case_id': case_id, 'stage': 'write_intent', 'address': address, 'data': data.hex()})
    gpu.write_bytes(address, data)
    _record(emit, 'same_start_read', address, data, gpu.read_bytes(address, length), case_id)
    for at in range(first, end, 4):
        expected = bytes(data[at - address:at - address + 4]) if address <= at < address + length else pattern(at, 4, case_id + 128)
        _record(emit, 'independent_4B_location_and_guard', at, expected, gpu.read_bytes(at, 4), case_id)
    # Success only. Disposable scratch is not restored; restoring after a failure
    # could hide corruption or replay an operation with uncertain completion.
    emit({'case_id': case_id, 'stage': 'complete', 'address': address, 'length': length})


def isolated_read(gpu, emit, address, words, case_id):
    """Only 1-word writes, followed by exactly one selected long READ.

    This separates long-read wrapping from long-write overwrite. No retries.
    """
    if words not in (1, 2, 4, 8, 16) or address % 4:
        raise ValueError('word-aligned 1/2/4/8/16-word case required')
    length = words * 4
    if address < 300000 or address + length > 300160:
        raise ValueError('outside disposable diagnostic region')
    for at in range(address, address + length, 4):
        data = pattern(at, 4, case_id)
        emit({'case_id': case_id, 'stage': 'seed_write_intent', 'address': at, 'data': data.hex()})
        gpu.write_bytes(at, data)
        _record(emit, 'seed_4B', at, data, gpu.read_bytes(at, 4), case_id)
    expected = pattern(address, length, case_id)
    _record(emit, 'isolated_long_read', address, expected, gpu.read_bytes(address, length), case_id)
    emit({'case_id': case_id, 'stage': 'complete', 'address': address, 'length': length})
