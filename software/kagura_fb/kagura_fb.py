# SPDX-License-Identifier: Apache-2.0
"""Kagura-FB ABI 1.2 driver. One caller owns a device/transport at a time."""
import time


def _put16(buffer, offset, value):
    buffer[offset] = value & 255
    buffer[offset + 1] = (value >> 8) & 255


def _put32(buffer, offset, value):
    for index in range(4):
        buffer[offset + index] = (value >> (index * 8)) & 255


class SPITransport:
    """Mode-0 SPI object with write/read methods and a CS Pin object."""
    def __init__(self, spi, cs):
        self.spi = spi
        self.cs = cs
        cs.value(1)

    def write(self, address, increment, data):
        self.cs.value(0)
        try:
            self.spi.write(bytes((address | (64 if increment else 0),)))
            self.spi.write(data)
        finally:
            self.cs.value(1)

    def read(self, address, increment, length):
        self.cs.value(0)
        try:
            self.spi.write(bytes((128 | address | (64 if increment else 0), length & 255, 0)))
            return self.spi.read(length, 0)
        finally:
            self.cs.value(1)


class Device:
    def __init__(self, transport, timeout_ms=1000, now_ms=None):
        if not isinstance(timeout_ms, int) or not 0 <= timeout_ms <= 60000:
            raise ValueError("timeout_ms must be 0..60000")
        self.transport = transport
        self.timeout_ms = timeout_ms
        self._now = now_ms or getattr(time, "ticks_ms", lambda: int(time.monotonic() * 1000) & 0xffffffff)
        self._diff = getattr(time, "ticks_diff", lambda now, before: (now - before) & 0xffffffff)
        self.last_device_error = 0
        self._idle()
        identity = transport.read(0, True, 7)
        if identity[:4] != b"KFB1" or identity[4] != 1 or identity[6] & 31 != 31:
            raise ValueError("unsupported Kagura-FB identity/ABI")
        tag = transport.read(28, True, 2)
        self._tag = ((tag[0] | (tag[1] << 8)) + 1) & 65535

    def _read(self, address):
        return self.transport.read(address, False, 1)[0]

    def _write(self, address, value):
        self.transport.write(address, False, bytes((value,)))

    def _expired(self, started):
        return self._diff(self._now(), started) >= self.timeout_ms

    def _idle(self):
        started = self._now()
        while True:
            status = self._read(27)
            if status & 128:
                raise OSError(6, "SPI timing error")
            if status & 3 == 2:
                return
            if self._expired(started):
                raise OSError(110, "Kagura-FB idle timeout")

    def submit(self, command, payload=None):
        if len(command) != 16:
            raise ValueError("GPU command must be 16 bytes")
        command = bytearray(command)
        if payload is not None:
            payload = memoryview(payload)
            if len(payload) > 64:
                raise ValueError("GPU payload exceeds 64 bytes")
            if not len(payload):
                payload = None
        self._idle()
        tag = self._tag
        self._tag = (tag + 1) & 65535
        _put16(command, 2, tag)
        self.last_device_error = 0
        self._write(7, 0)
        if payload is not None:
            self._write(25, 0)
            self.transport.write(24, False, payload)
        self.transport.write(8, True, command)
        self._write(26, 1)
        # A failed transfer can have reached the FPGA. Never resend it here.
        return tag

    def _execute(self, command, payload=None):
        self.wait(self.submit(command, payload))

    def wait(self, tag):
        if not isinstance(tag, int) or not 0 <= tag <= 65535:
            raise ValueError("GPU tag outside range")
        started = self._now()
        while True:
            status = self._read(27)
            if status & 128:
                raise OSError(6, "SPI timing error")
            if status & 17 == 16:
                result = self.transport.read(28, True, 3)
                if result[0] | (result[1] << 8) == tag:
                    self.last_device_error = result[2] or self._read(7)
                    self._write(31, 1)
                    if self.last_device_error:
                        raise OSError(self.last_device_error, "Kagura-FB command failed")
                    return
            if self._expired(started):
                raise OSError(110, "Kagura-FB completion timeout")

    def fence(self):
        self._execute(bytearray(16))

    def fill_rect(self, page, x, y, width, height, color):
        for value in (page, x, y, width, height, color):
            if not isinstance(value, int):
                raise TypeError("fill arguments must be integers")
        if page not in (0, 1) or not 0 <= color <= 15:
            raise ValueError("invalid page or color")
        if width <= 0 or height <= 0:
            return
        left, top = max(x, 0), max(y, 0)
        right, bottom = min(x + width, 640), min(y + height, 360)
        if right <= left or bottom <= top:
            return
        command = bytearray(16)
        command[0], command[1], command[12] = 1, page, color
        _put16(command, 4, left)
        _put16(command, 6, top)
        _put16(command, 8, right - left)
        _put16(command, 10, bottom - top)
        self._execute(command)

    def copy_rect(self, src_page, sx, sy, dst_page, dx, dy, width, height):
        """Opaque overlap-safe copy; strict bounds, even pixels, same word phase."""
        for value in (src_page, sx, sy, dst_page, dx, dy, width, height):
            if not isinstance(value, int):
                raise TypeError("copy arguments must be integers")
        if (src_page not in (0, 1) or dst_page not in (0, 1)
                or not 0 <= sx < 640 or not 0 <= dx < 640
                or not 0 <= sy < 360 or not 0 <= dy < 360
                or width < 0 or height < 0
                or max(sx, dx) + width > 640 or max(sy, dy) + height > 360
                or (sx | dx | width) & 1 or (sx ^ dx) & 7):
            raise ValueError("copy outside pages or unsupported alignment")
        if not width or not height or (src_page == dst_page and sx == dx and sy == dy):
            return
        if not self._read(6) & 64:
            raise ValueError("aligned copy capability missing")
        command = bytearray(16)
        command[0], command[1] = 6, src_page | (dst_page << 1)
        for offset, value in ((4, sx), (6, sy), (8, dx), (10, dy), (12, width), (14, height)):
            _put16(command, offset, value)
        self._execute(command)

    def palette(self, index, rgb444):
        if not isinstance(index, int) or not isinstance(rgb444, int):
            raise TypeError("palette arguments must be integers")
        if not 0 <= index <= 15 or not 0 <= rgb444 <= 4095:
            raise ValueError("invalid palette entry")
        command = bytearray(16)
        command[0], command[1] = 2, index
        _put16(command, 4, rgb444)
        self._execute(command)

    def present(self, page):
        if not isinstance(page, int) or page not in (0, 1):
            raise ValueError("invalid page")
        command = bytearray(16)
        command[0], command[1] = 3, page
        self._execute(command)

    @staticmethod
    def _range(address, length):
        if not isinstance(address, int) or not isinstance(length, int):
            raise TypeError("memory range must be integer")
        if address < 0 or length < 0 or address > 4194304 or length > 4194304 - address:
            raise ValueError("memory range outside PSRAM")

    def write_bytes(self, address, data):
        data = memoryview(data)
        self._range(address, len(data))
        offset = 0
        while offset < len(data):
            prefix = address & 3
            count = min(64 - prefix, len(data) - offset)
            span = (prefix + count + 3) & ~3
            payload = bytearray(span)
            payload[prefix:prefix + count] = data[offset:offset + count]
            mask = (1 << 64) - 1
            for index in range(prefix, prefix + count):
                mask &= ~(1 << index)
            command = bytearray(16)
            command[0], command[1] = 4, span // 4
            _put32(command, 4, address & ~3)
            for index in range(8):
                command[8 + index] = (mask >> (index * 8)) & 255
            self._execute(command, payload)
            address += count
            offset += count

    def read_into(self, address, data):
        data = memoryview(data)
        if len(data):
            data[0] = data[0]  # Check writability before starting a memory command.
        self._range(address, len(data))
        offset = 0
        while offset < len(data):
            prefix = address & 3
            count = min(64 - prefix, len(data) - offset)
            span = (prefix + count + 3) & ~3
            command = bytearray(16)
            command[0], command[1] = 5, span // 4
            _put32(command, 4, address & ~3)
            self._execute(command)
            self._write(25, 0)
            payload = self.transport.read(24, False, span)
            data[offset:offset + count] = payload[prefix:prefix + count]
            address += count
            offset += count

    def read_bytes(self, address, length):
        self._range(address, length)
        result = bytearray(length)
        self.read_into(address, result)
        return result


    def _cursor_available(self):
        if not self._read(6) & 32:
            raise ValueError("cursor capability missing")
        if self._read(27) & 128:
            raise OSError(6, "SPI timing error")

    def _cursor_check(self):
        self.last_device_error = self._read(53)
        if self.last_device_error:
            raise OSError(self.last_device_error, "cursor device error")

    def _cursor_begin(self):
        self._cursor_available()
        self.last_device_error = 0
        self._write(53, 0)

    def cursor_status(self):
        self._cursor_available()
        status = self._read(50)
        generation = self.transport.read(51, True, 2)
        self._cursor_check()
        return status, generation[0] | (generation[1] << 8)

    def cursor_shape(self, bank, shape, colors, hotspot=(0, 0)):
        shape = memoryview(shape)
        if not isinstance(bank, int) or bank not in (0, 1) or len(shape) != 256 or len(colors) != 3 or len(hotspot) != 2:
            raise ValueError("cursor needs bank 0/1, 256 bytes, 3 colors and hotspot pair")
        for color in colors:
            if not isinstance(color, int) or not 0 <= color <= 4095:
                raise ValueError("cursor RGB444 color outside range")
        for coordinate in hotspot:
            if not isinstance(coordinate, int) or not 0 <= coordinate <= 31:
                raise ValueError("cursor hotspot outside range")
        self._cursor_begin()
        status = self._read(50)
        if status & 1 or (status >> 1) & 1 == bank:
            self.last_device_error = 1
            raise OSError(1, "cursor bank busy")
        self.transport.write(46, True, bytes((0, bank)))
        self.transport.write(37, True, bytes(hotspot))
        palette = bytearray(6)
        for index in range(3):
            _put16(palette, index * 2, colors[index])
        self.transport.write(39, True, palette)
        for offset in range(0, 256, 64):
            self.transport.write(48, False, shape[offset:offset + 64])
        self._cursor_check()

    def cursor_move(self, x, y, bank, visible=True):
        if (not isinstance(x, int) or not isinstance(y, int) or not isinstance(bank, int)
                or not -1024 <= x <= 1023 or not -1024 <= y <= 1023 or bank not in (0, 1)):
            raise ValueError("cursor position or bank outside range")
        self._cursor_begin()
        pose = bytearray(5)
        pose[0] = bank * 2 + bool(visible)
        _put16(pose, 1, x & 65535)
        _put16(pose, 3, y & 65535)
        self.transport.write(32, True, pose)
        self._write(49, 1)
        self._cursor_check()  # Submission only; wait separately for vblank.

    def cursor_wait(self):
        self._cursor_available()
        started = self._now()
        while True:
            status = self._read(50)
            self._cursor_check()
            if not status & 1:
                generation = self.transport.read(51, True, 2)
                self._write(50, 64)
                return generation[0] | (generation[1] << 8)
            if self._expired(started):
                raise OSError(110, "cursor update timeout")


def connect_rp2040(baudrate=1000000, timeout_ms=1000):
    """SoftSPI on the existing GP2/3 data, GP6 clock, GP7 CS wiring."""
    from machine import Pin, SoftSPI
    spi = SoftSPI(baudrate=baudrate, polarity=0, phase=0,
                  sck=Pin(6), mosi=Pin(2), miso=Pin(3))
    return Device(SPITransport(spi, Pin(7, Pin.OUT, value=1)), timeout_ms)
