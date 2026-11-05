# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('decoder', Path(__file__).with_name('decode.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def repair(packet):
    packet[144] = 0
    for value in packet[:144]:
        packet[144] ^= value
    return packet


class Decoder(unittest.TestCase):
    def raw(self, name='r0-a0-f0'):
        return (ROOT / ('build/psram-wrap-target/packet-' + name + '.bin')).read_bytes()

    def test_three_models_are_distinguishable(self):
        wrap = decoder.decode(self.raw('r1-a0-f0'))
        linear = decoder.decode(self.raw())
        alias = decoder.decode(self.raw('r0-a1-f0'))
        self.assertEqual((wrap['last_step'], wrap['final_status']), (7, 4))
        self.assertEqual(wrap['records'][-1]['actual'][:8], '8aaccef0')
        self.assertEqual((linear['last_step'], linear['final_status']), (7, 5))
        self.assertEqual(linear['records'][-1]['actual'][:8], 'ed0f2143')
        self.assertEqual((alias['last_step'], alias['final_status']), (3, 1))
        self.assertIsNone(alias['prediction_match'])
        for result in (wrap, linear, alias):
            self.assertIsNone(result['linear_memory_pass'])
            self.assertFalse(result['hardware_pass'])

    def test_all_fault_captures(self):
        for name, step, status in [('r0-a0-f1', 6, 2), ('r0-a0-f2', 6, 3),
                                    ('r0-a0-f3', 6, 3), ('r0-a0-f4', 4, 1),
                                    ('r1-a0-f5', 7, 5), ('r0-a0-f6', 7, 2)]:
            result = decoder.decode(self.raw(name))
            self.assertEqual((result['last_step'], result['final_status']), (step, status))
        result = decoder.decode(self.raw('r1-a0-f5'))
        self.assertTrue(result['observation_complete'])
        self.assertFalse(result['prediction_match'])
        self.assertEqual(result['records'][-1]['actual'][:8], '8baccef0')

    def test_incomplete_extra_corrupt_and_post_fault_packets(self):
        data = self.raw()
        bad = bytearray(data)
        bad[100] ^= 1
        for value in (b'', data[:-1], data[:-149], data + data[-149:], bytes(bad),
                      self.raw('r0-a1-f0') + data[4 * 149:5 * 149]):
            with self.assertRaises(ValueError):
                decoder.decode(value)

    def test_final_status_cannot_claim_a_false_match(self):
        raw = self.raw()
        packet = bytearray(raw[-149:])
        packet[4] = 4  # Linear seed A did not match wrap prediction.
        with self.assertRaisesRegex(ValueError, 'prediction status/data'):
            decoder.decode(raw[:-149] + repair(packet))

    def test_wrong_target_address_and_old_protocol_rejected(self):
        raw = self.raw()
        packet = bytearray(raw[-149:])
        packet[8] ^= 4
        with self.assertRaisesRegex(ValueError, 'metadata'):
            decoder.decode(raw[:-149] + repair(packet))
        old = (ROOT / 'build/psram-boundary/packet-r0-a0-f0.bin').read_bytes()
        with self.assertRaises(ValueError):
            decoder.decode(old)


if __name__ == '__main__':
    unittest.main()
