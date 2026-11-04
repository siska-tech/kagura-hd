#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Executable COPY_RECT design model, not an implementation or RTL benchmark.

Models a proposed same-word-phase, even-pixel copy using the existing 64-byte
upload window. Checks against a pixel snapshot oracle, including overlap.
Run with --output build/fb-blit-analysis.json to save reproducible estimates.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random

WIDTH, HEIGHT, STRIDE = 640, 360, 320
PAGE_BYTES = STRIDE * HEIGHT
SYS_HZ = 54_000_000


@dataclass(frozen=True)
class Rect:
    src_page: int
    dst_page: int
    sx: int
    sy: int
    dx: int
    dy: int
    width: int
    height: int


@dataclass(frozen=True)
class Piece:
    src: int  # aligned byte address
    dst: int
    words: int
    mask: int  # 1 inhibits a byte; same lane map for source and destination


def validate(r):
    if r.src_page not in (0, 1) or r.dst_page not in (0, 1):
        raise ValueError("page")
    if min(r.sx, r.sy, r.dx, r.dy, r.width, r.height) < 0:
        raise ValueError("negative")
    if (r.sx >= WIDTH or r.dx >= WIDTH or r.sy >= HEIGHT or r.dy >= HEIGHT
            or max(r.sx, r.dx) + r.width > WIDTH
            or max(r.sy, r.dy) + r.height > HEIGHT):
        raise ValueError("bounds")
    if (r.sx | r.dx | r.width) & 1:
        raise ValueError("odd pixel alignment")
    if (r.sx ^ r.dx) & 7:
        raise ValueError("different word phase")


def pieces(r):
    """Each piece reads completely into the window before its masked write.

    No arbitration lock is required between those two transactions. Coordinates
    and sizes are validated before ANY transaction, including empty rectangles.
    """
    validate(r)
    if not r.width or not r.height:
        return
    if r.src_page == r.dst_page and (r.sx, r.sy) == (r.dx, r.dy):
        return
    same_page = r.src_page == r.dst_page
    down = same_page and r.dy > r.sy
    right = same_page and r.dy == r.sy and r.dx > r.sx
    rows = range(r.height - 1, -1, -1) if down else range(r.height)
    for row in rows:
        src = r.src_page * PAGE_BYTES + (r.sy + row) * STRIDE + r.sx // 2
        dst = r.dst_page * PAGE_BYTES + (r.dy + row) * STRIDE + r.dx // 2
        remaining = r.width // 2
        cursor = remaining if right else 0
        while remaining:
            if right:
                # End at the current right edge; at most 16 aligned words.
                length = min(remaining, 61 + ((dst + cursor - 1) & 3))
                cursor -= length
            else:
                length = min(remaining, 64 - ((dst + cursor) & 3))
            first = (dst + cursor) & 3
            words = (first + length + 3) // 4
            enabled = ((1 << length) - 1) << first
            yield Piece((src + cursor) & ~3, (dst + cursor) & ~3,
                        words, ((1 << 64) - 1) ^ enabled)
            if not right:
                cursor += length
            remaining -= length


def apply(memory, r):
    for p in pieces(r):
        size = 4 * p.words
        assert 1 <= p.words <= 16
        assert p.src % 4 == p.dst % 4 == 0
        assert p.src // PAGE_BYTES == (p.src + size - 1) // PAGE_BYTES == r.src_page
        assert p.dst // PAGE_BYTES == (p.dst + size - 1) // PAGE_BYTES == r.dst_page
        # Snapshot includes masked lanes, which must never be written.
        upload_window = bytes(memory[p.src:p.src + size])
        for lane, value in enumerate(upload_window):
            if not (p.mask >> lane) & 1:
                memory[p.dst + lane] = value


