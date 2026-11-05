# SPDX-License-Identifier: Apache-2.0
"""RAM-only KFB1 diagnostics. Requires exclusive GPIO ownership and a gated FPGA.

Does not modify firmware, filesystem, boot files or FPGA Flash. Stop on any error;
the caller must restore the known-good FPGA configuration before restarting KAGURA-9.
"""


def run(Device=None, QSPITransport=None):
    from machine import Pin
    from time import ticks_us, ticks_diff, sleep_ms
    import json
    # Optional classes allow loading all three source files with exec() into a
    # RAM namespace on MicroPython, without creating modules or device files.
    if Device is None:
        from kagura_fb import Device
    if QSPITransport is None:
        from rp2040_qspi import QSPITransport

    def log(event, **data):
        data["event"] = event
        print("KFB1 " + json.dumps(data))

    ready = Pin(9, Pin.IN)
    busy = Pin(8, Pin.IN)
    irq = Pin(10, Pin.IN)
    started = ticks_us()
    while not ready.value():
        if ticks_diff(ticks_us(), started) >= 3000000:
            raise OSError("FPGA READY timeout; no commands sent")
        sleep_ms(1)
    transport = QSPITransport(half_period_us=5)
    try:
        identity = transport.read(0, True, 7)
        if identity != b"KFB1\x01\x02\x7f":
            raise ValueError("KFB1 ABI 1.2/capability mismatch: " + repr(identity))
        log("identity", identity=list(identity), ready=ready.value(),
            busy=busy.value(), irq_n=irq.value(), half_period_us=5)
        gpu = Device(transport, timeout_ms=3000)
        gpu.fence()
        log("fence_pass")

        # Outside framebuffer pages and the diagnostic PCM area 240000..240127.
        address = 300000
        previous = gpu.read_bytes(address, 64)
        pattern = bytes((i * 37 + 11) & 255 for i in range(64))
        gpu.write_bytes(address, pattern)
        if gpu.read_bytes(address, 64) != pattern:
            raise ValueError("PSRAM scratch readback mismatch")
        gpu.write_bytes(address, previous)
        if gpu.read_bytes(address, 64) != previous:
            raise ValueError("PSRAM scratch restoration mismatch")
        log("scratch_read_write_pass", address=address, length=64)

        colors = (0x000, 0xfff, 0xf00, 0x0f0, 0x00f, 0xff0, 0xf0f, 0x0ff)
        for index, color in enumerate(colors):
            gpu.palette(index, color)
        gpu.fill_rect(1, 0, 0, 640, 360, 2)
        # Distinct corner tiles, one odd-nibble rectangle and the final pixel.
        for x, y, color in ((0, 0, 3), (624, 0, 4), (0, 344, 5), (624, 344, 6)):
            gpu.fill_rect(1, x, y, 16, 16, color)
        gpu.fill_rect(1, 31, 31, 3, 3, 7)
        gpu.fill_rect(1, 639, 359, 1, 1, 1)
        base = 115200
        if gpu.read_bytes(base, 4) != b"\x33" * 4:
            raise ValueError("top-left fill readback mismatch")
        if gpu.read_bytes(base + 115196, 4) != b"\x66\x66\x66\x61":
            raise ValueError("final pixel readback mismatch")
        if gpu.read_bytes(base + 31 * 320 + 15, 2) != b"\x27\x77":
            raise ValueError("odd-nibble fill mismatch")
        gpu.present(1)
        gpu.fence()
        log("fill_palette_present_readback_pass", displayed_page=1)

        samples = []
        for _ in range(5):
            start = ticks_us()
            gpu.copy_rect(1, 0, 0, 0, 0, 0, 640, 360)
            samples.append(ticks_diff(ticks_us(), start))
        if gpu.read_bytes(0, 16) != gpu.read_bytes(base, 16):
            raise ValueError("cross-page BLIT readback mismatch")
        for page in (0, 1, 0, 1):
            gpu.present(page)
        log("cross_page_copy_present_pass", host_round_trip_us=samples,
            timing_scope="includes slow Python transport; not isolated engine latency")

        bank = 1 - ((gpu.cursor_status()[0] >> 1) & 1)
        gpu.cursor_shape(bank, b"\x55" * 256, (0xfff, 0xf00, 0x0f0), (16, 16))
        generations = []
        for x, y in ((-8, -8), (639, 359), (320, 180)):
            gpu.cursor_move(x, y, bank)
            generations.append(gpu.cursor_wait())
        gpu.fence()
        status = transport.read(27, False, 1)[0]
        error = transport.read(7, False, 1)[0]
        log("cursor_pass", generations=generations, status=status, error=error,
            ready=ready.value(), busy=busy.value(), irq_n=irq.value())
        if error or status & 0x8c:
            raise OSError("GPU reports video/audio/transport error")
        log("minimum_diagnostics_complete", note="capture and remaining acceptance tests required")
    finally:
        transport.deinit()
