# SPDX-License-Identifier: Apache-2.0
"""M+ terminal surface: UTF-8, CR/LF, backspace, common REPL CSI sequences."""
class Terminal:
    def __init__(self, fb, font, color=15, background=0, atlas=None):
        self.fb, self.font = fb, font
        self.color, self.background = color, background
        self.atlas = atlas
        self.cell = font.glyph(' ')[0]
        self.rows = fb.height // font.height
        self.columns = fb.width // self.cell
        self.x = self.y = 0
        self.saved = (0, 0)
        self._utf8 = bytearray()
        self._escape = None
        self._dirty = {}
        fb.fill(background)

    def _mark(self, x, y, width, height):
        first = y // self.font.height
        last = min(self.rows - 1, (y + height - 1) // self.font.height)
        for row in range(first, last + 1):
            old = self._dirty.get(row)
            self._dirty[row] = (x, x + width) if old is None else (min(old[0], x), max(old[1], x + width))

    def flush(self):
        for row in sorted(self._dirty):
            left, right = self._dirty[row]
            self.fb.show(left, row * self.font.height, right - left, self.font.height, present=False)
        self._dirty = {}

    def _newline(self):
        self.x = 0
        self.y += 1
        if self.y < self.rows:
            return
        self.flush()
        h = self.font.height
        if self.atlas is None or not self.atlas.supported:
            self.fb.scroll(0, -h)
            self.fb.fill_rect(0, (self.rows - 1) * h, self.fb.width, self.fb.height - (self.rows - 1) * h, self.background)
        dev = self.fb.device
        dev.copy_rect(self.fb.page, 0, h, self.fb.page, 0, 0, self.fb.width, (self.rows - 1) * h)
        self.y = self.rows - 1
        dev.fill_rect(self.fb.page, 0, self.y * h, self.fb.width, self.fb.height - self.y * h, self.background)

    def _csi(self, sequence):
        command, args = sequence[-1], sequence[1:-1]
        if args.startswith('?'):
            return
        try:
            values = [int(value) if value else 0 for value in args.split(';')]
        except ValueError:
            return
        if any(value < 0 for value in values):
            return
        count = values[0] or 1
        if command == 'D': self.x = max(0, self.x - count * self.cell)
        elif command == 'C': self.x = min((self.columns - 1) * self.cell, self.x + count * self.cell)
        elif command == 'A': self.y = max(0, self.y - count)
        elif command == 'B': self.y = min(self.rows - 1, self.y + count)
        elif command in ('H', 'f'):
            self.y = min(self.rows - 1, count - 1)
            column = values[1] or 1 if len(values) > 1 else 1
            self.x = min(self.columns - 1, column - 1) * self.cell
        elif command == 'G': self.x = min(self.columns - 1, count - 1) * self.cell
        elif command == 'd': self.y = min(self.rows - 1, count - 1)
        elif command == 's': self.saved = (self.x, self.y)
        elif command == 'u': self.x, self.y = self.saved
        elif command in ('J', 'K') and values[0] in (0, 1, 2):
            # Finish pending RAM uploads first so they cannot repaint erased text.
            self.flush()
            mode = values[0]
            x = min(self.x, self.fb.width - self.cell)
            if command == 'J' and mode == 2:
                self._erase(0, 0, self.fb.width, self.fb.height)
                return
            if command == 'J' and mode == 1 and self.y:
                self._erase(0, 0, self.fb.width, self.y * self.font.height)
            start = 0 if mode in (1, 2) else x
            width = x + self.cell if mode == 1 else self.fb.width - start
            self._erase(start, self.y * self.font.height, width, self.font.height)
            if command == 'J' and mode == 0:
                top = (self.y + 1) * self.font.height
                self._erase(0, top, self.fb.width, self.fb.height - top)

    def _erase(self, x, y, width, height):
        if width <= 0 or height <= 0:
            return
        if self.atlas is None or not self.atlas.supported:
            self.fb.fill_rect(x, y, width, height, self.background)
        self.fb.device.fill_rect(self.fb.page, x, y, width, height, self.background)

    def character(self, ch):
        if self._escape is not None:
            self._escape += ch
            if len(self._escape) > 24 or (len(self._escape) == 1 and ch != '['):
                self._escape = None
            elif len(self._escape) > 1 and '@' <= ch <= '~':
                self._csi(self._escape)
                self._escape = None
            return
        if ch == '\x1b': self._escape = ''; return
        if ch == '\r': self.x = 0; return
        if ch == '\n': self._newline(); return
        if ch == '\b': self.x = max(0, self.x - self.cell); return
        if ch == '\t':
            for _ in range(4 - (self.x // self.cell) % 4): self.character(' ')
            return
        if ord(ch) < 32 or ord(ch) == 127:
            return
        width = self.atlas.advance(ch) if self.atlas is not None else self.font._lookup(ch)[0]
        if self.x + width > self.fb.width:
            self._newline()
        y = self.y * self.font.height
        if self.atlas is None or not self.atlas.draw(ch, self.x, y, width):
            self.font.draw(self.fb, ch, self.x, y, self.color, self.background)
            self._mark(self.x, y, width, self.font.height)
        self.x += width

    def feed(self, data):
        for value in data:
            if value < 128:
                if self._utf8:
                    self.character('?')
                    self._utf8 = bytearray()
                self.character(chr(value))
                continue
            self._utf8.append(value)
            first = self._utf8[0]
            length = 2 if 0xc2 <= first <= 0xdf else 3 if 0xe0 <= first <= 0xef else 4 if 0xf0 <= first <= 0xf4 else 1
            if len(self._utf8) >= length:
                try: ch = self._utf8.decode('utf-8')
                except UnicodeError: ch = '?'
                self.character(ch)
                self._utf8 = bytearray()
