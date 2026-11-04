# SPDX-License-Identifier: Apache-2.0
# Runs on the MicroPython 1.26 Unix port (16 MiB test heap for the memory model).
from kagura_fb import Device, SPITransport
from model import Model

model = Model()
dev = Device(model, 20, model.now)
dev.fill_rect(1, -3, -4, 20, 20, 7)
assert model.memory[115200] == 0x77
assert model.memory[115208] == 0x75
assert model.commands[0] == bytes.fromhex("01010000000000001100100007000000")
source = bytes((index * 17 + 3) & 255 for index in range(130))
dev.write_bytes(3, source)
assert model.memory[:3] == b"\xa5" * 3
assert dev.read_bytes(3, 130) == source
assert model.memory[133] == 0xa5
dev.write_bytes(4194301, b"xyz")
assert dev.read_bytes(4194301, 3) == b"xyz"
dev.palette(6, 0xf20)
assert model.active_palette is None
dev.present(1)
assert model.page == 1 and model.active_palette[6] == 0xf20
before = len(model.commands)
try:
    dev.read_into(0, b"abc")
    raise AssertionError("immutable buffer accepted")
except TypeError:
    pass
assert len(model.commands) == before
model.fail_submit = True
try:
    dev.fence()
    raise AssertionError("lost acknowledgement accepted")
except OSError:
    pass
assert len(model.commands) == before + 1
dev.fence()
assert len(model.commands) == before + 2
model.lost_done = True
try:
    dev.fence()
    raise AssertionError("missing completion flag accepted")
except OSError:
    pass

class Pin:
    def __init__(self):
        self.level = None
    def value(self, level):
        self.level = level

class SPI:
    def __init__(self):
        self.writes = []
        self.fail = False
    def write(self, data):
        if self.fail:
            raise OSError("SPI failure")
        self.writes.append(bytes(data))
    def read(self, length, fill):
        assert fill == 0
        return bytes((0x42,)) * length

spi, cs = SPI(), Pin()
transport = SPITransport(spi, cs)
transport.write(8, True, b"123")
assert spi.writes == [b"\x48", b"123"] and cs.level == 1
assert transport.read(27, False, 1) == b"\x42"
assert spi.writes[-1] == b"\x9b\x01\x00"
spi.fail = True
try:
    transport.read(27, False, 1)
    raise AssertionError("SPI failure accepted")
except OSError:
    pass
assert cs.level == 1
print("PASS: MicroPython driver clipping, tag wrap, masked transfers, readback, palette/present, timeout, SPI frames")

# Cursor operates independently while the drawing engine is busy.
from model import CursorModel
model = CursorModel()
dev = Device(model, 20, model.now)
model.hold = True
tag = dev.submit(b"\x03\x01" + bytes(14))
shape = bytes((n * 13) & 255 for n in range(256))
dev.cursor_shape(1, shape, (0xf00, 0x0f0, 0x00f), (3, 4))
assert bytes(model.cursor_assets[1]) == shape
model.cursor_generation = 65534
dev.cursor_move(-3, 2, 1)
dev.cursor_move(100, 80, 1)
dev.cursor_move(630, 350, 1)
assert dev.cursor_wait() == 0
assert model.cursor_position == (630, 350, 1, True) and model.pending is not None
dev.cursor_move(0, 0, 1, False)
assert dev.cursor_wait() == 1 and not model.cursor_visible
model.hold = False
dev.wait(tag)
assert model.page == 1
# Header bit5 is the sixth address bit for the cursor window.
spi.fail = False
transport.write(48, False, b"x")
assert spi.writes[-2:] == [b"0", b"x"]
print("PASS: MicroPython cursor upload, asynchronous/coalesced moves, hide, applied generation wrap, six-bit header")

from model import BlitModel
model = BlitModel()
dev = Device(model, 20, model.now)
model.memory[:320] = bytes(n & 255 for n in range(320))
original = bytes(model.memory[:320])
dev.copy_rect(0, 6, 0, 0, 14, 0, 258, 1)
assert model.memory[7:136] == original[3:132]
assert model.memory[:7] == original[:7] and model.memory[136:320] == original[136:]
dev.copy_rect(0, 6, 0, 1, 6, 0, 258, 1)
assert model.memory[115203:115332] == model.memory[3:132]
try:
    dev.copy_rect(0, 0, 0, 1, 2, 0, 8, 1)
    raise AssertionError("different byte phase accepted")
except ValueError:
    pass
print("PASS: MicroPython BLIT overlap, partial-word masks, cross-page copy, alignment rejection")
