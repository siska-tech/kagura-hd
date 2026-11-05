# SPDX-License-Identifier: Apache-2.0
"""Bounded telemetry; logs stream to the caller, not an unbounded RP2040 list."""
import time
import gc

def collect():
    # CPython render/test timings must not include needless full-heap scans.
    if hasattr(gc,'mem_free'):gc.collect()

def heap_stats():
    return (gc.mem_alloc(),gc.mem_free()) if hasattr(gc,'mem_free') else (None,None)

def now_us():
    return time.ticks_us() if hasattr(time, 'ticks_us') else int(time.monotonic()*1000000)

def diff_us(a, b):
    return time.ticks_diff(a, b) if hasattr(time, 'ticks_diff') else a-b

def sleep_us(n):
    if n > 0:
        if hasattr(time, 'sleep_us'): time.sleep_us(n)
        else: time.sleep(n/1000000)

class Diagnostics:
    def __init__(self, sink=None, clock=now_us):
        self.sink, self.clock = sink, clock
        self.commands = [0]*8
        self.calls = {}
        self.bytes_written = 0
        self.faulted = False

    def event(self, kind, **fields):
        fields['event'] = kind
        if self.sink: self.sink(fields)

    def measure(self, name, function, *args):
        before = self.clock()
        try: return function(*args)
        finally:
            elapsed = max(0, diff_us(self.clock(), before))
            stats = self.calls.get(name)
            if stats is None: stats = self.calls[name] = [0, 0, 0]
            stats[0] += 1; stats[1] += elapsed; stats[2] = max(stats[2], elapsed)

class CountedTransport:
    def __init__(self, transport, diagnostics):
        self.inner, self.diag, self.opcode = transport, diagnostics, 0

    def read(self, *args): return self.inner.read(*args)

    def write(self, address, increment, data):
        if address == 8 and increment and data: self.opcode = data[0]
        # Count attempts before transfer: an uncertain submission is never replayed.
        if address == 26 and data and data[0] == 1 and self.opcode < 8:
            self.diag.commands[self.opcode] += 1
        return self.inner.write(address, increment, data)
