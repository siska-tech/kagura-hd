# SPDX-License-Identifier: Apache-2.0
"""KAGURA-HD QSPI: KAGURA-9 PIO timing, Viper FIFO pump, optional TX DMA.

Stock RP2040 MicroPython; six-bit register addresses, no legacy BUSY byte flags.
One owner per state machine. No CPU clock changes or automatic transfer retry.
"""
from array import array
from machine import Pin, freq, mem32
from time import sleep_us, sleep_ms
import rp2
import micropython


@rp2.asm_pio(out_init=(rp2.PIO.IN_LOW,) * 4,
             set_init=(rp2.PIO.IN_LOW,) * 4, sideset_init=rp2.PIO.OUT_LOW,
             out_shiftdir=rp2.PIO.SHIFT_LEFT, in_shiftdir=rp2.PIO.SHIFT_LEFT,
             autopush=True, push_thresh=8)
def _qspi():
    wrap_target()
    label('top')
    pull(block).side(0)
    out(x, 1).side(0)
    jmp(not_x, 'start').side(0)
    wait(0, gpio, 8).side(0)  # bit31 is always zero in the HD protocol
    label('start')
    out(y, 1).side(0)
    out(pins, 4).side(0)[4]
    in_(pins, 4).side(0)
    nop().side(1)[5]
    out(pins, 4).side(0)[4]
    in_(pins, 4).side(0)
    nop().side(1)[5]
    jmp(not_y, 'top').side(0)
    set(pindirs, 0).side(0)
    wrap()


_owned = set()


@micropython.viper
def _transaction_kernel(source, destination, settings) -> int:
    c = ptr32(settings)
    pio = ptr32(c[0])
    sio = ptr32(0xd0000000)
    timer = ptr32(0x40054000)
    tx = ptr8(source)
    rx = ptr8(destination)
    sm = int(c[1])
    n = int(c[2])
    header = int(c[3])
    reading = int(c[6])
    timeout = uint(c[7])
    pio[54 + sm * 6] = c[8]
    t = uint(timer[10])
    while uint(uint(timer[10]) - t) < uint(1): pass
    sio[6] = uint(128)
    t = uint(timer[10])
    while uint(uint(timer[10]) - t) < uint(1): pass
    use_dma = int(c[16]) != 0 and reading == 0 and n - header >= 16 and n - header <= 64
    limit = header if use_dma else n
    sent = 0
    got = 0
    started = uint(timer[10])
    serviced = started
    while got < limit:
        status = uint(pio[1])
        if sent < limit and (status & (uint(1) << (16 + sm))) == uint(0):
            value = uint(0)
            if sent < header:
                value = uint(c[4 + sent])
            elif reading == 0:
                value = uint(tx[sent - header])
            value <<= 22
            if reading and sent == 1:
                value |= uint(0x40000000)
            pio[4 + sm] = value
            sent += 1
        if (status & (uint(1) << (8 + sm))) == uint(0):
            value = uint(pio[8 + sm])
            if reading and got >= 3:
                rx[got - 3] = value
            got += 1
        now = uint(timer[10])
        if uint(now - started) >= timeout: return -1
        if uint(now - serviced) >= uint(4000):
            sleep_ms(0)
            serviced = now
    if use_dma:
        dma = ptr32(0x50000000)
        words = ptr32(c[14])
        count = n - header
        for i in range(count): words[i] = uint(tx[i]) << 22
        a = int(c[10]) * 16
        b = int(c[11]) * 16
        dma[b] = c[0] + uint(0x20) + uint(sm * 4)
        dma[b + 1] = c[15]
        dma[b + 2] = uint(count)
        dma[b + 3] = c[13]
        dma[a] = c[14]
        dma[a + 1] = c[0] + uint(0x10) + uint(sm * 4)
        dma[a + 2] = uint(count)
        dma[a + 3] = c[12]
        while (uint(dma[a + 3]) | uint(dma[b + 3])) & uint(0x01000000):
            now = uint(timer[10])
            if uint(now - started) >= timeout: return -1
            if uint(now - serviced) >= uint(4000):
                sleep_ms(0)
                serviced = now
        if dma[a + 2] or dma[b + 2] or ((uint(dma[a + 3]) | uint(dma[b + 3])) & uint(0x60000000)):
            return -2
    t = uint(timer[10])
    while uint(uint(timer[10]) - t) < uint(2): pass
    sio[5] = uint(128)
    t = uint(timer[10])
    while uint(uint(timer[10]) - t) < uint(1): pass
    pio[54 + sm * 6] = c[9]
    return 0


