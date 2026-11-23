# SPDX-License-Identifier: Apache-2.0
"""XLINK USB-keyboard bridge -> MicroPython REPL bytes (UART0 GP0/GP1).

Only CRC-checked KEY/down events become input. Never attach framed UART data
directly with os.dupterm(UART). KAGURA-HD bridge status is informational.
"""
import time


def crc8(data):
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (7 if crc & 128 else 0)) & 255
    return crc


def frame(kind, payload):
    body = bytes((kind, len(payload))) + payload
    return b'\x7e' + body + bytes((crc8(body),))


_SPECIAL = {0x28: b'\r', 0x29: b'\x1b', 0x2a: b'\x08', 0x2b: b'\t',
            0x49: b'\x1b[2~', 0x4a: b'\x1b[H', 0x4b: b'\x1b[5~',
            0x4c: b'\x1b[3~', 0x4d: b'\x1b[F', 0x4e: b'\x1b[6~',
            0x4f: b'\x1b[C', 0x50: b'\x1b[D', 0x51: b'\x1b[B', 0x52: b'\x1b[A'}


class Keyboard:
    def __init__(self, uart=None, now_ms=None, buffer_size=256):
        if not isinstance(buffer_size, int) or buffer_size < 8:
            raise ValueError('keyboard ring must be at least 8 bytes')
        self._owns_uart = uart is None
        self._rx_pin = self._tx_pin = None
        self._high_since = None
        self._configuration = None
        if uart is None:
            from machine import Pin
            # Announce host power without starting an RX interrupt on an unknown
            # or unprogrammed module holding RX low. The XIAO waits for TX high.
            self._tx_pin = Pin(0, Pin.OUT, value=1)
            self._rx_pin = Pin(1, Pin.IN, Pin.PULL_DOWN)
        self.uart = uart
        self._now = now_ms or getattr(time, 'ticks_ms', lambda: int(time.monotonic() * 1000))
        self._diff = getattr(time, 'ticks_diff', lambda a, b: a - b)
        self._buffer = bytearray(buffer_size)
        self._head = self._tail = 0
        self._packet = bytearray()
        self._expected = None
        self._last_byte = self._now()
        self._rx = bytearray(128)
        self.interrupt = False
        self.bad_frames = self.dropped = self.events = 0
        self.bridge_version = None
        self.connected = None
        self.last_status_ms = None
        self._closed = False

    def configure(self, delay_ms=500, period_ms=33):
        if not 250 <= delay_ms <= 2000 or not 10 <= period_ms <= 500:
            raise ValueError('invalid repeat interval')
        self._configuration = bytes((1, 1, delay_ms & 255, delay_ms >> 8,
                                     period_ms & 255, period_ms >> 8, 0))
        if self.uart is not None:
            self.uart.write(frame(0x85, b'KHD1'))
            self.uart.write(frame(0x83, self._configuration))

    def _open_uart(self):
        if not self._rx_pin.value():
            self._high_since = None
            return
        now = self._now()
        if self._high_since is None:
            self._high_since = now
            return
        if self._diff(now, self._high_since) < 5:
            return
        from machine import UART, Pin
        self.uart = UART(0, baudrate=115200, bits=8, parity=None, stop=1,
                         tx=Pin(0), rx=Pin(1), timeout=0, timeout_char=0, rxbuf=512)
        if self._configuration is not None:
            self.uart.write(frame(0x85, b'KHD1'))
            self.uart.write(frame(0x83, self._configuration))

    def any(self):
        return self.interrupt or self._head != self._tail

    def _emit(self, data):
        if data == b'\x03':
            self.interrupt = True
            return
        free = (self._tail - self._head - 1) % len(self._buffer)
        if len(data) > free:
            self.dropped += len(data)
            return  # keep terminal escape sequences atomic
        for value in data:
            self._buffer[self._head] = value
            self._head = (self._head + 1) % len(self._buffer)

    def _handle(self, packet):
        kind, size = packet[0], packet[1]
        payload = packet[2:-1]
        if kind == 0xc5 and size == 6 and payload[:4] == b'KHDK':
            self.bridge_version, self.connected = payload[4], bool(payload[5])
            self.last_status_ms = self._now()
        elif kind == 1 and size == 4:
            usage, modifiers, flags, code = payload
            if not flags & 1 or usage >= 0xe0:
                return
            self.events += 1
            if modifiers & 0x11 or flags & 8:
                if 4 <= usage <= 0x1d:
                    self._emit(bytes((usage - 3,)))
                elif code in (ord('['), ord('\\'), ord(']'), ord('^'), ord('_')):
                    self._emit(bytes((code & 31,)))
                elif code == ord(' '):
                    self._emit(b'\0')
                return
            sequence = _SPECIAL.get(usage)
            if sequence is None and 32 <= code <= 126:
                sequence = bytes((code,))
            if sequence is not None:
                self._emit((b'\x1b' if modifiers & 0x44 else b'') + sequence)

    def feed(self, data):
        for value in data:
            now = self._now()
            if self._diff(now, self._last_byte) > 100:
                self._packet = bytearray()
                self._expected = None
            self._last_byte = now
            if self._expected is None:
                if value == 0x7e:
                    self._packet = bytearray()
                    self._expected = 0
                continue
            self._packet.append(value)
            if len(self._packet) == 2:
                size = self._packet[1]
                if size > 64:
                    self.bad_frames += 1
                    self._expected = None
                    continue
                self._expected = size + 3
            if self._expected and len(self._packet) == self._expected:
                valid = crc8(self._packet[:-1]) == self._packet[-1]
                if valid:
                    self._handle(self._packet)
                else:
                    self.bad_frames += 1
                self._expected = 0 if not valid and value == 0x7e else None
                self._packet = bytearray()

    def poll(self):
        if self._closed:
            return
        if self.uart is None:
            self._open_uart()
        if self.uart is not None and self.uart.any():
            n = self.uart.readinto(self._rx)
            if n:
                self.feed(memoryview(self._rx)[:n])

    def readinto(self, buffer):
        if not len(buffer):
            return 0
        if self.interrupt:
            self.interrupt = False
            buffer[0] = 3
            return 1
        count = min(len(buffer), (self._head - self._tail) % len(self._buffer))
        if not count:
            return None
        for index in range(count):
            buffer[index] = self._buffer[self._tail]
            self._tail = (self._tail + 1) % len(self._buffer)
        return count

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._owns_uart:
            if self.uart is not None:
                self.uart.deinit()
            from machine import Pin
            self._tx_pin.init(Pin.IN)
            self._rx_pin.init(Pin.IN, Pin.PULL_DOWN)
