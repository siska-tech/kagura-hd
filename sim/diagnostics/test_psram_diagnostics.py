# SPDX-License-Identifier: Apache-2.0
"""Offline tests of evidence inference and fail-stop diagnostic preparation."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'software/kagura_fb'), str(ROOT / 'software/kagura_fb/tests')]
from kagura_fb import Device
from model import Model


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diag = load('psram_case', 'software/kagura_fb/diagnostics/psram_case.py')
analysis = load('analysis', 'tools/analyze-psram-observation.py')


class WrappedDevice:
    def __init__(self):
        self.memory = {}
        self.operations = []

    def write_bytes(self, address, data):
        self.operations.append(('write', address, len(data)))
        for i, value in enumerate(data):
            self.memory[address // 32 * 32 + (address + i) % 32] = value

    def read_bytes(self, address, size):
        self.operations.append(('read', address, size))
        return bytes(self.memory[address // 32 * 32 + (address + i) % 32] for i in range(size))


class Diagnostics(unittest.TestCase):
    def test_record_and_hypotheses(self):
        record = json.loads((ROOT / 'sim/diagnostics/psram-observation.json').read_text())
        summary, rows = analysis.analyze(record)
        self.assertEqual(summary['smallest_exact_period'], 32)
        self.assertEqual(summary['wrap32_matching_bytes'], 48)
        self.assertEqual(summary['wrap32_bit_errors'], 46)
        self.assertEqual(summary['residual_offsets_mod4'], [14, 2, 0, 0])
        self.assertEqual(len(rows), 64)
        self.assertLess(max(summary['alternative_transforms'].values()), 48)

    def test_real_driver_linear_model_all_cases(self):
        model = Model()
        gpu = Device(model, 20, model.now)
        for words in (1, 2, 4, 8, 16):
            for address in (300032, 300060, 300064, 300092):
                records = []
                diag.run_one(gpu, records.append, address, words, words + address % 64)
                self.assertEqual(records[-1]['stage'], 'complete')
                self.assertTrue(all(record.get('match', True) for record in records))

    def test_window_echo_uses_no_memory_command(self):
        model = Model()
        gpu = Device(model, 20, model.now)
        records = []
        diag.window_only(gpu, records.append)
        self.assertEqual(len(model.commands), 0)
        self.assertEqual(records[0]['length'], 64)
        self.assertTrue(records[0]['match'])

    def test_wrap64_full_fault_log_and_no_replay(self):
        gpu = WrappedDevice()
        records = []
        with self.assertRaisesRegex(ValueError, 'STOP, no replay'):
            diag.run_one(gpu, records.append, 300032, 16, 1)
        self.assertEqual(records[-1]['stage'], 'same_start_read')
        self.assertEqual(len(bytes.fromhex(records[-1]['actual'])), 64)
        self.assertFalse(records[-1]['match'])
        self.assertEqual(gpu.operations[-1], ('read', 300032, 64))
        self.assertEqual(sum(op == ('write', 300032, 64) for op in gpu.operations), 1)

    def test_crossing_short_wrap_false_pass_exposed_by_location(self):
        gpu = WrappedDevice()
        records = []
        with self.assertRaisesRegex(ValueError, 'STOP, no replay'):
            diag.run_one(gpu, records.append, 300060, 2, 2)
        same = next(record for record in records if record['stage'] == 'same_start_read')
        self.assertTrue(same['match'])  # Same wrap path on write/read hides corruption.
        self.assertEqual(records[-1]['stage'], 'independent_4B_location_and_guard')
        self.assertFalse(records[-1]['match'])

    def test_transport_exception_propagates_without_retry(self):
        class FailingDevice:
            calls = 0
            def write_bytes(self, address, data):
                self.calls += 1
                raise OSError('uncertain completion')
        gpu = FailingDevice()
        records = []
        with self.assertRaisesRegex(OSError, 'uncertain'):
            diag.run_one(gpu, records.append, 300032, 1, 3)
        self.assertEqual(gpu.calls, 1)
        self.assertEqual(records[-1]['stage'], 'seed_write_intent')

    def test_long_read_isolated_from_long_write(self):
        gpu = WrappedDevice()
        records = []
        with self.assertRaisesRegex(ValueError, 'STOP, no replay'):
            diag.isolated_read(gpu, records.append, 300032, 16, 7)
        self.assertTrue(all(size == 4 for op, address, size in gpu.operations if op == 'write'))
        self.assertEqual(gpu.operations[-1], ('read', 300032, 64))
        self.assertEqual(records[-1]['stage'], 'isolated_long_read')
        model = Model()
        records = []
        diag.isolated_read(Device(model, 20, model.now), records.append, 300060, 2, 8)
        self.assertEqual(records[-1]['stage'], 'complete')


if __name__ == '__main__':
    unittest.main()
