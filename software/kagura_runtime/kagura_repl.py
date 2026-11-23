# SPDX-License-Identifier: Apache-2.0
"""GPU-backed HDMI REPL, XLINK keyboard and explicit application handoff.

The full screen stays in FPGA PSRAM. Only glyphs and a bounded output ring
occupy Python RAM. 0x80000..0x9c1ff is reserved for the console snapshot.
"""
from io import IOBase
import os
import time

SNAPSHOT = 0x80000
PAGE_BYTES = 115200
console = None


class BuiltinFont:
    """Complete ASCII fallback using MicroPython's built-in 8x8 bitmap font."""
    height, row_bytes = 8, 1

    def __init__(self):
        import framebuf
        self._bits = bytearray(8)
        self._surface = framebuf.FrameBuffer(self._bits, 8, 8, framebuf.MONO_HLSB)
        self._cache = {}

    def glyph(self, character):
        code = ord(character) if isinstance(character, str) else character
        code = code if 32 <= code <= 126 else 63
        found = self._cache.get(code)
        if found is None:
            self._surface.fill(0)
            self._surface.text(chr(code), 0, 0, 1)
            found = (8, bytes(self._bits))
            if len(self._cache) == 16:
                self._cache.clear()
            self._cache[code] = found
        return found

    _lookup = glyph

    def close(self):
        self._cache.clear()


class Device:
    """Small adapter for the shared terminal and kagura_framebuf APIs."""
    def __init__(self, backend):
        self.backend = backend

    def fill_rect(self, *args): self.backend.fill(*args)
    def copy_rect(self, *args): self.backend.copy(*args)
    def write_bytes(self, *args): self.backend.write(*args)
    def palette(self, *args): self.backend.palette(*args)
    def present(self, *args): self.backend.present(*args)


class Surface:
    width, height, page = 640, 360, 0

    def __init__(self, device):
        self.device = device

    def fill(self, color):
        self.device.fill_rect(0, 0, 0, 640, 360, color)

    def show(self, *args, **kwargs):
        pass  # Opaque glyphs and erases are already written directly to PSRAM.


class DirectGlyphs:
    supported, ready = True, True

    def __init__(self, backend, font):
        self.backend, self.font = backend, font

    def advance(self, character):
        return self.font._lookup(character)[0]

    def draw(self, character, x, y, width):
        advance, bits = self.font._lookup(character)
        self.backend.bitmap(0, x, y, advance, self.font.height,
                            self.font.row_bytes, bits, 15, 0)
        return True


class Console(IOBase):
    def __init__(self, backend, font, keyboard=None):
        self.backend, self.font, self.keyboard = backend, font, keyboard
        self.device = Device(backend)
        self.screen = None
        self._buffer = bytearray(4096)
        self._head = self._tail = 0
        self._timer = self._previous = self._previous_frequency = None
        self._attached = False
        self._display_owned = self._suspended = self._snapshot_valid = False
        self._busy = self._closed = self.paused = self._interrupt = False
        self.last_error = None
        self._tick_callback = self._tick
        self.dropped = 0
        self._cursor_position = None

    def readinto(self, buffer):
        if not len(buffer):
            return 0
        if self._interrupt:
            self._interrupt = False
            buffer[0] = 3
            return 1
        return self.keyboard.readinto(buffer) if self.keyboard is not None else None

    def ioctl(self, request, flags):
        if request == 3:
            ready = self._interrupt or (self.keyboard is not None and self.keyboard.any())
            return (5 if ready else 4) & flags
        return None

    def write(self, data):
        n = len(data)
        if self.paused or self._closed or not self._display_owned:
            return n
        head, size = self._head, len(self._buffer)
        count = min(n, (self._tail-head-1)%size)
        first = min(count, size-head)
        self._buffer[head:head+first] = data[:first]
        self._buffer[:count-first] = data[first:count]
        self._head = (head+count)%size
        self.dropped += n-count
        return n

    def _cursor(self, visible=True):
        if self.screen is not None:
            s = self.screen
            position=(min(s.x,(s.columns-1)*s.cell),s.y*self.font.height,s.cell,self.font.height,visible)
            if position!=self._cursor_position:
                self.backend.cursor(*position)
                self._cursor_position=position

    def _open_display(self):
        generation = getattr(self.backend,'generation',None)
        before = generation() if generation is not None else None
        try:
            self.backend.display_open()
            self._display_owned = True
            self._cursor_position = None
            self.backend.palette(0, 0x012)
            self.backend.palette(15, 0xfff)
            if self.screen is None:
                from kagura_terminal import Terminal
                self.screen = Terminal(Surface(self.device), self.font,
                                       atlas=DirectGlyphs(self.backend, self.font))
            self.backend.present(0)
        except BaseException:
            if generation is not None and generation()!=before:
                self._display_owned = True
            self._release_display()
            raise

    def _release_display(self):
        if self._display_owned:
            self._display_owned = False
            self.backend.close()

    def _flush_display(self, paused_ok=False):
        if (not self._display_owned or self._closed or self._busy or
                self.last_error is not None or (self.paused and not paused_ok)):
            return
        self._busy = True
        try:
            started = time.ticks_ms()
            count = min((self._head-self._tail)%len(self._buffer), 128)
            for _ in range(count):
                value = self._buffer[self._tail]
                self._tail = (self._tail+1)%len(self._buffer)
                self.screen.feed(bytes((value,)))
                if value == 10 or time.ticks_diff(time.ticks_ms(), started) >= 25:
                    break
            self.screen.flush()
            self._cursor()
        finally:
            self._busy = False

    def _arm(self):
        if self._closed or self._timer is None:
            return
        delay = 5 if self._display_owned and self._head != self._tail else 20
        self._timer.init(period=delay, mode=self._timer.ONE_SHOT, callback=self._tick_callback, hard=False)

    def _tick(self, timer=None):
        if self._closed:
            return
        try:
            if self.keyboard is not None:
                self.keyboard.poll()
            self._flush_display()
        except Exception as error:
            self.last_error = error
        if self._timer is not None:
            self._arm()
        # Keep input and Ctrl-C active while the application owns GPU/PIO.
        if self._interrupt or (self.keyboard is not None and self.keyboard.any()):
            os.dupterm_notify(self)

    def suspend(self):
        if self._closed or self._suspended or not self._display_owned:
            return False
        if self._busy:
            raise RuntimeError('cannot hand off the display inside a console update')
        try:
            self.paused = self._suspended = True
            self._snapshot_valid = False
            while self._head != self._tail and self.last_error is None:
                self._flush_display(paused_ok=True)
            if self.last_error is not None:
                raise OSError('console display fault; USB input remains available')
            self._cursor(False)
            self.backend.copy_bytes(0, SNAPSHOT, PAGE_BYTES)
            self._snapshot_valid = True
        except BaseException as error:
            self.last_error = error
            raise
        finally:
            self._release_display()
        return True

    def resume(self):
        if self._closed or not self._suspended:
            return False
        try:
            if (not self._snapshot_valid and self.last_error is not None
                    and not isinstance(self.last_error,KeyboardInterrupt)):
                self._suspended = False
                return False
            is_open=getattr(self.backend,'is_open',None)
            if is_open is not None:
                self._display_owned=is_open()
            if not self._display_owned:
                self._open_display()
            if self._snapshot_valid:
                self.backend.copy_bytes(SNAPSHOT, 0, PAGE_BYTES)
            self.backend.present(0)
            self._cursor()
            self.last_error = None
            self.paused = self._suspended = self._snapshot_valid = False
            if self._timer is not None:
                self._arm()
            return True
        except BaseException as error:
            self.last_error = error
            self._suspended = False
            self._release_display()
            if isinstance(error,KeyboardInterrupt):
                raise
            print('Framebuffer REPL restore failed; USB/keyboard retained:', error)
            return False

    def close(self):
        if self._closed:
            return
        if self._suspended:
            raise RuntimeError('finish the application before closing its console')
        self.paused = self._closed = True
        if self._timer is not None:
            self._timer.deinit()
            self._timer = None
        if self._attached:
            os.dupterm(self._previous, 0)
            self._attached = False
        try:
            self._release_display()
        finally:
            try:
                try:
                    if self.keyboard is not None:
                        self.keyboard.close()
                finally:
                    self.font.close()
            finally:
                if self._previous_frequency is not None:
                    from machine import freq
                    freq(self._previous_frequency)


