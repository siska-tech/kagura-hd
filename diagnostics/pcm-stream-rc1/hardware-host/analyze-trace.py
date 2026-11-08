"""Correlate Host trace and decoded HDMI audio without claiming wire timing."""
import argparse
import json
from pathlib import Path
import re
import wave

import numpy as np


def rows(lines, prefix):
    return [dict((key, int(value)) for key, value in re.findall(r"(\w+)=(\d+)", line))
            for line in lines if line.startswith(prefix + " ")]


def analyze(log, wav):
    lines = log.read_text(errors="replace").splitlines()
    opcodes = rows(lines, "OP")
    refills = rows(lines, "REFILL")
    statuses = rows(lines, "AUDIO")
    if not (refills and statuses and rows(lines, "TRACE_END")):
        raise ValueError("Incomplete Host trace")
    with wave.open(str(wav)) as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (48000, 2, 2):
            raise ValueError("Expected 48 kHz stereo PCM16 WAV")
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").reshape(-1, 2)
    onset = int(np.flatnonzero(abs(audio[:, 0].astype(np.int32)) > 1000)[0])
    stop = min(onset + 25 * 48000, len(audio))
    segment = audio[onset:stop].astype(float)
    rms = np.sqrt(np.mean(segment[:len(segment)//480*480].reshape(-1, 480, 2)**2, axis=1))
    # Exclude the startup and stop edges. Capture onset is an approximate
    # epoch for the Host trace, so event correlations use a +/-15 ms window.
    low = (rms < 20)
    low[:2] = low[-5:] = False
    bins = np.flatnonzero(low.any(axis=1))
    groups = np.split(bins, np.flatnonzero(np.diff(bins) > 1) + 1)
    names = ("fill", "copy", "palette", "present")
    events = []
    for group in groups:
        if not len(group):
            continue
        start = int(group[0]) * 10000
        end = (int(group[-1]) + 1) * 10000
        nearby = [op for op in opcodes if start-15000 <= op["t_us"] < end+15000]
        in_flight = [item["token"] for item in refills
                     if item["t_us"] < end+15000 and item["done_us"] >= start-15000]
        events.append(dict(start_ms=start/1000, duration_ms=(end-start)/1000,
                           nearby_opcode_counts={name: sum(op[name] for op in nearby) for name in names},
                           nearby_refill_tokens=in_flight))
    return dict(
        onset_sample=onset, opcode_counts={name: sum(op[name] for op in opcodes) for name in names},
        opcode_max_us={name: max((op[name+"_max"] for op in opcodes), default=0) for name in names},
        refill_count=len(refills),
        refill_max_us=max(r["done_us"]-r["t_us"] for r in refills),
        max_refill_publication_gap_us=max(b["done_us"]-a["done_us"] for a, b in zip(refills, refills[1:])),
        token_sequence_errors=sum(b["token"] != (a["token"]+1) % 256 for a, b in zip(refills, refills[1:])),
        status_samples=len(statuses), psram_read_pending_samples=sum(bool(s["stream"]&4) for s in statuses),
        unarmed_samples=sum(not s["stream"]&2 for s in statuses),
        inactive_channel_samples=sum((s["left"]&s["right"]&2) == 0 for s in statuses),
        pcm_fault_samples=sum(bool((s["left"]|s["right"])&0x38) for s in statuses),
        hdmi_fifo_fault_samples=sum(bool(s["hdmi"]&6) for s in statuses),
        hdmi_muted_samples=sum(bool(s["hdmi"]&8) for s in statuses),
        low_rms_10ms_by_channel=np.sum(low, axis=0).tolist(), low_rms_events=events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("wav", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.log, args.wav), indent=2))
