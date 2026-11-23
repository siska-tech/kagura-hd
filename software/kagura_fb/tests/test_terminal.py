# SPDX-License-Identifier: Apache-2.0
import framebuf
from kagura_terminal import Terminal
from kagura_ja import Font
from kagura_console import Console

class Transport:
    _active = False
    def deinit(self): self.closed = True

class Device:
    _display_busy = 0
    _pending_tag = None
    transport = Transport()
    def __init__(self): self.copies = []
    def copy_rect(self, *args): self.copies.append(args)
    def fill_rect(self, *args): pass
    def fence(self): pass
    def palette(self, *args): pass

class Surface(framebuf.FrameBuffer):
    width, height, page = 60, 39, 0
    def __init__(self, device):
        self.device = device
        self.buffer = bytearray(1170)
        self.uploads = []
        super().__init__(self.buffer, 60, 39, framebuf.GS4_HMSB)
    def show(self, *args, **kwargs): self.uploads.append(args)

with Font('software/kagura_fb/fonts/mplus12.kmf') as font:
    narrow = Surface(Device())
    split = Terminal(narrow, font)
    split.x = 54
    split.feed('A日'.encode())
    split.flush()
    assert narrow.uploads == [(54, 0, 6, 13), (0, 13, 12, 13)]
    cached = font.glyph('日')
    assert font.glyph('日') is cached
    with Font('software/kagura_fb/fonts/mplus12.kmf', cache=1) as small:
        original = small.glyph('A')
        small.glyph('B')
        assert small.glyph('A') == original
        assert len(small._keys) == len(small._glyphs) == 1
    with Font('software/kagura_fb/fonts/mplus12.kmf', cache=0) as uncached:
        assert uncached.glyph('日') == cached
        assert not uncached._keys
    dev = Device()
    fb = Surface(dev)
    terminal = Terminal(fb, font)
    assert (terminal.columns, terminal.rows) == (10, 3)
    for byte in '日A'.encode(): terminal.feed(bytes((byte,)))
    assert terminal.x == 18
    terminal.feed(b'\rB\x1b[2DC')
    assert terminal.x == 6
    terminal.feed(b'\x1b[K')
    assert fb.pixel(30, 0) == 0
    terminal.feed(b'\n1\n2\n3')
    terminal.flush()
    assert terminal.y == 2 and terminal.x == 6
    assert len(dev.copies) == 1
    assert dev.copies[0] == (0, 0, 13, 0, 0, 0, 60, 26)
    assert fb.uploads[-1][3] == 13
    terminal.feed(b'\xff\n')  # invalid UTF-8 falls back without stopping the stream
    assert terminal.y == 2
    terminal.feed(b'\x1b[2;4H')
    assert (terminal.x, terminal.y) == (18, 1)
    terminal.feed(b'\x1b[s\x1b[0;0H')
    assert (terminal.x, terminal.y) == (0, 0)
    terminal.feed(b'\x1b[u')
    assert (terminal.x, terminal.y) == (18, 1)
    terminal.feed(b'\x1b[99G\x1b[99d')
    assert (terminal.x, terminal.y) == (54, 2)
    terminal.feed(b'\x1b[?25l\x1b[-1H')
    assert (terminal.x, terminal.y) == (54, 2)
    fb.fill(15)
    terminal.feed(b'\x1b[2;4H\x1b[1J')
    assert fb.pixel(59, 0) == 0 and fb.pixel(23, 13) == 0
    assert fb.pixel(24, 13) == 15 and fb.pixel(0, 26) == 15
    terminal.feed(b'\x1b[0J')
    assert fb.pixel(24, 13) == 0 and fb.pixel(59, 38) == 0
    fb.fill(15)
    terminal.feed(b'\x1b[2J')
    assert fb.buffer == bytearray(len(fb.buffer))
    console = Console(dev, Surface(dev), font)
    assert console.readinto(bytearray(1)) is None
    assert console.write(b'hello') == 5
    dev._display_busy = 1
    console._tick()
    assert console._tail == 0
    dev._display_busy = 0
    dev._pending_tag = 4
    console._tick()
    assert console._tail == 0
    dev._pending_tag = None
    console._tick()
    assert console._tail == 5 and console.last_error is None
    console.pause()
    assert console.write(b'ignored') == 7
    console.resume()
    assert console.ioctl(3, 5) == 4

    class CursorDevice(Device):
        capabilities = 32
        def __init__(self):
            super().__init__()
            self.moves = []
            self.bank = 0
        def cursor_status(self): return self.bank << 1, 0
        def cursor_wait(self): return 0
        def cursor_shape(self, bank, shape, colors):
            assert shape[11 * 8:11 * 8 + 2] == b'\x55\x50'
            assert shape[12 * 8:12 * 8 + 2] == b'\x55\x50'
        def cursor_move(self, x, y, bank, visible=True):
            self.bank = bank
            self.moves.append((x, y, bank, visible))
    cursor_dev = CursorDevice()
    cursor = Console(cursor_dev, Surface(cursor_dev), font)
    cursor._setup_cursor()
    cursor.write(b'A')
    cursor._tick()
    assert cursor_dev.moves[-1] == (6, 0, 1, True)
    count = len(cursor_dev.moves)
    cursor._tick()
    assert len(cursor_dev.moves) == count
    cursor.screen.x = 60
    cursor._move_cursor()
    assert cursor_dev.moves[-1][0] == 54
    cursor.pause()
    assert not cursor_dev.moves[-1][-1]
    cursor.resume()
    assert cursor_dev.moves[-1][-1]
    import kagura_console as console_module
    original_os = console_module.os
    class DuptermOS:
        def dupterm(self, *args): return None
    console_module.os = DuptermOS()
    try:
        cursor.close()
    finally:
        console_module.os = original_os
    assert cursor.fb is None and cursor.screen is None and cursor.atlas is None
    assert cursor.font is None and not cursor._buffer
    assert cursor.device.transport.closed
    cursor.close()  # Idempotent even after large objects have been released.
with Font('software/kagura_fb/fonts/mplus10.kmf') as font:
    assert font.height == 11
    assert font.measure('日本語ABC') == (45, 11)
    assert font.measure('ｶﾞ') == (10, 11)
print('terminal UTF-8/CSI/scroll/locking and 10px font PASS')
