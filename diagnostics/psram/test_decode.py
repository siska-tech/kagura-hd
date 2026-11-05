# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('decoder', Path(__file__).with_name('decode.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


class Decoder(unittest.TestCase):
    def packet(self, name='w1-r0-f0'):
        return (root / ('build/psram-probe-sim/packet-' + name + '.bin')).read_bytes()

    def test_real_uart_captures(self):
        for name, status in [('w1-r0-f0', 0), ('w16-r0-f0', 0), ('w16-r1-f0', 1),
                             ('w1-r0-f1', 3), ('w1-r0-f2', 2)]:
            result = decoder.decode(self.packet(name))
            self.assertEqual(result['status'], status)
            self.assertFalse(result['hardware_pass'])

    def test_incomplete_extra_bad_checksum(self):
        packet = self.packet()
        for bad in (packet[:-1], packet + b'!', packet[:100] + bytes([packet[100] ^ 1]) + packet[101:]):
            with self.assertRaises(ValueError):
                decoder.decode(bad)

    def test_pass_with_inconsistent_payload_is_rejected(self):
        packet = bytearray(self.packet())
        packet[80] ^= 1
        packet[144] = 0
        for value in packet[:144]:
            packet[144] ^= value
        with self.assertRaisesRegex(ValueError, 'status/data inconsistency'):
            decoder.decode(packet)


if __name__ == '__main__':
    unittest.main()
