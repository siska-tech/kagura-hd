#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure a running HDMI REPL without Ctrl-C, firmware changes or file writes.

Requires pyserial. Keep keyboard idle while running. The screen is changed.
"""
import argparse
import json
from pathlib import Path
import time
import serial
from serial.tools import list_ports

class RawRepl:
    def __init__(self, port): self.port_name = port
    def until(self, marker, timeout):
        data = bytearray(); deadline = time.monotonic() + timeout
        while not data.endswith(marker):
            if time.monotonic() >= deadline: raise TimeoutError(bytes(data[-500:]))
            data.extend(self.port.read(1))
        return bytes(data)
    def __enter__(self):
        self.port = serial.Serial(self.port_name, 115200, timeout=.1, write_timeout=5)
        try:
            self.port.read(self.port.in_waiting)
            self.port.write(b'\x02\x01')
            def banner_until(timeout):
                data = bytearray()
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    data.extend(self.port.read(max(1, self.port.in_waiting)))
                    if b'raw REPL' in data and data.endswith(b'>'): break
                return bytes(data)
            banner = banner_until(2)
            if b'raw REPL' not in banner:
                self.port.write(b'\x05\x15\x01')  # end, kill line, raw REPL
                banner = banner_until(10)
            if b'raw REPL' not in banner: raise RuntimeError(banner)
            return self
        except BaseException:
            self.port.close()
            raise
    def run(self, source, timeout=180):
        data = source.encode()
        for offset in range(0, len(data), 128):
            self.port.write(data[offset:offset + 128]); time.sleep(.002)
        self.port.write(b'\x04')
        if self.port.read(2) != b'OK': raise RuntimeError('raw REPL rejected program')
        stdout = self.until(b'\x04', timeout)[:-1].decode()
        stderr = self.until(b'\x04', 10)[:-1].decode()
        self.until(b'>', 10)
        if stderr: raise RuntimeError(stdout + stderr)
        return stdout
    def __exit__(self, *exc):
        try:
            self.port.write(b'\x02')
        finally:
            self.port.close()

PROGRAM = '''import kagura_console,time,gc,json
c=kagura_console.console
assert c is not None and c.last_error is None
while c.atlas is not None and not c.atlas.ready:time.sleep_ms(20)
c.pause()
data=b'REPL display benchmark: ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 Python help text.\\r\\n'*8
samples=[]
before=c.dropped
try:
 for trial in range(REPEATS):
  c.screen.x=0
  c.screen.y=c.screen.rows-1
  c.paused=False
  started=time.ticks_ms()
  c.write(data)
  while c._head!=c._tail or c._updating:
   if c.last_error is not None:raise c.last_error
   if time.ticks_diff(time.ticks_ms(),started)>90000:raise OSError('display timeout')
   time.sleep_ms(5)
  samples.append(time.ticks_diff(time.ticks_ms(),started))
  c.paused=True
 for line in range(STRESS):
  c.paused=False
  c.write(('stress %03d: ABC xyz 012 日本語\\r\\n'%line).encode())
  started=time.ticks_ms()
  while c._head!=c._tail or c._updating:
   if c.last_error is not None:raise c.last_error
   if time.ticks_diff(time.ticks_ms(),started)>90000:raise OSError('stress timeout')
   time.sleep_ms(5)
  c.paused=True
 gc.collect()
 print('RESULT',json.dumps({'bytes':len(data),'samples_ms':samples,'stress_lines':STRESS,
  'dropped':c.dropped-before,'error':repr(c.last_error),'heap_free':gc.mem_free(),
  'native':getattr(c.device,'accelerated',False),'keyboard':c.keyboard.connected if c.keyboard else None}))
finally:
 c.paused=False
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port')
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--stress-lines',type=int,default=128)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1 <= args.repeat <= 10 or not 0 <= args.stress_lines <= 10000:
        parser.error('repeat must be 1..10; stress-lines must be 0..10000')
    port=args.port
    if port is None:
        ports=[p.device for p in list_ports.comports() if p.vid==0x2e8a and p.pid==5]
        if len(ports)!=1:parser.error('specify --port when there is not exactly one MicroPython Pico')
        port=ports[0]
    with RawRepl(port) as repl:
        source=PROGRAM.replace('REPEATS',str(args.repeat)).replace('STRESS',str(args.stress_lines))
        text=repl.run(source,timeout=max(180,args.stress_lines*3+args.repeat*90))
    print(text,end='')
    result=json.loads(next(line[7:] for line in text.splitlines() if line.startswith('RESULT ')))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if result['dropped'] or result['error']!='None':raise SystemExit('display failed')

if __name__=='__main__':main()
