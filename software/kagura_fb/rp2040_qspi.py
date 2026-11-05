# SPDX-License-Identifier: Apache-2.0
"""Slow KFB1 QSPI bring-up transport; call only after releasing other pin owners.

GPIO2..5=IO0..3, GPIO6=SCK, GPIO7=CS. No PIO, DMA or clock changes.
The software overhead makes the actual clock slower than 1/(2*half_period_us).
This backend is for diagnostics, not throughput measurements.
"""


class QSPITransport:
    def __init__(self, half_period_us=5):
        if not isinstance(half_period_us, int) or not 5 <= half_period_us <= 1000:
            raise ValueError("half_period_us must be 5..1000")
        from machine import Pin
        from time import sleep_us
        self._Pin = Pin
        self._sleep = sleep_us
        self._half = half_period_us
        self.cs = Pin(7, Pin.OUT, value=1)
        self.sck = Pin(6, Pin.OUT, value=0)
        self.io = [Pin(i, Pin.IN) for i in range(2, 6)]

    def _delay(self):
        self._sleep(self._half)

    def _edge(self):
        self._delay()
        self.sck.value(1)
        self._delay()
        self.sck.value(0)

    def _send(self, value):
        for shift in (4, 0):
            nibble = value >> shift
            for bit, pin in enumerate(self.io):
                pin.value((nibble >> bit) & 1)
            self._edge()

    def _receive(self):
        result = 0
        for _ in range(2):
            # FPGA advances its output after detecting the rising edge.
            # Sample the stable current nibble before issuing that edge.
            self._delay()
            nibble = sum(pin.value() << bit for bit, pin in enumerate(self.io))
            result = (result << 4) | nibble
            self._edge()
        return result

    def _begin(self):
        self.cs.value(1)
        self.sck.value(0)
        self._delay()
        for pin in self.io:
            pin.init(self._Pin.OUT, value=0)
        self.cs.value(0)
        self._delay()

    def deinit(self):
        self.cs.value(1)
        self.sck.value(0)
        # Let FPGA observe deselection before releasing/reusing data pins.
        self._delay()
        for pin in self.io:
            pin.init(self._Pin.IN)

    @staticmethod
    def _address(address):
        if not isinstance(address, int) or not 0 <= address <= 63:
            raise ValueError("KFB1 register address must be 0..63")

    def write(self, address, increment, data):
        self._address(address)
        data = memoryview(data)
        try:
            self._begin()
            self._send(address | (64 if increment else 0))
            for value in data:
                self._send(value)
        finally:
            self.deinit()

    def read(self, address, increment, length):
        self._address(address)
        if not isinstance(length, int) or not 1 <= length <= 256:
            raise ValueError("read length must be 1..256")
        result = bytearray(length)
        try:
            self._begin()
            self._send(128 | address | (64 if increment else 0))
            self._send(length & 255)
            # Release before the FIRST dummy edge to avoid bus contention.
            for pin in self.io:
                pin.init(self._Pin.IN)
            self._edge()
            self._edge()  # exactly one byte (two nibbles) of dummy clocks
            self._delay()
            for index in range(length):
                result[index] = self._receive()
            return result
        finally:
            self.deinit()
