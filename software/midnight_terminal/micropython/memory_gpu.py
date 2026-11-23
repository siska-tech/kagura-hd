"""Host-only 4bpp framebuffer model for checking the Python renderer."""
from pathlib import Path
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


class MemoryGPU:
    def __init__(self):
        c = (ROOT/'generated/assets.c').read_text(encoding='utf-8')
        self.arrays = {name: tuple(int(v.strip(), 0) for v in body.split(',') if v.strip())
                       for name, body in re.findall(r'const uint(?:8|16)_t (\w+)\[\d+\]=\{([^}]+)\}', c)}
        self.images = tuple(zlib.decompress(bytes(self.arrays['img_'+n]), -12) for n in ('title', 'bar', 'terminal'))
        font = (ROOT.parent/'fm_megademo/src/font.c').read_text()
        self.ascii = {char: tuple(int(row.replace('.', '0').replace('#', '1'), 2)
                                 for row in re.findall(r'"([.#]{5})"', body))
                      for char, body in re.findall(r"\{'(.)',\{([^}]+)\}\}", font)}
        self.pages = [bytearray(115200), bytearray(115200)]
        self.colors, self.page = [0]*16, 0
        self.now, self.closed = 0, False
        self.notes = []
        self.schedule = ()

    def open(self, patches, events, dsp=None):
        self.patches, self.schedule, self.score = bytes(patches), b''.join(events) if isinstance(events,(tuple,list)) else bytes(events), bool(events)
        self.closed = False

    def start(self):
        self.now = 0

    def close(self):
        self.closed = True

    def elapsed_us(self):
        return self.now

    def wait_until(self, until):
        self.now = max(self.now, until)

    def service(self):
        pass

    def check(self):
        pass

    def stats(self):
        return (1218, 56000, 100, 0)

    def write(self, address, data):
        page,offset=divmod(address,115200)
        assert page in (0,1) and offset+len(data)<=115200
        self.pages[page][offset:offset+len(data)]=data

    def glyph_run(self,page,x,y,glyphs,adv,rows,height,first,last,fg,bg,scale):
        font=0 if height==13 else 1
        name='mplus' if font==0 else 'misaki'
        assert bytes(adv)==bytes(self.arrays[name+'_adv'])
        expected=struct.pack('<'+'H'*len(self.arrays[name+'_rows']),*self.arrays[name+'_rows'])
        assert bytes(rows)==expected
        self.text(page,x,y,font,glyphs,first,last,fg,bg,scale)

    def note_on(self, *args):
        self.notes.append(('on',)+args)

    def note_off(self, voice):
        self.notes.append(('off', voice))

    def all_off(self):
        self.notes.append(('all_off',))

    def palette(self, index, color):
        assert 0 <= index < 16 and 0 <= color <= 4095
        self.colors[index] = color

    def present(self, page):
        assert page in (0, 1)
        self.page = page

    def fill(self, page, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        assert page in (0, 1) and 0 <= color <= 15
        assert 0 <= x < x+w <= 640 and 0 <= y < y+h <= 360, (x, y, w, h)
        data = self.pages[page]
        end = x+w
        for row in range(y, y+h):
            start = row*320
            if x&1:
                pos = start+x//2
                data[pos] = (data[pos]&0xf0)|color
            if end&1:
                pos = start+end//2
                data[pos] = (data[pos]&15)|(color<<4)
            first, last = (x+1)//2, end//2
            if first < last:
                data[start+first:start+last] = bytes((color*17,))*(last-first)

    def copy(self, sp, sx, sy, dp, dx, dy, w, h):
        assert not ((sx|dx|w)&1) and sx%8 == dx%8
        assert sp in (0, 1) and dp in (0, 1)
        assert 0 <= sx < sx+w <= 640 and 0 <= dx < dx+w <= 640
        assert 0 <= sy < sy+h <= 360 and 0 <= dy < dy+h <= 360
        rows = range(h-1, -1, -1) if sp == dp and dy > sy else range(h)
        for r in rows:
            src, dst = (sy+r)*320+sx//2, (dy+r)*320+dx//2
            self.pages[dp][dst:dst+w//2] = self.pages[sp][src:src+w//2]

    def image(self, asset, page, x0=0, y0=0, x1=640, y1=360):
        assert asset in (0, 1, 2) and page in (0, 1)
        assert not ((x0|x1)&1) and 0 <= x0 < x1 <= 640 and 0 <= y0 < y1 <= 360
        for y in range(y0, y1):
            start, end = y*320+x0//2, y*320+x1//2
            self.pages[page][start:end] = self.images[asset][start:end]

    def blit(self, asset, page, x, y, w, h):
        patch = self.arrays['eye_'+('open', 'closed', 'red')[asset]]
        assert w*h//2 == len(patch) and x+w <= 640 and y+h <= 360
        for row in range(h):
            start = (y+row)*320+x//2
            self.pages[page][start:start+w//2] = bytes(patch[row*w//2:(row+1)*w//2])

    def text(self, page, x, y, font, glyphs, first, last, fg, bg, scale):
        name, height = ('mplus', 13) if font == 0 else ('misaki', 8)
        adv, rows = self.arrays[name+'_adv'], self.arrays[name+'_rows']
        x += sum(adv[g]*scale for g in glyphs[:first])
        width = min(640-x, sum(adv[g]*scale for g in glyphs[first:last]))
        if width <= 0:
            return
        assert page in (0, 1) and x >= 0 and not x&1 and not width&1
        assert 0 <= y < y+height*scale <= 360
        for r in range(height*scale):
            line, px = bytearray((bg*17,))*(width//2), 0
            for g in glyphs[first:last]:
                bits = rows[g*height+r//scale]
                for c in range(adv[g]*scale):
                    if px >= width:
                        break
                    if bits >> (adv[g]-1-c//scale)&1:
                        line[px//2] = (line[px//2]&0xf0)|fg if px&1 else (line[px//2]&15)|(fg<<4)
                    px += 1
            start = (y+r)*320+x//2
            self.pages[page][start:start+len(line)] = line

    def big_text(self, page, x, y, text, scale, color):
        for char in text:
            for row, bits in enumerate(self.ascii.get(char.upper(), (0,)*7)):
                for c in range(5):
                    if bits >> (4-c)&1:
                        self.fill(page, x+c*scale, y+row*scale, scale, scale, color)
            x += 6*scale