def start(font_path='fonts/mplus12.kmf', keyboard=True, startup_ms=2000):
    global console
    if console is not None and not console._closed:
        return console
    import machine
    import _kagura
    import sys
    directory=os.getcwd()
    if directory not in sys.path:
        sys.path.insert(0,directory)
    from time import ticks_ms, ticks_diff, sleep_ms
    if not hasattr(os, 'dupterm') or not hasattr(os, 'dupterm_notify'):
        raise RuntimeError('dupterm-enabled MicroPython required')
    previous = machine.freq()
    font = keys = result = None
    try:
        machine.freq(120000000)
        try:
            from kagura_ja import Font
            font = Font(font_path, cache=16)
            space=font.glyph(' ')
            if space is None or space[0] not in (6, 8) or not 2<=font.height<=32:
                font.close()
                raise ValueError('console needs an even-width font')
        except (OSError, ValueError):
            font = BuiltinFont()
        if keyboard:
            from kagura_keyboard import Keyboard
            keys = Keyboard()
            keys.configure()
        result = Console(_kagura, font, keys)
        result._previous_frequency = previous
        # An absent FPGA leaves USB and the XLINK keyboard working.
        try:
            ready = machine.Pin(9, machine.Pin.IN, machine.Pin.PULL_DOWN)
            busy = machine.Pin(8, machine.Pin.IN)
            started = ticks_ms()
            while not (ready.value() and not busy.value()):
                if ticks_diff(ticks_ms(), started) >= startup_ms:
                    raise OSError('FPGA not ready')
                sleep_ms(10)
            result._open_display()
            result._cursor()
        except Exception as error:
            result.last_error = error
            result._release_display()
        result._timer = machine.Timer(-1)
        result._tick_callback = _kagura.interrupt_guard(result._tick,result._arm)
        result._previous = os.dupterm(result, 0)
        result._attached = True
        console = result
        result._arm()
        print('KAGURA-HD framebuffer REPL / XIAO XLINK UART0 GP0/GP1')
        if result.last_error is not None:
            print('Framebuffer unavailable; USB/keyboard retained:', result.last_error)
        return result
    except BaseException:
        if result is not None:
            result.close()
        else:
            if keys is not None:
                keys.close()
            if font is not None:
                font.close()
            machine.freq(previous)
        raise


def autostart():
    # Respect user boot/main scripts and their existing hardware ownership.
    for path in ('/boot.py', '/main.py'):
        try:
            os.stat(path)
            return False
        except OSError:
            pass
    try:
        start()
        return True
    except Exception as error:
        print('Framebuffer REPL startup skipped:', error)
        return False
