# SPDX-License-Identifier: Apache-2.0
"""Independent register/command model shared by portable C and Python tests."""
import ctypes as C
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "software/kagura_fb"))
from kagura_fb import Device, SPITransport


from model import Model, CursorModel, BlitModel


READ = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_uint8, C.c_bool, C.POINTER(C.c_uint8), C.c_size_t)
WRITE = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_uint8, C.c_bool, C.POINTER(C.c_uint8), C.c_size_t)
NOW = C.CFUNCTYPE(C.c_uint32, C.c_void_p)


class IO(C.Structure):
    _fields_ = [("context", C.c_void_p), ("read", READ), ("write", WRITE), ("now_ms", NOW)]


class CDevice(C.Structure):
    _fields_ = [("io", IO), ("timeout_ms", C.c_uint32), ("next_tag", C.c_uint16),
                ("last_device_error", C.c_uint8), ("connected", C.c_bool)]


class CDriver:
    def __init__(self, model, timeout=20):
        self.model = model
        self.callback_errors = []
        self.lib = C.CDLL(str(ROOT / "build/fb-driver/libkagura_fb.so"))
        self.device = CDevice()

        def read(_, address, increment, data, length):
            try:
                value = model.read(address, increment, length)
                C.memmove(data, bytes(value), length)
                return 0
            except Exception as error:
                self.callback_errors.append(error)
                return -1

        def write(_, address, increment, data, length):
            try:
                model.write(address, increment, C.string_at(data, length))
                return 0
            except OSError:
                return -1
            except Exception as error:
                self.callback_errors.append(error)
                return -1

        self.callbacks = (READ(read), WRITE(write), NOW(lambda _: model.now()))
        io = IO(None, *self.callbacks)
        self.check(self.lib.kfb_init(C.byref(self.device), io, timeout))
        self.check(self.lib.kfb_probe(C.byref(self.device)))

    def check(self, result):
        if self.callback_errors:
            raise self.callback_errors[0]
        if result:
            raise OSError(result, "C driver error")

    def submit(self, command, payload=None):
        packet = (C.c_uint8 * 16).from_buffer_copy(command)
        data = None if payload is None else (C.c_uint8 * len(payload)).from_buffer_copy(payload)
        tag = C.c_uint16()
        self.check(self.lib.kfb_submit(C.byref(self.device), packet, data, C.c_size_t(0 if payload is None else len(payload)), C.byref(tag)))
        return tag.value

    def wait(self, tag):
        self.check(self.lib.kfb_wait(C.byref(self.device), C.c_uint16(tag)))

    def fill_rect(self, *args):
        self.check(self.lib.kfb_fill_rect(C.byref(self.device), *args))

    def copy_rect(self, *args):
        self.check(self.lib.kfb_copy_rect(C.byref(self.device), *args))

    def palette(self, *args):
        self.check(self.lib.kfb_palette(C.byref(self.device), *args))

    def present(self, page):
        self.check(self.lib.kfb_present(C.byref(self.device), page))

    def fence(self):
        self.check(self.lib.kfb_fence(C.byref(self.device)))

    def write_bytes(self, address, data):
        array = (C.c_uint8 * len(data)).from_buffer_copy(data)
        self.check(self.lib.kfb_write_bytes(C.byref(self.device), address, array, C.c_size_t(len(data))))

    def read_bytes(self, address, length):
        array = (C.c_uint8 * length)()
        self.check(self.lib.kfb_read_bytes(C.byref(self.device), address, array, C.c_size_t(length)))
        return bytes(array)


class CursorCDriver(CDriver):
    def cursor_shape(self, bank, shape, colors, hotspot=(0, 0)):
        bitmap = (C.c_uint8 * 256).from_buffer_copy(shape)
        palette = (C.c_uint16 * 3)(*colors)
        self.check(self.lib.kfb_cursor_shape(C.byref(self.device), bank, bitmap, palette, *hotspot))

    def cursor_move(self, x, y, bank, visible=True):
        self.check(self.lib.kfb_cursor_move(C.byref(self.device), x, y, bank, C.c_bool(visible)))

    def cursor_status(self):
        status, generation = C.c_uint8(), C.c_uint16()
        self.check(self.lib.kfb_cursor_status(C.byref(self.device), C.byref(status), C.byref(generation)))
        return status.value, generation.value

    def cursor_wait(self):
        generation = C.c_uint16()
        self.check(self.lib.kfb_cursor_wait(C.byref(self.device), C.byref(generation)))
        return generation.value


