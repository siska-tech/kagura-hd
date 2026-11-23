# SPDX-License-Identifier: Apache-2.0
"""File-backed M+ bitmap font. Inspired by KAGURA-9 kagura_ja's binary search.

KMF1: <4sBBH header (magic, height, row bytes, count), sorted fixed records:
<IB (Unicode code point, advance) followed by height * row_bytes MSB-first bits.
The caller owns the font lifetime. No full-font allocation or unbounded cache.
"""
import struct


class Font:
    def __init__(self, path, cache=64):
        if not isinstance(cache, int) or cache < 0 or cache > 256 or cache & (cache - 1):
            raise ValueError('cache must be 0 or a power of two up to 256')
        f = open(path, 'rb')
        try:
            header = f.read(8)
            if len(header) != 8 or header[:4] != b'KMF1':
                raise ValueError('not a KMF1 font')
            _, self.height, self.row_bytes, self.count = struct.unpack('<4sBBH', header)
            if not 1 <= self.height <= 32 or not 1 <= self.row_bytes <= 4 or not self.count:
                raise ValueError('invalid font metrics')
            self._size = 5 + self.height * self.row_bytes
            f.seek(0, 2)
            if f.tell() != 8 + self.count * self._size:
                raise ValueError('font size does not match glyph count')
            self._record = bytearray(self._size)
            self._keys = [-1] * cache
            self._glyphs = [None] * cache
            self._mask = cache - 1
        except BaseException:
            f.close()
            raise
        self._file = f

    def glyph(self, character):
        """Return (advance, immutable bitmap), or None for a missing character."""
        if self._file is None:
            raise ValueError('font is closed')
        code = ord(character) if isinstance(character, str) else character
        slot = code & self._mask
        if self._keys and self._keys[slot] == code:
            return self._glyphs[slot]
        lo, hi = 0, self.count - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            self._file.seek(8 + mid * self._size)
            if self._file.readinto(self._record) != self._size:
                raise ValueError('font record truncated')
            found = struct.unpack_from('<I', self._record)[0]
            if found == code:
                width = self._record[4]
                if not 1 <= width <= self.row_bytes * 8:
                    raise ValueError('invalid glyph width')
                glyph = width, bytes(self._record[5:])
                if self._keys:
                    self._keys[slot], self._glyphs[slot] = code, glyph
                return glyph
            if found < code:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def _lookup(self, character):
        glyph = self.glyph(character)
        if glyph is None:
            glyph = self.glyph('?')
        if glyph is None:
            raise ValueError('font has no fallback glyph')
        return glyph

    def measure(self, text):
        width = current = 0
        height = self.height
        for ch in text:
            if ch == '\n':
                width, current = max(width, current), 0
                height += self.height
            else:
                current += self._lookup(ch)[0]
        return max(width, current), height

    def draw(self, target, text, x, y, color=15, background=None):
        """Draw to any framebuf surface; clipping is handled by its primitives."""
        if not isinstance(color, int) or not 0 <= color <= 15:
            raise ValueError('color must be 0..15')
        if background is not None and (not isinstance(background, int) or not 0 <= background <= 15):
            raise ValueError('background must be None or 0..15')
        left = x
        for ch in text:
            if ch == '\n':
                x, y = left, y + self.height
                continue
            width, bits = self._lookup(ch)
            if background is not None:
                target.fill_rect(x, y, width, self.height, background)
            for row in range(self.height):
                col = 0
                while col < width:
                    if bits[row * self.row_bytes + col // 8] & (128 >> (col & 7)):
                        start = col
                        col += 1
                        while col < width and bits[row * self.row_bytes + col // 8] & (128 >> (col & 7)):
                            col += 1
                        target.hline(x + start, y + row, col - start, color)
                    else:
                        col += 1
            x += width
        return x, y

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
