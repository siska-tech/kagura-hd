# SPDX-License-Identifier: Apache-2.0
"""Application artwork and font data on top of the generic GPU primitives."""
from midnight_assets import ADV, ASCII


class Graphics:
    def __init__(self, backend, asset_dir='mt_data'):
        if not asset_dir.startswith('/') and not (len(asset_dir)>1 and asset_dir[1]==':'):
            import os
            asset_dir=os.getcwd().rstrip('/')+'/'+asset_dir
        self.backend, self.asset_dir = backend, asset_dir
        self.rows = tuple(self._load(n+'_rows.bin') for n in ('mplus','misaki'))
        if any(len(rows)!=len(adv)*h*2 for rows,adv,h in zip(self.rows,ADV,(13,8))):
            raise ValueError('font bitmap file does not match metrics')
        self.patches = tuple(self._load('eye_'+n+'.bin') for n in ('open','closed','red'))
        self._row = bytearray(320)

    def _load(self, name):
        with open(self.asset_dir+'/'+name,'rb') as source:
            return source.read()

    def __getattr__(self, name):
        return getattr(self.backend,name)

    def image(self, asset, page, x0=0, y0=0, x1=640, y1=360):
        name=('title','bar','terminal')[asset]
        if page not in (0,1) or (x0|x1)&1 or not 0<=x0<x1<=640 or not 0<=y0<y1<=360:
            raise ValueError('invalid image rectangle')
        with open(self.asset_dir+'/'+name+'.bin','rb') as source:
            source.seek(y0*320)
            view=memoryview(self._row)
            for y in range(y0,y1):
                if source.readinto(self._row)!=320:
                    raise ValueError('truncated image: '+name)
                self.backend.write(page*115200+y*320+x0//2,view[x0//2:x1//2])

    def blit(self, asset, page, x, y, width, height):
        patch=memoryview(self.patches[asset])
        if len(patch)!=width//2*height:
            raise ValueError('bitmap metrics differ from asset')
        for row in range(height):
            self.backend.write(page*115200+(y+row)*320+x//2,patch[row*width//2:(row+1)*width//2])

    def text(self, page, x, y, font, glyphs, first, last, fg, bg, scale):
        self.backend.glyph_run(page,x,y,glyphs,ADV[font],self.rows[font],
                               13 if font==0 else 8,first,last,fg,bg,scale)

    def big_text(self, page, x, y, text, scale, color):
        for char in text:
            glyph=ASCII.get(char.upper(),b'\0'*7)
            for row,bits in enumerate(glyph):
                c=0
                while c<5:
                    if not bits>>(4-c)&1:
                        c+=1
                        continue
                    end=c
                    while end<5 and bits>>(4-end)&1:
                        end+=1
                    self.backend.fill(page,x+c*scale,y+row*scale,(end-c)*scale,scale,color)
                    c=end
            x+=6*scale
