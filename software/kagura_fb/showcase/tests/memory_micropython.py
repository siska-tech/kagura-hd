# SPDX-License-Identifier: Apache-2.0
"""Run with MicroPython Unix -X heapsize=192K. NO board or PSRAM model.
The storage-free sink is ONLY a runtime/heap smoke fixture, not a GPU oracle.
"""
import gc
from kagura_fb import Device
from kagura_fb_audio import Audio
from showcase.gpu_api_adapter import GPU
from showcase.diagnostics import Diagnostics
from showcase.scene_manager import Demo

class SinkTransport:
    def __init__(self):
        self.command=bytearray(16);self.audio=bytearray(256);self.index=0
        self.pcm=[0,0];self.completed=False;self.tag=0;self.bank=0;self.control=0;self.generation=0;self.clock=0
    def now(self):self.clock+=1;return self.clock
    def read(self,address,increment,length):
        out=bytearray(length)
        for i in range(length):
            if address<7:v=b'KFB1\x01\x04\xff'[address]
            elif address==27:v=2|(16 if self.completed else 0)
            elif address==28:v=self.tag&255
            elif address==29:v=self.tag>>8
            elif address==50:v=(self.bank<<1)|(self.control&1)<<2|0x30
            elif address==51:v=self.generation&255
            elif address==52:v=self.generation>>8
            elif address==55:
                v=self.pcm[(self.index-0x6f)//32] if self.index in (0x6f,0x8f) else self.audio[self.index]
            else:v=0
            out[i]=v
            if increment:address=(address+1)&63
        return out
    def write(self,address,increment,data):
        for v in data:
            if 8<=address<24:self.command[address-8]=v
            elif address==26:
                self.tag=self.command[2]|self.command[3]<<8;self.completed=True
                if self.command[0]==7:
                    for c in (0,1):
                        self.pcm[c]=(self.pcm[c]|2) if self.audio[0x6e+c*32]&1 else (self.pcm[c]&~2)
            elif address==31:self.completed=False
            elif address==32:self.control=v
            elif address==49:self.bank=self.control>>1;self.generation=(self.generation+1)&65535
            elif address==54:self.index=v
            elif address==55:
                if self.index in (0x6f,0x8f):
                    c=(self.index-0x6f)//32
                    if v==1:self.pcm[c]=1
                    elif v==2:self.pcm[c]=0
                    elif v==4:self.pcm[c]&=3
                else:self.audio[self.index]=v
            if increment:address=(address+1)&63

clock=[0];maximum=[0];minimum_free=[1<<30];ends=[0]
def now():return clock[0]
def sleep(n):clock[0]+=n
def events(record):
    maximum[0]=max(maximum[0],gc.mem_alloc());minimum_free[0]=min(minimum_free[0],gc.mem_free())
    if record['event']=='scene_end':
        ends[0]+=1;gc.collect()
gc.collect();before=gc.mem_alloc()
transport=SinkTransport();device=Device(transport,now_ms=transport.now)
gpu=GPU(device,Audio(device),Diagnostics(events,now),verify=False)
demo=Demo(gpu);demo.run(2,sleep=sleep)
gc.collect();after=gc.mem_alloc()
assert ends[0]==12 and not demo.halted
assert len(gpu.row)==320 and len(transport.audio)==256
print('PASS: MicroPython Unix bounded heap, 12 scenes / 2 loops; storage-free sink, not RTL/FB validation')
print('heap_before=%d heap_after=%d sampled_max_alloc=%d sampled_min_free=%d native_RP2040_measured=false'%(before,after,maximum[0],minimum_free[0]))
print('gc_heap_total=%d'%(gc.mem_alloc()+gc.mem_free()))
