# SPDX-License-Identifier: Apache-2.0
"""PRT1 extension of the PBC1 decoder. Offline files only, no device access.

Status 4/5 classify the final observation; neither is linear-memory acceptance.
The original PBC1 decoder and hardware-proven diagnostic remain unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'pbc1_decoder', Path(__file__).parents[1] / 'psram-boundary/decode.py')
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
PLAN = _base.PLAN[:7] + [('wrap_target_observation', 300032, False, '8aaccef0')]


def decode(data):
    if not data or len(data) % 149 or len(data) > len(PLAN) * 149:
        raise ValueError('missing, incomplete or extra packet')
    records = []
    packet_count = len(data) // 149
    for index in range(packet_count):
        packet = data[index * 149:(index + 1) * 149]
        if packet[:4] != b'PRT1' or packet[145:] != b'END!':
            raise ValueError('invalid PRT1 framing')
        checksum = 0
        for value in packet[:144]:
            checksum ^= value
        if packet[144] != checksum:
            raise ValueError('packet XOR mismatch')
        status, step, words, write = packet[4:8]
        if step != index or status not in (0, 1, 2, 3, 4, 5):
            raise ValueError('out-of-order step or unknown status')
        name, address, expected_write, expected_hex = PLAN[index]
        expected = bytes.fromhex(expected_hex)
        if (int.from_bytes(packet[8:12], 'little') != address or words * 4 != len(expected) or
                write != int(expected_write) or packet[12:16] != b'\x8f\x1f\x0e\x06'):
            raise ValueError('metadata differs from fixed plan')
        if packet[16:80] != expected + bytes(64 - len(expected)):
            raise ValueError('unexpected expected-data field')
        actual = packet[80:144]
        equal = actual[:len(expected)] == expected
        if index < 7:
            if status in (4, 5) or write and status == 1:
                raise ValueError('prediction classification before final observation')
            valid = not write and status in (0, 1)
            if valid and ((status == 0) != equal):
                raise ValueError('initialization status/data inconsistency')
        else:
            if status not in (2, 3, 4, 5):
                raise ValueError('missing final observation classification')
            valid = status in (4, 5)
            if valid and ((status == 4) != equal):
                raise ValueError('prediction status/data inconsistency')
        if status and index != packet_count - 1:
            raise ValueError('packet after terminal status; stop contract violated')
        records.append(dict(step=step, operation=name, address=address, words=words,
                            write=bool(write), status=status,
                            prediction=packet[16:80].hex() if index == 7 else None,
                            expected=packet[16:80].hex(), actual=actual.hex(),
                            meaningful_bytes=len(expected), data_valid=valid))
    last = records[-1]
    if last['status'] == 0:
        raise ValueError('premature end without terminal result')
    observed = last['step'] == 7 and last['status'] in (4, 5)
    return dict(capture_valid=True, observation_complete=observed,
                prediction_match=(last['status'] == 4) if observed else None,
                classification=('wrap32_target_prediction_match' if last['status'] == 4 else
                                'target_prediction_differs' if last['status'] == 5 else 'aborted'),
                last_step=last['step'], final_status=last['status'], records=records,
                uart_bytes=len(data), uart_sha256=hashlib.sha256(data).hexdigest(),
                linear_memory_pass=None, device_programmed=False, hardware_pass=False, release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    result = decode(args.capture.read_bytes())
    print(json.dumps(result, indent=2))
    # Both match and non-match are successful observation capture, not memory PASS.
    raise SystemExit(0 if result['observation_complete'] else 1)
