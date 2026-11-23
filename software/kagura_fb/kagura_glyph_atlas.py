# SPDX-License-Identifier: Apache-2.0
"""Page-1 resident opaque glyphs for aligned COPY_RECT, page 0 terminal.

Four x phases preserve 6px/12px advances under the current sx%8 == dx%8 ABI.
ASCII stays pinned; other Unicode glyph/phase pairs use a bounded FIFO cache.
"""
import framebuf


class GlyphAtlas:
    def __init__(self, device, font, color=15, background=0):
        self.device, self.font = device, font
        self.color, self.background = color, background
        self.supported = font.glyph(' ')[0] == 6
        self._bits = bytearray(320 * font.height)
        self._view = memoryview(self._bits)
        self._line = framebuf.FrameBuffer(self._bits, 640, font.height, framebuf.GS4_HMSB)
        self.capacity = (360 // font.height) * 20
        if self.capacity <= 380:
            raise ValueError('glyph atlas needs a font height below 18 pixels')
        self.hits = self.misses = self.uploaded_bytes = self.copies = 0
        self.reset()

    def reset(self):
        self._keys = [None] * self.capacity
        self._map = {}
        self._warm_row = 0
        self._next = 380
        self._warm = self.supported

    @property
    def ready(self):
        return not self._warm

    def _store(self, slot, code, phase, width):
        old = self._keys[slot]
        if old is not None:
            del self._map[old]
        key = (code << 3) | phase
        self._keys[slot] = key
        self._map[key] = ((slot % 20) * 32 + phase, (slot // 20) * self.font.height, width)

    def prewarm_step(self):
        """Upload one contiguous 640-pixel atlas strip; no second full buffer."""
        if not self._warm:
            return False
        first = self._warm_row * 20
        end = min(first + 20, 380)
        self._line.fill(self.background)
        entries = []
        for slot in range(first, end):
            code, phase = 32 + slot // 4, (slot & 3) * 2
            x = (slot % 20) * 32 + phase
            width = self.font.glyph(code)[0]
            self.font.draw(self._line, chr(code), x, 0, self.color, self.background)
            entries.append((slot, code, phase, width))
        address = 115200 + self._warm_row * self.font.height * 320
        self.device.write_bytes(address, self._view)
        for entry in entries:
            self._store(*entry)
        self.uploaded_bytes += len(self._bits)
        self._warm_row += 1
        if end == 380:
            self._warm = False
        return True

    def advance(self, character):
        # Pinned glyph metrics avoid repeatedly reading ASCII from the font file
        # when a mixed line collides in the small direct-mapped font cache.
        code = ord(character)
        entry = self._map.get(code << 3) if 32 <= code <= 126 else None
        return entry[2] if entry is not None else self.font._lookup(character)[0]

    def draw(self, character, x, y, width):
        if not self.supported or not self.ready or (x | width) & 1 or x < 0 or x + width > 640 or width > 16:
            return False
        if character == ' ':
            self.device.fill_rect(0, x, y, width, self.font.height, self.background)
            return True
        code, phase = ord(character), x & 7
        key = (code << 3) | phase
        entry = self._map.get(key)
        if entry is None:
            self.misses += 1
            slot = self._next
            self._next += 1
            if self._next == self.capacity:
                self._next = 380
            sx, sy = (slot % 20) * 32 + phase, (slot // 20) * self.font.height
            self._line.fill(self.background)
            self.font.draw(self._line, character, phase, 0, self.color, self.background)
            for row in range(self.font.height):
                start = row * 320 + phase // 2
                self.device.write_bytes(115200 + (sy + row) * 320 + sx // 2,
                                        self._view[start:start + width // 2])
            self.uploaded_bytes += width // 2 * self.font.height
            self._store(slot, code, phase, width)
            entry = self._map[key]
        else:
            self.hits += 1
        self.device.copy_rect(1, entry[0], entry[1], 0, x, y, width, self.font.height)
        self.copies += 1
        return True
