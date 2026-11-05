# SPDX-License-Identifier: Apache-2.0
"""Offline PBC1 capture validation; no serial/programmer/device access."""
import argparse
import hashlib
import json
from pathlib import Path

# All expected data are little-endian byte strings, separate from the HDL ROM.
PLAN = [
    ('seed_alias_write', 300032, True, 'ed0f2143'),
    ('seed_before_write', 300060, True, '21436587'),
    ('seed_after_write', 300064, True, '6587a9cb'),
    ('seed_alias_verify', 300032, False, 'ed0f2143'),
    ('seed_before_verify', 300060, False, '21436587'),
    ('seed_after_verify', 300064, False, '6587a9cb'),
    ('crossing_write', 300060, True, '012345678aaccef0'),
    ('same_start_read', 300060, False, '012345678aaccef0'),
    ('independent_before_read', 300060, False, '01234567'),
    ('independent_after_read', 300064, False, '8aaccef0'),
    ('alias_guard_read', 300032, False, 'ed0f2143'),
]


def decode(data):
    if not data or len(data) % 149 or len(data) > 11 * 149:
        raise ValueError('missing, incomplete or extra packet; no PASS')
    records = []
    for index in range(len(data) // 149):
        packet = data[index * 149:(index + 1) * 149]
        if packet[:4] != b'PBC1' or packet[145:] != b'END!':
            raise ValueError('invalid packet framing')
        checksum = 0
        for value in packet[:144]:
            checksum ^= value
        if packet[144] != checksum:
            raise ValueError('packet XOR mismatch')
        status, step, words, write = packet[4:8]
        if step != index or status not in (0, 1, 2, 3):
            raise ValueError('out-of-order step or unknown status')
        name, address, expected_write, expected_hex = PLAN[index]
        expected = bytes.fromhex(expected_hex)
        if (int.from_bytes(packet[8:12], 'little') != address or
                words * 4 != len(expected) or write != int(expected_write) or
                packet[12:16] != b'\x8f\x1f\x0e\x06'):
            raise ValueError('operation metadata differs from fixed plan')
        if packet[16:80] != expected + bytes(64 - len(expected)):
            raise ValueError('expected payload differs from fixed plan')
        actual = packet[80:144]
        valid = not write and status in (0, 1)
        equal = actual[:len(expected)] == expected
        if write and status == 1 or valid and ((status == 0) != equal):
            raise ValueError('status/data inconsistency')
        if status and index != len(data) // 149 - 1:
            raise ValueError('packet after first fault; stop contract violated')
        records.append(dict(step=step, operation=name, address=address, words=words,
                            write=bool(write), status=status,
                            expected=packet[16:80].hex(), actual=actual.hex(),
                            meaningful_bytes=len(expected), data_valid=valid,
                            mismatches=[i for i in range(len(expected)) if expected[i] != actual[i]] if valid else None))
    final = records[-1]
    if final['status'] == 0 and len(records) != 11:
        raise ValueError('premature end without fault; no PASS')
    return dict(complete=True, single_case_packet_pass=final['status'] == 0,
                last_step=final['step'], final_status=final['status'], records=records,
                uart_bytes=len(data), uart_sha256=hashlib.sha256(data).hexdigest(),
                device_programmed=False, hardware_pass=False, release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    result = decode(args.capture.read_bytes())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['single_case_packet_pass'] else 1)