class CursorTests(unittest.TestCase):
    def each(self):
        for kind in ("python", "c"):
            model = CursorModel()
            driver = Device(model, 20, model.now) if kind == "python" else CursorCDriver(model)
            yield kind, model, driver

    def test_shape_motion_independent_of_gpu_and_no_fb_writes(self):
        shape = bytes((n * 13) & 255 for n in range(256))
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.hold = True
                tag = driver.submit(b"\x03\x01" + bytes(14))
                driver.cursor_shape(1, shape, (0xf00, 0x0f0, 0x00f), (3, 4))
                self.assertEqual(bytes(model.cursor_assets[1]), shape)
                self.assertEqual(bytes(model.cursor_palettes[1]), b"\x00\x0f\xf0\x00\x0f\x00")
                self.assertEqual(bytes(model.cursor_hotspots[1]), b"\x03\x04")
                driver.cursor_move(-1024, 1023, 1)
                self.assertIsNotNone(model.cursor_pending)
                self.assertEqual(driver.cursor_wait(), 1)
                status, generation = driver.cursor_status()
                self.assertEqual((status & 7, generation), (6, 1))
                self.assertTrue(status & 32)
                self.assertEqual(model.cursor_position, (-1024, 1023, 1, True))
                self.assertIsNotNone(model.pending)
                self.assertEqual(len(model.commands), 1)
                model.hold = False
                driver.wait(tag)
                self.assertEqual(model.page, 1)
                self.assertEqual(model.memory[:4096], bytes((0xa5,)) * 4096)
                self.assertFalse(model.cursor_completed)

    def test_latest_motion_and_generation_wrap(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                driver.cursor_shape(1, bytes(256), (1, 2, 3))
                model.cursor_generation = 65534
                driver.cursor_move(1, 2, 1)
                driver.cursor_move(3, 4, 1)
                driver.cursor_move(5, 6, 1)
                self.assertEqual(driver.cursor_wait(), 0)
                self.assertEqual(model.cursor_position, (5, 6, 1, True))
                driver.cursor_move(5, 6, 1, False)
                self.assertEqual(driver.cursor_wait(), 1)
                self.assertFalse(model.cursor_visible)

    def test_busy_missing_shape_timeout_and_no_retry(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                with self.assertRaises(OSError):
                    driver.cursor_move(0, 0, 1)
                with self.assertRaises(OSError):
                    driver.cursor_shape(0, bytes(256), (1, 2, 3))
                driver.cursor_shape(1, bytes(256), (1, 2, 3))
                model.cursor_fail_submit = True
                with self.assertRaises(OSError):
                    driver.cursor_move(10, 20, 1)
                self.assertEqual(len(model.cursor_submissions), 1)
                model.cursor_auto = False
                with self.assertRaises(OSError):
                    driver.cursor_wait()
                model.cursor_auto = True
                self.assertEqual(driver.cursor_wait(), 1)
                self.assertEqual(model.cursor_position, (10, 20, 1, True))

    def test_invalid_input_and_old_firmware(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                for coordinates in ((-1025, 0, 1), (0, 1024, 1), (0, 0, 2)):
                    with self.assertRaises((OSError, ValueError)):
                        driver.cursor_move(*coordinates)
                with self.assertRaises((OSError, ValueError)):
                    driver.cursor_shape(1, bytes(256), (1, 2, 4096))
                self.assertFalse(model.cursor_submissions)
                model.identity = b"KFB1\x01\x00\x1f"
                with self.assertRaises((OSError, ValueError)):
                    driver.cursor_move(0, 0, 1)


class DriverTests(unittest.TestCase):
    def each(self):
        for kind in ("python", "c"):
            model = Model()
            driver = Device(model, 20, model.now) if kind == "python" else CDriver(model)
            yield kind, model, driver

    def test_clipping_and_tag_wrap(self):
        traces = []
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                driver.fill_rect(1, -3, -4, 20, 20, 7)
                command = model.commands[0]
                self.assertEqual(command, bytes.fromhex("01010000000000001100100007000000"))
                self.assertEqual(model.memory[115200], 0x77)
                self.assertEqual(model.memory[115200 + 8], 0x75)
                self.assertEqual(model.memory[115200 + 9], 0xa5)
                driver.fill_rect(0, 700, 0, 10, 20, 1)
                driver.fill_rect(0, 0, 0, 0, 20, 1)
                driver.fill_rect(0, -2147483648, 0, 2147483647, 20, 1)
                self.assertEqual(len(model.commands), 1)
                driver.fence()
                self.assertEqual(model.tag, 1)
                traces.append(model.commands)
        self.assertEqual(*traces)

    def test_unaligned_transfers_and_masks(self):
        traces = []
        data = bytes((i * 17 + 3) & 255 for i in range(130))
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                driver.write_bytes(3, data)
                self.assertEqual(model.memory[:3], b"\xa5" * 3)
                self.assertEqual(model.memory[3:133], data)
                self.assertEqual(model.memory[133], 0xa5)
                self.assertEqual(driver.read_bytes(3, 130), data)
                driver.write_bytes(4194301, b"xyz")
                self.assertEqual(driver.read_bytes(4194301, 3), b"xyz")
                traces.append(model.commands)
        self.assertEqual(*traces)

    def test_palette_present(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                driver.palette(6, 0xf20)
                self.assertIsNone(model.active_palette)
                driver.present(1)
                self.assertEqual(model.active_palette[6], 0xf20)
                self.assertEqual(model.page, 1)

    def test_bounds_before_io(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                for operation in (lambda: driver.present(2), lambda: driver.palette(16, 0),
                                  lambda: driver.fill_rect(0, 0, 0, 1, 1, 16),
                                  lambda: driver.write_bytes(4194303, b"12"),
                                  lambda: driver.read_bytes(4194303, 2)):
                    with self.assertRaises((ValueError, OSError)):
                        operation()
                self.assertEqual(model.commands, [])

    def test_timeout_and_missing_completion_flag(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.lost_done = True
                with self.assertRaises(OSError):
                    driver.fence()
                self.assertEqual(len(model.commands), 1)

    def test_uncertain_submit_is_not_retried(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.fail_submit = True
                with self.assertRaises(OSError):
                    driver.fence()
                self.assertEqual(len(model.commands), 1)
                driver.fence()
                self.assertEqual([int.from_bytes(c[2:4], "little") for c in model.commands], [0, 1])

    def test_device_error_and_transport_fault(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.force_error = 4
                with self.assertRaises(OSError):
                    driver.fence()
                model.late = True
                with self.assertRaises(OSError):
                    driver.fence()
                self.assertEqual(len(model.commands), 1)

    def test_incompatible_identity(self):
        for kind in ("python", "c"):
            model = Model()
            model.identity = b"K9xx\x00\x06\x00"
            with self.subTest(kind=kind), self.assertRaises((ValueError, OSError)):
                Device(model, 20, model.now) if kind == "python" else CDriver(model)

    def test_read_only_destination_before_command(self):
        model = Model()
        driver = Device(model, 20, model.now)
        with self.assertRaises(TypeError):
            driver.read_into(0, b"abc")
        self.assertFalse(model.commands)


class BlitTests(unittest.TestCase):
    def each(self):
        for kind in ("python", "c"):
            model = BlitModel()
            driver = Device(model, 20, model.now) if kind == "python" else CDriver(model)
            yield kind, model, driver

    def test_overlap_bounds_and_descriptors(self):
        traces = []
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.memory[:230400] = bytes((n * 37 + n // 640) & 255 for n in range(230400))
                for args in ((0, 6, 3, 0, 14, 3, 258, 4), (0, 14, 3, 0, 6, 3, 258, 4),
                             (0, 0, 0, 0, 0, 16, 640, 344), (0, 0, 16, 0, 0, 0, 640, 344),
                             (0, 638, 359, 1, 638, 359, 2, 1)):
                    sp, sx, sy, dp, dx, dy, w, h = args
                    expected = bytearray(model.memory)
                    for row in range(h):
                        source = sp * 115200 + (sy + row) * 320 + sx // 2
                        target = dp * 115200 + (dy + row) * 320 + dx // 2
                        expected[target:target+w//2] = model.memory[source:source+w//2]
                    driver.copy_rect(*args)
                    self.assertEqual(model.memory, expected)
                before = len(model.commands)
                driver.copy_rect(0, 0, 0, 0, 0, 0, 640, 360)
                driver.copy_rect(0, 638, 359, 1, 638, 359, 0, 0)
                self.assertEqual(len(model.commands), before)
                for args in ((0, 0, 0, 1, 2, 0, 2, 1), (0, 1, 0, 1, 1, 0, 2, 1),
                             (0, 0, 0, 1, 0, 0, 3, 1), (0, 638, 0, 1, 638, 0, 4, 1),
                             (0, 0, 359, 1, 0, 0, 2, 2), (0, 0, 0, 1, 0, 359, 2, 2),
                             (0, 0, 0, 1, 0, 0, 2147483647, 1), (0, 0, 0, 1, 0, 0, -2, 1)):
                    with self.assertRaises((ValueError, OSError)):
                        driver.copy_rect(*args)
                self.assertEqual(len(model.commands), before)
                traces.append(model.commands)
        self.assertEqual(*traces)

    def test_capability_errors_and_no_retry(self):
        for kind, model, driver in self.each():
            with self.subTest(kind=kind):
                model.identity = b"KFB1\x01\x01\x3f"
                with self.assertRaises((ValueError, OSError)):
                    driver.copy_rect(0, 0, 0, 1, 0, 0, 8, 1)
                self.assertEqual(model.commands, [])
                model.identity = b"KFB1\x01\x02\x7f"
                model.fail_submit = True
                with self.assertRaises(OSError):
                    driver.copy_rect(0, 0, 0, 1, 0, 0, 8, 1)
                self.assertEqual(len(model.commands), 1)
                driver.wait(int.from_bytes(model.commands[0][2:4], "little"))
                model.force_error = 4
                with self.assertRaises(OSError):
                    driver.copy_rect(0, 0, 0, 1, 0, 0, 8, 1)
                self.assertEqual(len(model.commands), 2)


if __name__ == "__main__":
    unittest.main()
