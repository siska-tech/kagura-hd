# SPDX-License-Identifier: Apache-2.0
"""MIDNIGHT TERMINAL instrument definitions; edit operators in Python."""
from kagura_fm import Patch, operator, effects, phase_increment


def dsp_parameters():
    decay=lambda ms:65536//(3*ms)
    return effects(kick_base_inc=phase_increment(44),kick_soft_inc=phase_increment(70),
        kick_hard_inc=phase_increment(120),kick_soft_decay=decay(190),kick_hard_decay=decay(260),
        kick_soft_sweep_decay=decay(45),kick_hard_sweep_decay=decay(30),kick_soft_gain=11,kick_hard_gain=15,
        brush_decay=decay(170),brush_swell=9000,brush_filter_shift=2,brush_left=200,brush_right=150,brush_send=32,
        ride_decay=decay(85),ride_inc=phase_increment(5400),ride_left=120,ride_right=200,
        rim_decay=decay(14),rim_inc=phase_increment(1700),rim_left=160,rim_right=220,
        noise_glide_shift=7,noise_filter_shift=3,noise_dc_shift=6,noise_left=256,noise_right=192,
        noise_drop_mask=63,noise_drop_min=40,noise_drop_range_mask=31,noise_drop_decay=2,delay_frames=12000)
INSTRUMENTS = ('ep', 'bass', 'vib', 'blip', 'chime', 'sting', 'siren', 'drone')

def presets():
    return (
        Patch((
            operator(ratio=1.0, detune=2, level=15500, attack_ms=1, decay_ms=1700, sustain=0.25, release_ms=320),
            operator(ratio=1.0, detune=0, level=8000, attack_ms=0, decay_ms=500, sustain=0.12, release_ms=320),
            operator(ratio=1.0, detune=-2, level=5200, attack_ms=0, decay_ms=420, sustain=0.0, release_ms=320),
            operator(ratio=14.0, detune=0, level=5600, attack_ms=0, decay_ms=55, sustain=0.0, release_ms=320),
        ), feedback=0, vibrato=22, vibrato_shift=8, send=45, vibrato_hz10=48),
        Patch((
            operator(ratio=1.0, detune=0, level=22500, attack_ms=3, decay_ms=650, sustain=0.35, release_ms=90),
            operator(ratio=1.0, detune=0, level=15000, attack_ms=0, decay_ms=130, sustain=0.18, release_ms=90),
            operator(ratio=1.0, detune=0, level=6000, attack_ms=0, decay_ms=180, sustain=0.0, release_ms=90),
            operator(ratio=3.0, detune=0, level=5000, attack_ms=0, decay_ms=35, sustain=0.0, release_ms=90),
        ), feedback=0, vibrato=0, vibrato_shift=8, send=0, vibrato_hz10=0),
        Patch((
            operator(ratio=1.0, detune=0, level=15500, attack_ms=0, decay_ms=2300, sustain=0.0, release_ms=700),
            operator(ratio=4.0, detune=0, level=11500, attack_ms=0, decay_ms=320, sustain=0.0, release_ms=700),
            operator(ratio=3.0, detune=0, level=3600, attack_ms=0, decay_ms=600, sustain=0.0, release_ms=700),
            operator(ratio=10.0, detune=0, level=3800, attack_ms=0, decay_ms=80, sustain=0.0, release_ms=700),
        ), feedback=0, vibrato=70, vibrato_shift=8, send=120, vibrato_hz10=55),
        Patch((
            operator(ratio=1.0, detune=0, level=7000, attack_ms=0, decay_ms=40, sustain=0.0, release_ms=30),
            operator(ratio=2.0, detune=0, level=8000, attack_ms=0, decay_ms=25, sustain=0.0, release_ms=30),
            operator(ratio=1.0, detune=0, level=0, attack_ms=0, decay_ms=10, sustain=0.0, release_ms=10),
            operator(ratio=1.0, detune=0, level=0, attack_ms=0, decay_ms=10, sustain=0.0, release_ms=10),
        ), feedback=0, vibrato=0, vibrato_shift=8, send=30, vibrato_hz10=0),
        Patch((
            operator(ratio=1.0, detune=0, level=12000, attack_ms=0, decay_ms=900, sustain=0.0, release_ms=500),
            operator(ratio=3.5, detune=0, level=15000, attack_ms=0, decay_ms=400, sustain=0.0, release_ms=500),
            operator(ratio=2.0, detune=0, level=5000, attack_ms=0, decay_ms=600, sustain=0.0, release_ms=500),
            operator(ratio=7.0, detune=0, level=6000, attack_ms=0, decay_ms=150, sustain=0.0, release_ms=500),
        ), feedback=0, vibrato=0, vibrato_shift=8, send=110, vibrato_hz10=0),
        Patch((
            operator(ratio=1.0, detune=9, level=14000, attack_ms=0, decay_ms=500, sustain=0.0, release_ms=200),
            operator(ratio=1.01, detune=0, level=20000, attack_ms=0, decay_ms=400, sustain=0.0, release_ms=200),
            operator(ratio=0.5, detune=-9, level=12000, attack_ms=0, decay_ms=600, sustain=0.0, release_ms=200),
            operator(ratio=1.41, detune=0, level=18000, attack_ms=0, decay_ms=300, sustain=0.0, release_ms=200),
        ), feedback=6, vibrato=0, vibrato_shift=8, send=60, vibrato_hz10=0),
        Patch((
            operator(ratio=1.0, detune=0, level=10500, attack_ms=30, decay_ms=4000, sustain=0.9, release_ms=200),
            operator(ratio=1.0, detune=0, level=14000, attack_ms=30, decay_ms=4000, sustain=0.8, release_ms=200),
            operator(ratio=1.5, detune=7, level=6000, attack_ms=30, decay_ms=4000, sustain=0.9, release_ms=200),
            operator(ratio=2.0, detune=0, level=9000, attack_ms=30, decay_ms=4000, sustain=0.8, release_ms=200),
        ), feedback=5, vibrato=255, vibrato_shift=3, send=40, vibrato_hz10=25),
        Patch((
            operator(ratio=1.0, detune=0, level=15000, attack_ms=500, decay_ms=4000, sustain=1.0, release_ms=1500),
            operator(ratio=2.0, detune=0, level=2500, attack_ms=800, decay_ms=4000, sustain=0.8, release_ms=1500),
            operator(ratio=1.5, detune=3, level=3500, attack_ms=900, decay_ms=4000, sustain=0.9, release_ms=1500),
            operator(ratio=3.0, detune=0, level=1500, attack_ms=900, decay_ms=4000, sustain=0.7, release_ms=1500),
        ), feedback=0, vibrato=30, vibrato_shift=8, send=30, vibrato_hz10=3),
    )
