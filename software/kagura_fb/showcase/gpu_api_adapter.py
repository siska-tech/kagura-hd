# SPDX-License-Identifier: Apache-2.0
"""Use the existing Device/Audio APIs; no invented GPU text or FIFO CSR."""
from .diagnostics import Diagnostics, CountedTransport, collect
from .vendor.fonts import BitmapFont8
from .vendor.ascii_rows import ROWS
try: import binascii
except ImportError: import ubinascii as binascii

PALETTE = (0x112,0x223,0x334,0x556,0x9ab,0xdef,0xfff,0x04a,
           0x08c,0x0df,0x087,0x4eb,0x743,0xf85,0xfe9,0xa5e)
BITSTREAM_SHA256 = '642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7'

class _Rows:
    def glyph(self, code):
        i = (code-32 if 32 <= code <= 126 else 31)*8
        return ROWS[i:i+8]

class GPU:
    def __init__(self, device, audio, diagnostics=None, oracle=None, verify=False):
        identity = device.transport.read(0,True,7)
        if identity != b'KFB1\x01\x04\xff': raise ValueError('showcase requires audited PCM2 ABI1.4 / capabilities FF')
        self.device, self.audio = device, audio
        self.diag = diagnostics or Diagnostics()
        device.transport = CountedTransport(device.transport,self.diag)
        self.oracle, self.verify_reads = oracle, verify
        self.page = 0; self.bank = (device.cursor_status()[0] >> 1) & 1
        self.font = BitmapFont8(_Rows(),cache=0)
        self.row = bytearray(320)
        self.clip = None
        self._writes = 0
        self.palette_shadow = list(PALETTE)
        self.palette_active = None

    def fill(self, page, x, y, w, h, color):
        left,top=max(0,x),max(0,y);right,bottom=min(640,x+w),min(360,y+h)
        if self.clip:
            left=max(left,self.clip[0]);top=max(top,self.clip[1])
            right=min(right,self.clip[2]);bottom=min(bottom,self.clip[3])
        if right<=left or bottom<=top:return
        x,y,w,h=left,top,right-left,bottom-top
        self.diag.measure('fill_us',self.device.fill_rect,page,x,y,w,h,color)
        if self.oracle: self.oracle.fill(page,x,y,w,h,color)

    def copy(self, src, sx, sy, dst, dx, dy, w, h):
        # Enforce the exact ABI before sending anything.
        if (sx | dx | w) & 1 or (sx ^ dx) & 7: raise ValueError('BLIT byte phase/alignment')
        self.diag.measure('blit_us',self.device.copy_rect,src,sx,sy,dst,dx,dy,w,h)
        if self.oracle: self.oracle.copy(src,sx,sy,dst,dx,dy,w,h)

    def write(self, address, data):
        self.device.write_bytes(address,data); self.diag.bytes_written += len(data)
        if self.oracle: self.oracle.write(address,data)
        self._writes=(self._writes+1)&15
        if self._writes==0:collect()

    def text(self, page, x, y, text, color=6, bg=0, scale=1):
        # Existing KAGURA Host glyphs; opaque scanline strips, not a new GPU
        # font engine. X is even, width multiple of 8, at most one 320B row.
        if x & 1 or x < 0 or y < 0 or scale < 1: raise ValueError('text alignment')
        width = len(text)*8*scale
        if x+width > 640 or y+8*scale > 360: raise ValueError('text bounds')
        left,top,right,bottom=x,y,x+width,y+8*scale
        if self.clip:
            left=max(left,self.clip[0]);top=max(top,self.clip[1])
            right=min(right,self.clip[2]);bottom=min(bottom,self.clip[3])
        if right<=left or bottom<=top:return
        if (left|right)&1:raise ValueError('text clip must preserve even byte boundaries')
        glyphs = [self.font.glyph(ch) for ch in text]
        span = (right-left)//2; view = memoryview(self.row)[:span]
        for yy in range(top-y,bottom-y):
            for byte in range(span):
                px=left-x+byte*2
                g0,bit0=divmod(px//scale,8);g1,bit1=divmod((px+1)//scale,8)
                hi=color if glyphs[g0][yy//scale] & (128 >> bit0) else bg
                lo=color if glyphs[g1][yy//scale] & (128 >> bit1) else bg
                view[byte]=(hi<<4)|lo
            self.write(page*115200+(y+yy)*320+left//2,view)

    def palette(self, values):
        if len(values)!=16: raise ValueError('16 palette entries required')
        for i,color in enumerate(values):
            self.device.palette(i,color); self.palette_shadow[i]=color

    def present(self, page):
        self.device.fence()
        self.diag.measure('present_wait_us',self.device.present,page)
        # Synchronous SDK wait(tag) means vblank ACK, not merely CSR DONE submit.
        self.page=page; self.palette_active=tuple(self.palette_shadow)

    def cursor(self, x, y, bank=None, visible=True):
        if bank is None: bank=self.bank
        self.device.cursor_move(x,y,bank,visible)
        generation=self.diag.measure('cursor_wait_us',self.device.cursor_wait)
        self.bank=bank
        return generation

    def shape(self, variant):
        self.device.cursor_wait()
        bank=1-((self.device.cursor_status()[0]>>1)&1)
        data=bytearray(256)
        for y in range(32):
            for x in range(32):
                if variant==0:
                    c=(2 if x==0 or x==y//2 else 1) if y<25 and x<=y//2 else 0
                else:
                    d=(x-15)*(x-15)+(y-15)*(y-15)
                    c=3 if 110<d<190 or x==15 or y==15 else 0
                data[y*8+x//4] |= c << (6-2*(x%4))
        colors=(0xfff,0x112,0x0df) if variant==0 else (0xfff,0x112,0xf85)
        self.device.cursor_shape(bank,data,colors,(0,0) if variant==0 else (15,15))
        return bank

    def crc(self, page):
        value=0; buffer=bytearray(64)
        for offset in range(0,115200,64):
            self.device.read_into(page*115200+offset,buffer)
            value=binascii.crc32(buffer,value)
        return value & 0xffffffff

    def verify(self):
        if self.oracle:
            self.oracle.verify(self.device,0); self.oracle.verify(self.device,1)

    def health(self):
        status=self.device.transport.read(27,False,1)[0]
        error=self.device.transport.read(7,False,1)[0]
        if status & 0x8c or error: raise OSError(error or status,'GPU status fault')
        return status

    def shutdown(self):
        # Called only on a clean frame boundary, never after an uncertain I/O.
        for channel in (0,1): self.audio.pcm_enable(channel,False)
        self.audio.commit()
        for channel in (0,1): self.audio.pcm_stop(channel)
        self.cursor(0,0,visible=False)
        self.device.fence()
        self.palette((0,)*16)
        self.present(self.page)  # Never leave a stale ACTIVE meter on screen.
