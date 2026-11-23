# SPDX-License-Identifier: Apache-2.0
"""Run with native MicroPython framebuf, from repository root (16 MiB heap)."""
import framebuf
import gc
from kagura_fb import Device
from kagura_framebuf import FrameBuffer
from kagura_ja import Font
from model import Model

FONT = 'software/kagura_fb/fonts/mplus12.kmf'


def raises(kind, function):
    try:
        function()
    except kind:
        return
    raise AssertionError('expected exception')


model = Model()
device = Device(model, 20, model.now)
fb = FrameBuffer(device, page=1)
assert isinstance(fb, framebuf.FrameBuffer)
fb.fill(0)
fb.pixel(0, 0, 1)
fb.pixel(1, 0, 2)
assert fb.buffer[0] == 0x12
assert fb.show(1, 0, 1, 1) == 1
assert model.memory[115200] == 0x12
assert model.memory[115201] == 0xa5
assert model.page == 1
fb.fill(3)
fb.line(0, 0, 639, 359, 4)
fb.rect(10, 10, 30, 20, 5)
fb.text('native', 20, 20, 6)
fb.scroll(1, 1)
assert fb.show(present=False) == 115200
assert model.memory[115200:230400] == fb.buffer
assert model.memory[:115200] == b'\xa5' * 115200
fb.fill(7)
assert fb.show(639, 359, 100, 100) == 1
assert model.memory[230399] == 0x77
before = len(model.commands)
assert fb.show(640, 360, 10, 10) == 0
assert fb.show(0, 0, -1, 10) == 0
assert len(model.commands) == before
raises(ValueError, lambda: FrameBuffer(device, 2))
raises(ValueError, lambda: FrameBuffer(device, buffer=bytearray(4)))
raises(TypeError, lambda: fb.show(1.0))

# Failed upload must not submit a PRESENT after an incomplete frame.
model.page = None
model.force_error = 2
raises(OSError, lambda: fb.show(0, 0, 4, 1))
assert model.page is None

with Font(FONT) as font:
    assert font.height == 13
    assert font.measure('A日\n本B') == (18, 26)
    assert font.measure('ｶﾞ') == (12, 13)
    assert font.glyph('😀') is None
    # Independent reference: original JIS 0x467C (日) scanlines.
    width, bits = font.glyph('日')
    assert width == 12
    expected = (0, 0x3fc0, 0x2040, 0x2040, 0x2040, 0x2040,
                0x3fc0, 0x2040, 0x2040, 0x2040, 0x2040, 0x3fc0, 0)
    fb.fill(2)
    assert fb.text_jp('日', 1, 2, font, 9, 0) == (13, 2)
    for y, row in enumerate(expected):
        for x in range(12):
            assert fb.pixel(1 + x, 2 + y) == (9 if row & (0x8000 >> x) else 0)
    assert fb.pixel(0, 2) == 2 and fb.pixel(13, 2) == 2
    fb.fill(2)
    fb.text_jp('日', -2, -3, font, 9)
    for y in range(10):
        for x in range(10):
            assert fb.pixel(x, y) == (9 if expected[y + 3] & (0x8000 >> (x + 2)) else 2)
    fb.fill(0)
    font.draw(fb, '😀', 0, 0)
    fallback = bytes(fb.buffer[:13 * 320])
    fb.fill(0)
    font.draw(fb, '?', 0, 0)
    assert fb.buffer[:13 * 320] == fallback
    assert font.draw(fb, 'A\n日', 4, 5) == (16, 18)
    raises(ValueError, lambda: font.draw(fb, 'A', 0, 0, 16))
    # Repeated rendering retains no glyph cache or whole font in RAM.
    gc.collect()
    available = gc.mem_free()
    for _ in range(50):
        font.draw(fb, '日本語表示 ｶｸﾞﾗ', 0, 0)
    gc.collect()
    assert gc.mem_free() >= available - 1024
raises(ValueError, lambda: font.glyph('A'))
font.close()

bad = 'build/framebuf/bad.kmf'
for data in (b'', b'KMF1\x00\x02\x01\x00', b'KMF1\x0d\x02\x01\x00'):
    with open(bad, 'wb') as stream:
        stream.write(data)
    raises(ValueError, lambda: Font(bad))
print('framebuf / M+ Japanese tests PASS')
