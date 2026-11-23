# SPDX-License-Identifier: Apache-2.0
"""Configurable 4-operator FM patches and timestamped commands, no built-in song."""
import struct
from kagura_gpu import Device

NOTE, OFF, GAIN, DRUM, NOISE, PITCH, MASTER, CRUSH, STUTTER, PITCH_RAMP, MASTER_RAMP, ALL_OFF, DELAY = range(13)
RATE = 48000
EFFECT_FIELDS = ('kick_base_inc','kick_soft_inc','kick_hard_inc','kick_soft_decay','kick_hard_decay',
    'kick_soft_sweep_decay','kick_hard_sweep_decay','kick_soft_gain','kick_hard_gain',
    'brush_decay','brush_swell','brush_filter_shift','brush_left','brush_right','brush_send',
    'ride_decay','ride_inc','ride_left','ride_right','rim_decay','rim_inc','rim_left','rim_right',
    'noise_glide_shift','noise_filter_shift','noise_dc_shift','noise_left','noise_right',
    'noise_drop_mask','noise_drop_min','noise_drop_range_mask','noise_drop_decay','delay_frames')


def effects(**parameters):
    """Pack configurable percussion/noise/delay DSP parameters; no sound presets."""
    values=[0]*33
    values[32]=12000
    for name,value in parameters.items():
        values[EFFECT_FIELDS.index(name)]=value
    return struct.pack('<33I',*values)


def phase_increment(hz):
    return (((hz<<32)//RATE) if isinstance(hz,int) else int(hz*4294967296/RATE))&0xffffffff


def operator(ratio=1, detune=0, level=0, attack_ms=0, decay_ms=500, sustain=0, release_ms=200):
    def coefficient(ms, numerator):
        if ms < 0:
            raise ValueError('negative envelope time')
        return min(65535, max(1, numerator//(3*ms))) if ms else 65535
    values = (int(ratio*256), detune, level, coefficient(attack_ms, 65535),
              coefficient(decay_ms, 65536), int(sustain*65535), coefficient(release_ms, 65536))
    if (not 0 <= values[0] <= 65535 or not -128 <= detune <= 127 or
            any(not 0 <= x <= 65535 for x in values[2:])):
        raise ValueError('operator parameter outside packed range')
    return values


class Patch:
    def __init__(self, operators, algorithm=1, feedback=0, vibrato=0, vibrato_shift=8, send=0, vibrato_hz10=0):
        if len(operators) != 4:
            raise ValueError('a patch has four operators')
        self.operators = tuple(operators)
        self.header = (algorithm, feedback, vibrato, vibrato_shift, send, vibrato_hz10)

    def pack(self):
        alg, fb, vib, shift, send, hz = self.header
        if alg not in (0, 1) or not 0 <= fb <= 16 or not 3 <= shift <= 24 or not 0 <= hz <= 2000:
            raise ValueError('invalid FM patch header')
        return struct.pack('<BBBBBH', *self.header)+b''.join(struct.pack('<HbHHHHH', *op) for op in self.operators)


class Schedule:
    """Sorted, compact sample-frame commands. No Python object list is retained."""
    def __init__(self):
        self._parts = []
        self._current = bytearray(1024)
        self._used = self._size = 0
        self.last_frame = 0

    def add(self, frame, op, channel=0, a=0, b=0, value=0, duration=0):
        if not self.last_frame <= frame <= 0xffffffff or self._size >= 131072:
            raise ValueError('unsorted, oversized or out-of-range schedule')
        struct.pack_into('<IBBBBII', self._current, self._used, frame, op, channel, a, b, value, duration)
        self._used += 16
        self._size += 16
        if self._used == 1024:
            self._parts.append(bytes(self._current))
            self._used = 0
        self.last_frame = frame
        return self

    def pages(self):
        return tuple(self._parts)+((bytes(memoryview(self._current)[:self._used]),) if self._used else ())

    @property
    def data(self):
        # Contiguous export for host tools; playback uses pages() instead.
        return b''.join(self.pages())

    def at_ms(self, ms, *args, **kwargs):
        return self.add(ms*48, *args, **kwargs)


class Synth(Device):
    def __init__(self, patches, schedule=b'', backend=None, autostart=True, dsp=None):
        super().__init__(backend)
        self.patches = patches if isinstance(patches, (bytes, bytearray)) else b''.join(p.pack() for p in patches)
        if not self.patches or len(self.patches)%59 or len(self.patches)>16*59:
            raise ValueError('one to sixteen packed FM patches required')
        self._schedule = schedule.pages() if isinstance(schedule, Schedule) else schedule
        self._autostart, self._started = autostart, False
        self._dsp=effects() if dsp is None else dsp

    def _open_backend(self):
        self.backend.open(self.patches, self._schedule, self._dsp)

    def __enter__(self):
        super().__enter__()
        try:
            if self._autostart:
                self.start()
            return self
        except BaseException:
            try:
                self.close()
            except Exception as error:
                self.cleanup_error = error
            raise

    def close(self):
        self._started = False
        super().close()

    def start(self):
        self._require_open()
        if self._started:
            raise RuntimeError('audio already started')
        self.backend.start()
        self._started = True

    def note_on(self, note, voice=0, instrument=0, velocity=200, gate_ms=0):
        self._require_open()
        if not 0 <= instrument < len(self.patches)//59:
            raise ValueError('instrument outside supplied patches')
        self.backend.note_on(voice, instrument, note, velocity, gate_ms)

    def note_off(self, voice=0): self._require_open(); self.backend.note_off(voice)
    def all_off(self): self._require_open(); self.backend.all_off()

    def command(self, op, channel=0, a=0, b=0, value=0, duration=0):
        self._require_open()
        self.backend.command(op, channel, a, b, value, duration)

    def sleep_ms(self, ms):
        self._require_open()
        if not self._started:
            raise RuntimeError('start audio before waiting')
        if not isinstance(ms, int) or not 0 <= ms <= 60000:
            raise ValueError('wait must be 0..60000 ms')
        self.backend.wait_until(self.backend.elapsed_us()+ms*1000)

    def stats(self):
        return dict(zip(('halves', 'worst_latency_us', 'fm_peak', 'fm_clipped'), self.backend.stats()))
