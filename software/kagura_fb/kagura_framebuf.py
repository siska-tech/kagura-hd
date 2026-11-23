# SPDX-License-Identifier: Apache-2.0
"""MicroPython native GS4_HMSB drawing surface for KAGURA-HD (640x360)."""
import framebuf


class FrameBuffer(framebuf.FrameBuffer):
    width = 640
    height = 360

    def __init__(self, device, page=0, buffer=None):
        if page not in (0, 1):
            raise ValueError('page must be 0 or 1')
        if buffer is None:
            buffer = bytearray(115200)
        if len(buffer) != 115200:
            raise ValueError('buffer must contain 115200 bytes')
        super().__init__(buffer, 640, 360, framebuf.GS4_HMSB)
        self.device, self.page, self.buffer = device, page, buffer
        self._view = memoryview(buffer)

    def show(self, x=0, y=0, width=640, height=360, present=True):
        """Upload a clipped region, then optionally present this page.

        Odd horizontal edges expand to pixel pairs from the local buffer.
        Upload failures propagate without presenting an incomplete frame.
        """
        if any(not isinstance(v, int) for v in (x, y, width, height)):
            raise TypeError('region must use integer coordinates')
        left, top = max(0, x), max(0, y)
        right, bottom = min(640, x + width), min(360, y + height)
        if left >= right or top >= bottom:
            return 0
        left &= ~1
        right = (right + 1) & ~1
        base = self.page * 115200
        if left == 0 and right == 640:
            start, end = top * 320, bottom * 320
            self.device.write_bytes(base + start, self._view[start:end])
        else:
            for row in range(top, bottom):
                start, end = row * 320 + left // 2, row * 320 + right // 2
                self.device.write_bytes(base + start, self._view[start:end])
        if present:
            self.device.present(self.page)
        return (right - left) // 2 * (bottom - top)

    def text_jp(self, text, x, y, font, color=15, background=None):
        """Draw Unicode text with a kagura_ja.Font; return final pen position."""
        return font.draw(self, text, x, y, color, background)