@micropython.viper
def _gpu_kernel(command, payload, scratch, settings, timeout_us: int) -> int:
    # One synchronous GPU command, preserving the ordinary register protocol.
    # Every CS interval still goes through the same proven PIO/DMA kernel.
    c = ptr32(settings)
    reply = ptr8(scratch)
    desc = ptr8(command)
    timer = ptr32(0x40054000)
    tag = int(desc[2]) | (int(desc[3]) << 8)
    started = uint(timer[10])
    serviced = started
    for stage in range(2):
        while True:
            c[2] = 4; c[3] = 2; c[4] = 155; c[5] = 1; c[6] = 1
            result = int(_transaction_kernel(scratch, scratch, settings))
            if result: return result
            status = int(reply[0])
            if status & 128: return -4
            if stage == 0 and status & 3 == 2: break
            if stage == 1 and status & 17 == 16:
                c[2] = 6; c[4] = 220; c[5] = 3
                result = int(_transaction_kernel(scratch, scratch, settings))
                if result: return result
                if int(reply[0]) | (int(reply[1]) << 8) == tag:
                    error = int(reply[2])
                    if error == 0:
                        c[2] = 4; c[4] = 135; c[5] = 1
                        result = int(_transaction_kernel(scratch, scratch, settings))
                        if result: return result
                        error = int(reply[0])
                    reply[0] = 1
                    c[2] = 2; c[3] = 1; c[4] = 31; c[6] = 0
                    result = int(_transaction_kernel(scratch, scratch, settings))
                    if result: return result
                    return error
            now = uint(timer[10])
            if uint(now - started) >= uint(timeout_us): return -3
            if uint(now - serviced) >= uint(4000):
                sleep_ms(0)
                serviced = now
        reply[0] = 0
        c[2] = 2; c[3] = 1; c[4] = 7; c[6] = 0
        result = int(_transaction_kernel(scratch, scratch, settings))
        if result: return result
        count = int(len(payload))
        if count:
            c[4] = 25
            result = int(_transaction_kernel(scratch, scratch, settings))
            if result: return result
            c[2] = count + 1; c[4] = 24
            result = int(_transaction_kernel(payload, scratch, settings))
            if result: return result
        c[2] = 17; c[4] = 72
        result = int(_transaction_kernel(command, scratch, settings))
        if result: return result
        reply[0] = 1
        c[2] = 2; c[4] = 26
        result = int(_transaction_kernel(scratch, scratch, settings))
        if result: return result
        started = uint(timer[10])
    return -3


