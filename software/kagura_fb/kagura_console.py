# SPDX-License-Identifier: Apache-2.0
"""USB-input REPL mirrored to HDMI, using a buffered os.dupterm output stream.

Use pause()/resume() around applications which own the framebuffer or a separate
Device. Never access the same pins through a second transport while attached.
"""
from io import IOBase
import os


class Console(IOBase):
    def __init__(self, device, fb, font, keyboard=None, atlas=None):
        from kagura_terminal import Terminal
        self.device, self.fb, self.font = device, fb, font
        self.keyboard = keyboard
        self.atlas = atlas
        self.screen = Terminal(fb, font, atlas=atlas)
        self._buffer = bytearray(4096)
        self._head = self._tail = 0
        self.dropped = 0
        self.last_error = None
        self.paused = False
        self._updating = self._closed = False
        self._interrupt = self._needs_sync = False
        self._previous = self._timer = None
        self._cursor_bank = self._cursor_position = None

    def _setup_cursor(self):
        if not getattr(self.device, 'capabilities', 0) & 32:
            return
        status, _ = self.device.cursor_status()
        if status & 1:
            self.device.cursor_wait()
            status, _ = self.device.cursor_status()
        bank = 1 - ((status >> 1) & 1)
        shape = bytearray(256)
        for y in range(self.font.height - 2, self.font.height):
            for x in range(self.screen.cell):
                shape[y * 8 + x // 4] |= 1 << ((3 - x % 4) * 2)
        self.device.cursor_shape(bank, shape, (0xfff, 0, 0))
        self._cursor_bank, self._cursor_position = bank, None
        self._move_cursor()

    def _move_cursor(self):
        if self._cursor_bank is None:
            return
        position = (min(self.screen.x, (self.screen.columns - 1) * self.screen.cell),
                    self.screen.y * self.font.height)
        if position != self._cursor_position:
            self.device.cursor_move(position[0], position[1], self._cursor_bank)
            self._cursor_position = position

    def _hide_cursor(self):
        if self._cursor_bank is not None:
            self.device.cursor_move(0, 0, self._cursor_bank, visible=False)
            self.device.cursor_wait()
            self._cursor_position = None

    def readinto(self, buffer):
        try:
            if not len(buffer):
                return 0
            if self._interrupt:
                self._interrupt = False
                buffer[0] = 3
                return 1
            return self.keyboard.readinto(buffer) if self.keyboard is not None else None
        except KeyboardInterrupt:
            buffer[0] = 3
            return 1

    def ioctl(self, request, flags):
        try:
            ready = self._interrupt or (self.keyboard is not None and self.keyboard.any())
            return ((5 if ready else 4) & flags) if request == 3 else 0
        except KeyboardInterrupt:
            self._interrupt = True
            return 5 & flags

    def write(self, data):
        n = len(data)
        head, size = self._head, len(self._buffer)
        count = min(n, (self._tail - head - 1) % size) * (not self.paused)
        first = min(count, size - head)
        self._buffer[head:head + first] = data[:first]
        self._buffer[:count - first] = data[first:count]
        self._head = (head + count) % size
        self.dropped += (n - count) * (not self.paused)
        return n

    def _tick(self, timer=None):
        try:
            if self.keyboard is not None:
                self.keyboard.poll()
            self._flush_display()
        except KeyboardInterrupt:
            self._interrupt = self._needs_sync = True
        except Exception as error:
            self.last_error = error
        # Re-arm after finishing. A periodic timer can flood the scheduler when
        # a slow display update takes longer than its period and starve USB.
        if not self._closed and self._timer is not None:
            self._arm()
        # Like KAGURA-9, hand an interrupted soft callback back to the REPL.
        # Keep notify last: it can pend KeyboardInterrupt for the foreground VM.
        if self._interrupt or (self.keyboard is not None and self.keyboard.any()):
            return os.dupterm_notify(self)

    def _arm(self):
        from machine import Timer
        delay = 5 if self._head != self._tail else 20
        self._timer.init(period=delay, mode=Timer.ONE_SHOT, callback=self._tick, hard=False)

    def _flush_display(self):
        dev = self.device
        if (self.paused or self._closed or self._updating or self.last_error is not None
                or dev._display_busy or (dev._pending_tag is not None and not self._needs_sync)
                or dev.transport._active):
            return
        self._updating = True
        try:
            if self._needs_sync:
                # Fence with a fresh tag; never resend an uncertain GPU command.
                dev.fence()
                self._needs_sync = False
            if self.atlas is not None and not self.atlas.ready:
                self.atlas.prewarm_step()
                return
            count = min((self._head - self._tail) % len(self._buffer), 128)
            from time import ticks_ms, ticks_diff
            started = ticks_ms()
            for _ in range(count):
                value = self._buffer[self._tail]
                self._tail = (self._tail + 1) % len(self._buffer)
                self.screen.feed(bytes((value,)))
                # End a batch at a line boundary, avoiding transfer of empty
                # rectangles across unrelated lines while keeping typing live.
                if value == 10 or ticks_diff(ticks_ms(), started) >= 25:
                    break
            self.screen.flush()
            self._move_cursor()
        except Exception as error:
            self.last_error = error
        finally:
            self._updating = False

    def pause(self):
        if self._closed:
            return
        snapshot = not self.paused and self.atlas is not None and self.atlas.supported
        self.paused = True
        self._tail = self._head
        self._hide_cursor()
        if snapshot:
            # BLIT text stays on the FPGA; synchronize the RAM shadow only when
            # handing the display to an application, not for every character.
            self.device.read_into(self.fb.page * 115200, self.fb.buffer)

    def resume(self):
        if self._closed:
            raise ValueError('console is closed')
        self.paused = True
        self.device.fence()
        self.device.palette(0, 0x012)
        self.device.palette(15, 0xfff)
        self.fb.show()
        if self.atlas is not None:
            self.atlas.reset()
        self._needs_sync = False
        self.last_error = None
        self._setup_cursor()
        self.paused = False

    def close(self):
        if self._closed:
            return
        self.paused = True
        self._closed = True
        if self._timer is not None:
            self._timer.deinit()
            self._timer = None
        os.dupterm(self._previous, 0)
        try:
            self._hide_cursor()
        except Exception:
            pass  # Cleanup must still release UART/PIO after a communication fault.
        self.font.close()
        if self.keyboard is not None:
            self.keyboard.close()
        self.device.transport.deinit()
        # A deinitialized timer/queued bound callback can retain this stream.
        # Release the large surfaces explicitly when ownership is relinquished.
        self.fb = self.screen = self.atlas = self.font = self.keyboard = None
        self._buffer = bytearray()


console = None


def start(font_path='fonts/mplus12.kmf', baudrate=5_000_000, startup_ms=2000, keyboard=True, blit=True, native=True):
    global console
    if console is not None and not console._closed:
        return console
    from machine import Pin, Timer
    from time import ticks_ms, ticks_diff, sleep_ms
    import gc
    if not hasattr(os, 'dupterm') or not hasattr(os, 'dupterm_notify'):
        raise RuntimeError('HDMI REPL requires dupterm-enabled MicroPython')
    # FPGA power-up pulls several pins high. Require READY high and BUSY low.
    ready, busy = Pin(9, Pin.IN, Pin.PULL_DOWN), Pin(8, Pin.IN)
    started = ticks_ms()
    while not (ready.value() and not busy.value()):
        if ticks_diff(ticks_ms(), started) >= startup_ms:
            raise OSError('FPGA not ready; USB REPL remains available')
        sleep_ms(10)
    # Reserve the largest contiguous object before importing/compiling PIO kernels.
    gc.collect()
    pixels = bytearray(115200)
    from rp2040_pio import connect
    from kagura_framebuf import FrameBuffer
    from kagura_ja import Font
    dev = connect(baudrate, native=native)
    font = None
    keys = None
    try:
        font = Font(font_path)
        fb = FrameBuffer(dev, page=0, buffer=pixels)
        dev.palette(0, 0x012)
        dev.palette(15, 0xfff)
        dev.fill_rect(0, 0, 0, 640, 360, 0)
        dev.present(0)
        if keyboard:
            from kagura_keyboard import Keyboard
            keys = Keyboard()
            keys.configure()
        atlas = None
        if blit:
            from kagura_glyph_atlas import GlyphAtlas
            atlas = GlyphAtlas(dev, font)
        result = Console(dev, fb, font, keys, atlas)
        result._setup_cursor()
        result._timer = Timer(-1)
        result._previous = os.dupterm(result, 0)
        result._arm()
        console = result
        print('KAGURA-HD MicroPython / PIO QSPI %d MHz' % (baudrate // 1_000_000))
        print('USB REPL -> HDMI / M+ bitmap font')
        if keys is not None:
            print('XIAO keyboard: UART0 GP0/GP1 / XLINK / 115200 8N1')
        return result
    except BaseException:
        if keys is not None:
            keys.close()
        if font is not None:
            font.close()
        dev.transport.deinit()
        raise
