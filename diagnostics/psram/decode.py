# SPDX-License-Identifier: Apache-2.0
"""Decode an already captured PDR1 UART file. No device connection or writes."""
import argparse
import hashlib
import json
from pathlib import Path


def decode(packet):
    if len(packet) != 149 or packet[:4] != b'PDR1' or packet[145:] != b'END!':
        raise ValueError('incomplete/invalid PDR1 packet; no PASS')
    checksum = 0
    for value in packet[:144]:
        checksum ^= value
    if checksum != packet[144]:
        raise ValueError('packet XOR mismatch; no PASS')
    status, case_id, words = packet[4:7]
    address = int.from_bytes(packet[8:12], 'little')
    if status not in (0, 1, 2, 3) or words not in (1, 2, 4, 8, 16) or packet[7] != 0:
        raise ValueError('unsupported status/length/reserved field')
    if address % 4 or not 300000 <= address <= 300160 - words * 4:
        raise ValueError('address outside diagnostic scratch')
    if packet[12:16] != b'\x8f\x1f\x0e\x06':
        raise ValueError('unexpected CR0/LAT/RDL metadata')
    length = words * 4
    expected, actual = packet[16:80], packet[80:144]
    pattern = bytes(((address + i) * 37 + ((address + i) >> 8) * 17 + case_id * 29) & 255
                    for i in range(length))
    if expected[:length] != pattern:
        raise ValueError('unexpected transmitted test pattern')
    equal = expected[:length] == actual[:length]
    if status == 0 and not equal or status == 1 and equal:
        raise ValueError('status/data inconsistency; no PASS')
    return dict(case_id=case_id, address=address, words=words, status=status,
                status_name=('pass', 'mismatch', 'controller_error', 'timeout')[status],
                expected=expected.hex(), actual=actual.hex(), meaningful_bytes=length,
                mismatches=[i for i in range(length) if expected[i] != actual[i]],
                data_valid=status in (0, 1), packet_sha256=hashlib.sha256(packet).hexdigest(),
                hardware_pass=False, scope='single diagnostic packet; not hardware/Release acceptance')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    result = decode(args.capture.read_bytes())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 0 else 1)
