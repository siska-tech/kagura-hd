# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('decoder', Path(__file__).with_name('decode.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


class Decoder(unittest.TestCase):
    def raw(self, name='r0-a0-f0'):
        return (ROOT / ('build/psram-boundary/packet-' + name + '.bin')).read_bytes()

    def test_all_real_uart_simulation_captures(self):
        for name, step, status in [('r0-a0-f0', 10, 0), ('r1-a0-f0', 9, 1),
                                    ('r0-a1-f0', 3, 1), ('r0-a0-f1', 6, 2),
                                    ('r0-a0-f2', 6, 3), ('r0-a0-f3', 6, 3), ('r0-a0-f4', 8, 1)]:
            result = decoder.decode(self.raw(name))
            self.assertEqual((result['last_step'], result['final_status']), (step, status))
            self.assertFalse(result['hardware_pass'])

    def test_wrap_same_start_false_pass_and_independent_failure(self):
        result = decoder.decode(self.raw('r1-a0-f0'))
        self.assertEqual(result['records'][7]['status'], 0)
        fault = result['records'][9]
        self.assertEqual(fault['address'], 300064)
        self.assertEqual(fault['expected'][:8], '8aaccef0')
        self.assertEqual(fault['actual'][:8], '6587a9cb')
        self.assertEqual(len(result['records']), 10)  # No guard read after fault.

    def test_missing_extra_and_corrupt_capture(self):
        data = self.raw()
        bad = bytearray(data)
        bad[100] ^= 1
        for value in (b'', data[:-1], data[:-149], data + data[-149:], bytes(bad)):
            with self.assertRaises(ValueError):
                decoder.decode(value)

    def test_following_packet_after_fault_rejected(self):
        with self.assertRaisesRegex(ValueError, 'packet after first fault'):
            decoder.decode(self.raw('r1-a0-f0') + self.raw()[-149:])


if __name__ == '__main__':
    unittest.main()
