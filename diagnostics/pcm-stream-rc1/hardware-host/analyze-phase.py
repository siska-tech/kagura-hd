"""Measure common HDMI capture drift against the known streaming markers."""
import argparse
import json
from pathlib import Path
import wave

import numpy as np


def analyze(path, halves, marker_cycle=64):
    with wave.open(str(path)) as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (48000, 2, 2):
            raise ValueError("Expected 48 kHz stereo PCM16 WAV")
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").reshape(-1, 2)
    starts = [int(np.flatnonzero(abs(audio[:, ch].astype(np.int32)) > 1000)[0]) for ch in (0, 1)]
    positions = np.arange(halves) * 4096
    if max(starts) + positions[-1] + 1024 > len(audio):
        raise ValueError("Capture shorter than requested marker count")
    summaries = []
    phases = []
    for ch, period in enumerate((64, 32)):
        offsets = np.arange(512, 1024)
        window = np.sign(audio[starts[ch] + positions[:, None] + offsets, ch])
        scores = np.stack([
            np.mean(window == np.where((offsets + shift) % period < period // 2, 1, -1), axis=1)
            for shift in range(period)
        ], axis=1)
        phase = np.rint(np.unwrap(scores.argmax(axis=1) * (2 * np.pi / period))
                        * (period / (2 * np.pi))).astype(int)
        # The capture onset can lead the first full sample by a sample or two.
        # Use the signed phase nearest that onset, e.g. 31 means -1 at period 32.
        if phase[0] > period // 2:
            phase -= period
        phases.append(phase)
        marker_start = starts[ch] + positions - phase
        marker_samples = audio[marker_start[:, None] + np.arange(10, 54), ch].astype(np.int32)
        gain = np.median(abs(audio[marker_start[:, None] + np.arange(200, 300), ch].astype(np.int32))) / 72
        actual = np.rint(np.median(abs(marker_samples), axis=1) / gain)
        expected = 24 + (np.arange(halves) % marker_cycle + 37 * ch) % 64
        drift = np.polyfit(positions, phase, 1)[0] * 1e6
        summaries.append(dict(channel=ch, marker_mismatches=int(np.count_nonzero(actual != expected)),
                              phase_start=int(phase[0]), phase_end=int(phase[-1]),
                              drift_samples_per_million=float(drift),
                              max_phase_step=int(np.max(abs(np.diff(phase)), initial=0))))
    start = max(starts) + 960
    end = min(starts) + int(positions[-1] - max(phase[-1] for phase in phases)) - 960
    segment = audio[start:end].astype(float)
    rms = np.sqrt(np.mean(segment[:len(segment)//480*480].reshape(-1, 480, 2)**2, axis=1))
    return dict(halves=halves, channel_starts=starts, channels=summaries,
                channel_phase_disagreement=int(np.count_nonzero(phases[0] != phases[1])),
                low_rms_10ms_by_channel=np.sum(rms < 20, axis=0).tolist())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("halves", type=int)
    parser.add_argument("--marker-cycle", type=int, choices=(2, 64), default=64)
    args = parser.parse_args()
    if args.halves < 2:
        parser.error("at least two full markers required")
    print(json.dumps(analyze(args.wav, args.halves, args.marker_cycle), indent=2))
