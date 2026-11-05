# SPDX-License-Identifier: Apache-2.0
"""PC-only unpacked pixel oracle. Never imported by the RP2040 runtime."""
class FramebufferOracle:
    def __init__(self): self.pages = [bytearray(640*360), bytearray(640*360)]

    def fill(self, page, x, y, w, h, color):
        for yy in range(max(0,y), min(360,y+h)):
            left, right = max(0,x), min(640,x+w)
            if right > left: self.pages[page][yy*640+left:yy*640+right] = bytes([color])*(right-left)

    def copy(self, src, sx, sy, dst, dx, dy, w, h):
        # Snapshot the pixel rectangle before any destination write. This is
        # deliberately different from the device model's packed byte algorithm.
        rows = [self.pages[src][(sy+y)*640+sx:(sy+y)*640+sx+w] for y in range(h)]
        for y,row in enumerate(rows): self.pages[dst][(dy+y)*640+dx:(dy+y)*640+dx+w] = row

    def write(self, address, data):
        for i,value in enumerate(data):
            a = address+i
            if a < 230400:
                page, offset = divmod(a,115200)
                self.pages[page][offset*2] = value >> 4
                self.pages[page][offset*2+1] = value & 15

    def verify(self, device, page):
        buffer = bytearray(64)
        for offset in range(0,115200,64):
            device.read_into(page*115200+offset,buffer)
            for i,value in enumerate(buffer):
                at = (offset+i)*2
                if (value >> 4, value & 15) != (self.pages[page][at],self.pages[page][at+1]):
                    raise AssertionError('FB oracle mismatch page=%d byte=%d expected=%02X actual=%02X' %
                        (page,offset+i,(self.pages[page][at]<<4)|self.pages[page][at+1],value))
