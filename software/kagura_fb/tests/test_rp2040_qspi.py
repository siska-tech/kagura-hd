# SPDX-License-Identifier: Apache-2.0
"""Pin-level transaction oracle for the slow bring-up transport (no hardware)."""
import importlib.util
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "rp2040_qspi", Path(__file__).resolve().parents[1] / "rp2040_qspi.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class Bus:
    def __init__(self, response=b"KFB1"):
        self.pins = {}
        self.sent = []
        self.edges = 0
        self.response = [n for b in response for n in (b >> 4, b & 15)]
        self.fail_at = None

    def pin(self, number, mode, value=None):
        pin = self.pins.setdefault(number, Pin(self, number))
        pin.init(mode, value)
        return pin

    def rising(self):
        if self.pins[7].level:
            return
        self.edges += 1
        if self.edges == self.fail_at:
            raise OSError("injected transfer failure")
        modes = [self.pins[i].mode for i in range(2, 6)]
        if self.edges <= 4:
            assert modes == [1] * 4
        if modes == [1] * 4:
            self.sent.append(sum(self.pins[i].level << (i - 2) for i in range(2, 6)))
        else:
            assert modes == [0] * 4


class Pin:
    def __init__(self, bus, number):
        self.bus, self.number = bus, number
        self.level, self.mode = 0, 0

    def init(self, mode, value=None):
        self.mode = mode
        if value is not None:
            self.value(value)

    def value(self, value=None):
        if value is None:
            if 2 <= self.number <= 5 and not self.mode:
                index = self.bus.edges - 6
                if 0 <= index < len(self.bus.response):
                    return (self.bus.response[index] >> (self.number - 2)) & 1
            return self.level
        rising = self.number == 6 and not self.level and value
        self.level = value
        if rising:
            self.bus.rising()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.bus = Bus()
        factory = self.bus.pin
        # A callable factory with the same direction constants as machine.Pin.
        factory_type = type("PinFactory", (), {"IN": 0, "OUT": 1,
                            "__call__": lambda _, *a, **kw: factory(*a, **kw)})
        self.machine_patch = patch.dict(sys.modules, {"machine": types.SimpleNamespace(Pin=factory_type())})
        self.time_patch = patch.object(time, "sleep_us", lambda _: None, create=True)
        self.machine_patch.start()
        self.time_patch.start()
        self.addCleanup(self.machine_patch.stop)
        self.addCleanup(self.time_patch.stop)
        self.transport = driver.QSPITransport()

    def assert_released(self):
        self.assertEqual(self.bus.pins[7].level, 1)
        self.assertEqual(self.bus.pins[6].level, 0)
        self.assertTrue(all(self.bus.pins[i].mode == 0 for i in range(2, 6)))

    def test_read_has_one_dummy_byte_and_releases_before_dummy(self):
        self.assertEqual(self.transport.read(32, True, 4), b"KFB1")
        self.assertEqual(self.bus.sent, [14, 0, 0, 4])  # E0 header, 04 count
        self.assertEqual(self.bus.edges, 14)  # header+count+dummy+4 data bytes
        self.assert_released()

    def test_write_keeps_full_six_bit_address_and_nibble_order(self):
        self.transport.write(63, False, b"\xab\x01")
        self.assertEqual(self.bus.sent, [3, 15, 10, 11, 0, 1])
        self.assert_released()

    def test_failure_releases_pins_without_retry(self):
        self.bus.fail_at = 5
        with self.assertRaises(OSError):
            self.transport.read(0, True, 4)
        self.assertEqual(self.bus.edges, 5)
        self.assert_released()

    def test_invalid_read_does_not_select_device(self):
        for address, length in ((64, 1), (0, 0), (0, 257)):
            with self.assertRaises(ValueError):
                self.transport.read(address, False, length)
        self.assertEqual(self.bus.edges, 0)
        self.assert_released()


if __name__ == "__main__":
    unittest.main()