class PIOTransport:
    # This connection owns a single FPGA configuration; reconnect after reload.
    capabilities_stable = True

    def __init__(self, baudrate=5_000_000, sm_id=0, timeout_us=100_000, dma=True):
        if not isinstance(baudrate, int) or not 100_000 <= baudrate <= 8_000_000 or baudrate * 12 > freq():
            raise ValueError('QSPI rate must be 100 kHz..8 MHz and PIO clock <= CPU clock')
        if sm_id not in range(8) or sm_id in _owned or not 1 <= timeout_us <= 10_000_000:
            raise ValueError('state machine already owned or invalid configuration')
        self.baudrate, self.sm_id = baudrate, sm_id
        self.timeout_us = timeout_us
        self._active = self._closed = False
        self.cs = Pin(7, Pin.OUT, value=1)
        self.sck = Pin(6, Pin.OUT, value=0)
        self.io = [Pin(i, Pin.IN) for i in range(2, 6)]
        self._out = rp2.asm_pio_encode('set(pindirs, 15)', 1)
        self._in = rp2.asm_pio_encode('set(pindirs, 0)', 1)
        self._config = array('I', [0x50200000 + (sm_id // 4) * 0x100000, sm_id % 4, 0, 0, 0, 0, 0, timeout_us, self._out, self._in, 0, 0, 0, 0, 0, 0, 0])
        self._dummy = bytearray(256)
        self._reply = bytearray(4)
        self._words = array('I', [0] * 64)
        self._sink = bytearray(4)
        self._tx = self._rx = None
        self._sm = rp2.StateMachine(sm_id)
        _owned.add(sm_id)
        try:
            for pin in range(2, 8):
                address = 0x4001c004 + 4 * pin
                mem32[address] = (mem32[address] & ~0x31) | 2  # 2mA, slow slew, Schmitt
            self._init()
            if dma and hasattr(rp2, 'DMA'):
                self._tx = rp2.DMA()
                self._rx = rp2.DMA()
                dreq = (sm_id // 4) * 8 + sm_id % 4
                self._tx_ctrl = self._tx.pack_ctrl(size=2, inc_read=True, inc_write=False, treq_sel=dreq)
                self._rx_ctrl = self._rx.pack_ctrl(size=2, inc_read=False, inc_write=False, treq_sel=dreq + 4)
                from uctypes import addressof
                self._config[10] = self._tx.channel
                self._config[11] = self._rx.channel
                self._config[12] = self._tx_ctrl
                self._config[13] = self._rx_ctrl
                self._config[14] = addressof(self._words)
                self._config[15] = addressof(self._sink)
                self._config[16] = 1
        except BaseException:
            self.deinit()
            raise

    def _init(self):
        self._sm.init(_qspi, freq=self.baudrate * 12, out_base=Pin(2), set_base=Pin(2),
                      in_base=Pin(2), sideset_base=Pin(6))
        self._sm.active(1)

    def _abort(self):
        for channel in (self._tx, self._rx):
            if channel is not None:
                channel.active(0)
        self._sm.active(0)
        self.cs(1)
        sleep_us(1)
        self._init()
        self._active = False

    def write(self, address, increment, data):
        if not isinstance(address, int) or not 0 <= address <= 63:
            raise ValueError('six-bit register address required')
        if self._closed or self._active:
            raise RuntimeError('QSPI transport closed or already active')
        try:
            self._active = True
            c = self._config
            c[2], c[3], c[4], c[6] = len(data) + 1, 1, address | (64 if increment else 0), 0
            result = _transaction_kernel(data, self._dummy, c)
            if result: raise OSError(110 if result == -1 else 5, 'QSPI transfer failed; outcome may be partial')
            self._active = False
        except BaseException:
            self._abort()
            raise

    def read(self, address, increment, length):
        if not isinstance(address, int) or not 0 <= address <= 63 or not 1 <= length <= 256:
            raise ValueError('invalid six-bit register address or read length')
        if self._closed or self._active:
            raise RuntimeError('QSPI transport closed or already active')
        result = bytearray(length)
        try:
            self._active = True
            c = self._config
            c[2], c[3], c[4], c[5], c[6] = length + 3, 2, 128 | address | (64 if increment else 0), length & 255, 1
            status = _transaction_kernel(self._dummy, result, c)
            if status: raise OSError(110 if status == -1 else 5, 'QSPI transfer failed; outcome may be partial')
            self._active = False
        except BaseException:
            self._abort()
            raise
        return result

    def execute_command(self, command, payload, timeout_ms):
        if len(command) != 16 or len(payload) > 64:
            raise ValueError('invalid GPU descriptor or payload')
        if self._closed or self._active:
            raise RuntimeError('QSPI transport closed or already active')
        try:
            self._active = True
            result = _gpu_kernel(command, payload, self._reply, self._config, timeout_ms * 1000)
            if result < 0:
                raise OSError(6 if result == -4 else 110 if result in (-1, -3) else 5,
                              'GPU transfer failed; outcome may be partial')
            self._active = False
            return result
        except BaseException:
            self._abort()
            raise

    def deinit(self):
        if self._closed:
            return
        for channel in (self._tx, self._rx):
            if channel is not None:
                channel.active(0)
                channel.close()
        self._sm.active(0)
        self.cs(1)
        self.sck.init(Pin.OUT, value=0)
        for pin in self.io:
            pin.init(Pin.IN)
        try:
            rp2.PIO(self.sm_id // 4).remove_program(_qspi)
        except ValueError:
            pass
        _owned.discard(self.sm_id)
        self._closed = True


def connect(baudrate=5_000_000, timeout_ms=1000, native=True, **options):
    if native:
        from kagura_native_commands import NativeDevice as Device
    else:
        from kagura_fb import Device
    transport = PIOTransport(baudrate, **options)
    try:
        return Device(transport, timeout_ms)
    except BaseException:
        transport.deinit()
        raise