def pixel(memory, page, x, y):
    value = memory[page * PAGE_BYTES + y * STRIDE + x // 2]
    return (value >> 4) if x % 2 == 0 else (value & 15)


def oracle(before, r):
    # Pixel-at-a-time immutable source is independent of chunk/direction/masks.
    after = bytearray(before)
    for y in range(r.height):
        for x in range(r.width):
            value = pixel(before, r.src_page, r.sx + x, r.sy + y)
            dx, dy = r.dx + x, r.dy + y
            addr = r.dst_page * PAGE_BYTES + dy * STRIDE + dx // 2
            if dx % 2:
                after[addr] = (after[addr] & 0xF0) | value
            else:
                after[addr] = (after[addr] & 0x0F) | (value << 4)
    return after


def verify(seed=9):
    rng = random.Random(seed)
    memory = rng.randbytes(2 * PAGE_BYTES)
    cases = []
    # All byte phases, forward/backward chunk edges, one-byte and full rows.
    for phase in range(4):
        for width in (2, 6, 8, 118, 120, 122, 124, 126, 128, 130, 256, 512):
            for dx, dy in ((phase * 2 + 8, 10), (phase * 2, 11),
                           (phase * 2, 9), (phase * 2 + 8, 11)):
                cases.append(Rect(0, 0, phase * 2, 10, dx, dy, width, 7))
                cases.append(Rect(0, 0, dx, dy, phase * 2, 10, width, 7))
    for _ in range(500):
        width = 2 * rng.randint(0, 320)
        height = rng.randint(0, 40)
        phase = rng.randrange(4)
        xs = list(range(phase * 2, WIDTH - max(width, 1) + 1, 8))
        if not xs:
            continue
        cases.append(Rect(rng.randrange(2), rng.randrange(2),
                          rng.choice(xs), rng.randrange(HEIGHT - max(height, 1) + 1),
                          rng.choice(xs), rng.randrange(HEIGHT - max(height, 1) + 1),
                          width, height))
    cases += [Rect(0, 1, 0, 0, 0, 0, 640, 360),
              Rect(0, 0, 0, 16, 0, 0, 640, 344),
              Rect(0, 0, 0, 0, 0, 16, 640, 344),
              Rect(1, 1, 638, 359, 638, 359, 2, 1),
              Rect(0, 1, 638, 359, 638, 359, 0, 0)]
    for r in cases:
        actual = bytearray(memory)
        apply(actual, r)
        assert actual == oracle(memory, r), r
    bad = [Rect(0, 0, 1, 0, 1, 0, 2, 1),
           Rect(0, 0, 0, 0, 2, 0, 2, 1),
           Rect(0, 0, 0, 0, 0, 0, 3, 1),
           Rect(0, 0, 638, 0, 638, 0, 4, 1),
           Rect(0, 0, 0, 359, 0, 0, 2, 2),
           Rect(2, 0, 0, 0, 0, 0, 2, 1),
           Rect(0, 0, 640, 0, 0, 0, 0, 1),
           Rect(0, 0, -8, 0, 0, 0, 8, 1)]
    for r in bad:
        try:
            next(pieces(r), None)
        except ValueError:
            continue
        raise AssertionError(("accepted invalid", r))
    return {"seed": seed, "pixel_oracle_cases": len(cases),
            "rejected_cases": len(bad)}


def estimate(r):
    work = list(pieces(r))
    words = sum(p.words for p in work)
    # LAT14, RDL6, CS-high2, plus CHECK and IDLE/ISSUE/response handoff.
    # Saturated arbiter start-to-start: write=21+2N, read=27+2N.
    # Does NOT include GPU FSM bubbles, scanout/PCM grants or SDK/transport.
    cycles = sum(48 + 4 * p.words for p in work)
    return {"pieces": len(work), "read_transactions": len(work),
            "write_transactions": len(work), "read_bus_bytes": words * 4,
            "write_bus_bytes": words * 4,
            "masked_write_bytes": words * 4 - sum(
                sum(not ((p.mask >> i) & 1) for i in range(4 * p.words)) for p in work),
            "transaction_service_cycles": cycles,
            "service_ms_without_gpu_bubbles_or_competition": round(cycles / SYS_HZ * 1000, 6)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scroll = estimate(Rect(0, 0, 0, 16, 0, 0, 640, 344))
    fill_cycles = 16 * 5 * (21 + 32)  # 16 cleared rows, five full writes each
    scanout_cycles = 360 * 60 * 5 * (27 + 32)
    pcm_cycles = 96_000 * (27 + 2)  # two 48 kHz byte streams, all cache misses
    report = {
        "scope": "Proposed aligned BLIT model; not implemented RTL or measured performance",
        "verification": verify(),
        "full_page_copy": estimate(Rect(0, 1, 0, 0, 0, 0, 640, 360)),
        "scroll_16_rows_copy_only": scroll,
        "window_200x100_move_8px": estimate(Rect(0, 0, 0, 0, 8, 0, 200, 100)),
        "window_200x100_phase_3": estimate(Rect(0, 1, 6, 0, 6, 0, 200, 100)),
        "bandwidth_60_scrolls_per_second": {
            "scanout_service_cycles_per_second": scanout_cycles,
            "pcm_all_miss_service_cycles_per_second": pcm_cycles,
            "copy_and_clear_service_cycles_per_operation": scroll["transaction_service_cycles"] + fill_cycles,
            "one_page_total_service_percent": round(100 * (scanout_cycles + pcm_cycles + 60 * (scroll["transaction_service_cycles"] + fill_cycles)) / SYS_HZ, 3),
            "two_page_replay_total_service_percent": round(100 * (scanout_cycles + pcm_cycles + 120 * (scroll["transaction_service_cycles"] + fill_cycles)) / SYS_HZ, 3),
        },
    }
    result = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
