"""RAM-only ISO1 test. Import has no IO. Caller owns connection, logging and recovery.

Never uses PSRAM; board must have the separately approved ISO1 bitstream.
No retry, sweep, device connection, reset, file write or firmware programming.
"""

def _record(emit, stage, expected, actual):
    expected, actual = bytes(expected), bytes(actual)
    differences = [i for i in range(min(len(expected), len(actual))) if expected[i] != actual[i]]
    emit(dict(test_id=1, stage=stage, address=300032, length=len(expected),
              expected=expected.hex(), actual=actual.hex(),
              xor=bytes(a ^ b for a, b in zip(expected, actual)).hex(), error_bytes=differences,
              match=expected == actual))
    if expected != actual:
        raise ValueError('ISO1 mismatch; STOP, no retry: ' + stage)

def _trace_idle(gpu, expected_count):
    started = gpu._now()
    while True:
        status = gpu._read(36)
        if status & 8 or status & 3 != expected_count:
            raise ValueError('ISO1 unexpected count/fault; STOP, no retry')
        if not status & 48:
            if bool(status & 4) != (expected_count == 2):
                raise ValueError('ISO1 unexpected freeze; STOP')
            return status
        if gpu._expired(started):
            raise OSError(110, 'ISO1 trace timeout; STOP, no retry')

def run_write(gpu, emit):
    # Caller must persist each emitted record synchronously before returning.
    identity = gpu.transport.read(32, True, 7)
    emit(dict(test_id=1, stage='diagnostic_identity', actual=identity.hex()))
    if identity != b'ISO1\x00\x01\x04':
        raise ValueError('ISO1 identity/state differs; STOP before commands')
    payload = bytes.fromhex('ed0f2143')
    gpu._idle()
    gpu._write(25, 0)
    gpu.transport.write(24, False, payload)
    gpu._write(25, 0)
    _record(emit, 'upload_echo', payload, gpu.transport.read(24, False, 4))
    emit(dict(test_id=1, stage='write_intent', address=300032, length=4,
              expected=payload.hex(), mask='fffffffffffffff0'))
    gpu.write_bytes(300032, payload)
    _trace_idle(gpu, 1)
    emit(dict(test_id=1, stage='write_complete_wait_for_pc_trace', psram_tested=False))

def run_read(gpu, emit):
    # Call only after the PC has validated frame 1, including its CRC and TX data.
    _trace_idle(gpu, 1)
    emit(dict(test_id=1, stage='read_injection_intent', address=300032, length=4))
    injected = bytes(((300032+i)*13+91) & 255 for i in range(4))
    _record(emit, 'independent_download', injected, gpu.read_bytes(300032, 4))
    status = _trace_idle(gpu, 2)
    emit(dict(test_id=1, stage='complete', status=status, psram_tested=False,
              uart_required_frames=2, release_ready=False))

def run_one(gpu, emit, confirm_frame):
    # confirm_frame must durably save/decode/compare the requested UART frame,
    # and raise on absence, timeout, CRC error, metadata or payload mismatch.
    # A remote RP2040 runner uses run_write/run_read as two separate RAM calls.
    run_write(gpu, emit)
    confirm_frame(1)
    run_read(gpu, emit)
    confirm_frame(2)
