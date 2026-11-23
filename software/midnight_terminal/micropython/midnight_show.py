# SPDX-License-Identifier: Apache-2.0
"""All scene decisions and drawing instructions, executed by MicroPython."""
from midnight_assets import CHARS, ADV, PALETTES, SCREEN, EYE


def ramp_in(t, start, length):
    return max(0, min(256, (t - start) * 256 // length))


def ramp_out(t, end, length):
    return max(0, min(256, (end - t) * 256 // length))


def lerp(a, b, t):
    result = 0
    for shift in (0, 4, 8):
        ca, cb = (a >> shift) & 15, (b >> shift) & 15
        n = (cb - ca) * t + 128
        # Match the original C renderer's signed division, including fades out.
        result |= (ca + (n // 256 if n >= 0 else -((-n) // 256))) << shift
    return result


class Text:
    def __init__(self, text, font=0):
        self.font = font
        try:
            self.glyphs = bytes(CHARS[font].index(ch) for ch in text)
        except ValueError:
            raise ValueError('text contains a character outside the bundled font: ' + text)
        self.length = len(self.glyphs)
        self.width = sum(ADV[font][g] for g in self.glyphs)


class Show:
    def __init__(self, backend, script):
        self.gpu, self.script = backend, script
        self.boundaries = tuple(t for _, t in script.SCENES)
        if (len(self.boundaries) != 7 or self.boundaries[0] != 0 or
                any(a >= b for a, b in zip(self.boundaries, self.boundaries[1:])) or
                script.END_MS <= self.boundaries[-1]):
            raise ValueError('seven increasing scene boundaries starting at zero required')
        self.at = dict(script.SCENES)
        self.renderers = tuple(getattr(self, 'scene_' + name) for name, _ in script.SCENES)
        self.subtitle, self.speaker = Text(script.SUBTITLE), Text(script.SPEAKER)
        self.dialogues = tuple((at, Text(s)) for at, _, s in script.DIALOGUE)
        self.choices = tuple(Text(s) for s in script.CHOICES)
        if len(self.choices) != 3:
            raise ValueError('the choice window has three items')
        self.terminal = tuple((at, Text(s)) for at, s in script.TERMINAL)
        self.logs, self.message = tuple(Text(s, 1) for s in script.LOGS), Text(script.MESSAGE)
        if not self.logs:
            raise ValueError('at least one anomaly log required')
        self.palette, self.sent = [0] * 16, [None] * 16
        self.scene = self.frames = 0
        self.scene_frames = [0] * 7
        self.last_ms = -1
        self.seed = 0x9e3779b9
        self.dialogue_line, self.dialogue_drawn, self.marker = -1, 0, False
        self.eye_state = 0
        self.terminal_ready = self.bar_ready = self.title_text = False
        self.choice_open = self.choice_closed = False
        self.subtitle_drawn = self.choice_selected = self.log_written = self.message_drawn = 0
        self.term_drawn = [0] * len(self.terminal)
        self.cursor_x = self.cursor_y = 0
        self.cursor_on = False

    def preload(self):
        self.present(0)
        self.gpu.image(0, 0)
        self.gpu.image(1, 1)

    def random(self):
        x = self.seed
        x = (x ^ (x << 13)) & 0xffffffff
        x ^= x >> 17
        self.seed = (x ^ (x << 5)) & 0xffffffff
        return self.seed

    def set_palette(self, base, fade=256):
        for i in range(16):
            self.palette[i] = lerp(0, base[i], fade)

    def present(self, page):
        for i in range(16):
            if self.palette[i] != self.sent[i]:
                self.gpu.palette(i, self.palette[i])
                self.sent[i] = self.palette[i]
        self.gpu.present(page)

    def text(self, page, x, y, text, first=0, last=None, fg=7, bg=1, scale=1):
        if last is None:
            last = text.length
        if first < last:
            self.gpu.text(page, x, y, text.font, text.glyphs, first, last, fg, bg, scale)

    def big_text(self, page, y, text, scale, color):
        width = (len(text) * 6 - 1) * scale if text else 0
        self.gpu.big_text(page, ((640 - width) // 2) & ~1, y, text, scale, color)

    def box(self, page, x0, y0, x1, y1):
        fill = self.gpu.fill
        fill(page, x0, y0, x1-x0, y1-y0, 1)
        fill(page, x0, y0, x1-x0, 2, 6)
        fill(page, x0, y1-2, x1-x0, 2, 6)
        fill(page, x0, y0, 2, y1-y0, 6)
        fill(page, x1-2, y0, 2, y1-y0, 6)

    def dialogue_box(self, page):
        self.box(page, 16, 280, 624, 352)
        self.gpu.fill(page, 28, 270, 72, 22, 14)
        self.text(page, 40+(48-self.speaker.width)//2, 275, self.speaker, fg=7, bg=14)

    def dialogue(self, page, ms, start, end):
        cur = -1
        for i, (at, _) in enumerate(self.dialogues):
            if start <= at < end and ms >= at:
                cur = i
        if cur < 0:
            return
        at, text = self.dialogues[cur]
        if cur != self.dialogue_line:
            self.gpu.fill(page, 32, 300, 584, 22, 1)
            self.dialogue_line, self.dialogue_drawn, self.marker = cur, 0, False
        due = min(text.length, (ms-at)//self.script.CHAR_MS+1)
        if due > self.dialogue_drawn:
            self.text(page, 36, 304, text, self.dialogue_drawn, due)
            self.dialogue_drawn = due
        marker = due == text.length and bool((ms//400) % 2)
        if marker != self.marker:
            for r in range(6):
                self.gpu.fill(page, 598+r, 334+r, 12-2*r, 1, 6 if marker else 1)
            self.marker = marker

    def eyes(self, page, ms, allow_red=False):
        want = 1 if ms % 3700 < 140 else 0
        if allow_red and self.script.RED_EYES[0] <= ms < self.script.RED_EYES[1]:
            want = 2
        if want != self.eye_state:
            self.gpu.blit(want, page, *EYE)
            self.eye_state = want

    def scene_title(self, ms):
        end = self.at['bar']
        fade = ramp_in(ms, 0, 1500) if ms < end-1000 else ramp_out(ms, end, 1000)
        base = list(PALETTES[0])
        k = ms//85
        base[12+k%3], base[12+(k+2)%3], base[12+(k+1)%3] = 0x9bd, 0x46a, 0x213
        base[15] = lerp(0, 0xfff, ramp_in(ms, 3000, 1200))
        self.set_palette(base, fade)
        if ms >= 3000 and not self.title_text:
            self.big_text(0, 18, self.script.TITLE, 4, 0)
            self.big_text(0, 14, self.script.TITLE, 4, 15)
            self.title_text = True
        if ms >= 5500:
            due = min(self.subtitle.length, (ms-5500)//90+1)
            self.text(0, ((640-self.subtitle.width)//2)&~1, 318, self.subtitle,
                      self.subtitle_drawn, due, fg=15)
            self.subtitle_drawn = due
        self.present(0)

    def choice_item(self, i, selected):
        y, bg = 136+i*32, 5 if selected else 1
        self.gpu.fill(1, 402, y-6, 208, 24, bg)
        if selected:
            for r in range(5):
                self.gpu.fill(1, 408+r, y+1+r, 1, 10-2*r, 14)
        self.text(1, 426, y, self.choices[i], bg=bg)

    def scene_bar(self, ms):
        s, end = self.script, self.at['terminal']
        fade = ramp_in(ms, self.at['bar'], 1000) if ms < end-1000 else ramp_out(ms, end, 600)
        self.set_palette(PALETTES[1], fade)
        if s.CHOICE_PICK <= ms < s.CHOICE_PICK+120:
            self.palette[5] = 0xfff
        self.eyes(1, ms)
        self.dialogue(1, ms, self.at['bar'], end)
        if ms >= s.CHOICE_SHOW and not self.choice_open:
            self.box(1, 396, 120, 616, 230)
            for i in range(3):
                self.choice_item(i, i == 0)
            self.choice_open = True
        if self.choice_open and not self.choice_closed:
            selected = min(2, sum(ms >= at for at in s.CHOICE_MOVES))
            if selected != self.choice_selected:
                self.choice_item(self.choice_selected, False)
                self.choice_item(selected, True)
                self.choice_selected = selected
            if ms >= s.CHOICE_PICK+600:
                self.gpu.image(1, 1, 396, 120, 616, 230)
                self.choice_closed = True
        self.present(1)
        if ms >= self.at['bar']+18000 and not self.terminal_ready:
            self.gpu.image(2, 0)
            self.terminal_ready = True

    def scene_terminal(self, ms):
        s = self.script
        self.set_palette(PALETTES[2], ramp_in(ms, self.at['terminal'], 600))
        tx = (SCREEN[0]+18)&~1
        for i, (at, text) in enumerate(self.terminal):
            if ms < at:
                break
            due = min(text.length, (ms-at)//s.TERM_CHAR_MS+1)
            if due > self.term_drawn[i]:
                y = 70+i*22
                if self.cursor_on:
                    self.gpu.fill(0, self.cursor_x, self.cursor_y, 8, 13, 13)
                    self.cursor_on = False
                self.text(0, tx, y, text, self.term_drawn[i], due, fg=14, bg=13)
                self.term_drawn[i] = due
                self.cursor_x, self.cursor_y = (tx+text.width*due//text.length)&~1, y
        on = bool((ms//350)%2)
        if on != self.cursor_on and self.cursor_y:
            self.gpu.fill(0, self.cursor_x, self.cursor_y, 8, 13, 14 if on else 13)
            self.cursor_on = on
        if ms >= s.GLITCH_START:
            level = (ms-s.GLITCH_START)*256//(self.at['anomaly']-s.GLITCH_START)
            x0, y0, x1, y1 = SCREEN
            for _ in range(1+level//64):
                y, h, d = y0+self.random()%(y1-y0-12), 2+self.random()%10, (self.random()%5-2)*8
                if d:
                    self.gpu.copy(0, x0+max(0, -d), y, 0, x0+max(0, d), y, x1-x0-abs(d), h)
            if self.random()%4 == 0:
                h, w = 2+self.random()%6, (4+self.random()%20)&~1
                y = y0+self.random()%(y1-y0-8)
                x = (x0+self.random()%(x1-x0-24))&~1
                self.gpu.fill(0, x, y, w, h, 11)
            if self.random()%3 == 0:
                self.palette[14], self.palette[13] = 0xe38, 0x201
            for i in range(16):
                self.palette[i] = lerp(self.palette[i], 0, level*3//4)
        self.present(0)

    def scene_anomaly(self, ms):
        s, ts = self.script, (ms-self.at['anomaly'])//100
        self.set_palette(PALETTES[3], ramp_out(ms, s.ANOMALY_END, 500))
        if self.random()&7 == 0:
            for i in range(16):
                self.palette[i] = 0xfff-self.palette[i]
        due = (6*ts+ts*ts*12//100)//10 if ts < 110 else 211+(ts-110)*32//10
        for _ in range(min(6, due-self.log_written)):
            i = self.log_written
            self.log_written += 1
            a, b = self.logs[(i*7)%len(self.logs)], self.logs[(i*11+3)%len(self.logs)]
            x, y = ((i*37)%13)*16, (i%45)*8
            xb = (x+a.width+24+((i*53)%7)*16)&~1
            self.gpu.fill(1, 0, y, x, 8, 0)
            self.text(1, x, y, a, fg=14 if i%5 == 0 else 7, bg=0)
            self.gpu.fill(1, x+a.width, y, xb-x-a.width, 8, 0)
            if xb+b.width <= 640:
                self.text(1, xb, y, b, fg=14 if i%3 == 0 else 7, bg=0)
                self.gpu.fill(1, xb+b.width, y, 640-xb-b.width, 8, 0)
            else:
                self.gpu.fill(1, xb, y, 640-xb, 8, 0)
        for _ in range(3 if ms >= s.ANOMALY_FULL else 1):
            h = 2+self.random()%12
            y, d = self.random()%(360-h), (self.random()%9-4)*8
            if d:
                self.gpu.copy(1, max(0, -d), y, 1, max(0, d), y, 640-abs(d), h)
        self.present(1)

    def scene_message(self, ms):
        s = self.script
        heart = ((ms-s.MESSAGE_START+600)&0xffffffff)%1150
        base = [0x000, 0x200, 0x300, 0x500, 0, 0, 0, 0xfdd, 0, 0, 0, 0, 0, 0, 0xc23, 0xfff]
        base[7] = lerp(0xc66, 0xfdd, 256-heart*256//300 if heart < 300 else 0)
        self.set_palette(base, ramp_out(ms, s.MESSAGE_END, 600))
        if ms >= s.MESSAGE_START:
            due = min(self.message.length, (ms-s.MESSAGE_START)//s.MESSAGE_CHAR_MS+1)
            self.text(0, ((640-self.message.width*2)//2)&~1, 166, self.message,
                      self.message_drawn, due, fg=7, bg=0, scale=2)
            self.message_drawn = due
        self.present(0)
        if ms >= self.at['message']+5000 and not self.bar_ready:
            self.gpu.image(1, 1)
            self.dialogue_box(1)
            self.bar_ready = True

    def scene_restore(self, ms):
        s = self.script
        fade = ramp_in(ms, self.at['restore'], 1000) if ms < self.at['end']-1500 else ramp_out(ms, self.at['end'], 700)
        self.set_palette(PALETTES[3] if s.RED_EYES[0] <= ms < s.RED_EYES[1] else PALETTES[1], fade)
        self.eyes(1, ms, True)
        self.dialogue(1, ms, self.at['restore'], self.at['end'])
        self.present(1)

    def scene_end(self, ms):
        base = (0x000, 0x102, 0x213, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x8ac, 0xe38, 0xeef)
        end = self.script.END_MS
        self.set_palette(base, ramp_in(ms, self.at['end'], 1000) if ms < end-2500 else ramp_out(ms, end, 2500))
        self.present(0)

    def enter(self, scene):
        name = self.script.SCENES[scene][0]
        if name == 'bar':
            self.dialogue_box(1)
        elif name == 'terminal' and not self.terminal_ready:
            self.gpu.image(2, 0)
            self.terminal_ready = True
        elif name == 'message':
            self.gpu.fill(0, 0, 0, 640, 360, 0)
        elif name == 'restore':
            if not self.bar_ready:
                self.gpu.image(1, 1)
                self.dialogue_box(1)
                self.bar_ready = True
            self.dialogue_line, self.eye_state = -1, 0
        elif name == 'end':
            self.gpu.fill(0, 0, 0, 640, 360, 0)
            for y, scale, color, text in zip((120, 196, 222), (5, 2, 2), (15, 13, 14), self.script.END_LINES):
                self.big_text(0, y, text, scale, color)

    def frame(self, ms):
        if ms < self.last_ms or ms < 0:
            raise ValueError('frame timestamps must increase')
        ms = min(ms, self.script.END_MS-1)
        self.last_ms = ms
        while self.scene < 6 and ms >= self.boundaries[self.scene+1]:
            self.scene += 1
            self.enter(self.scene)
        self.frames += 1
        self.scene_frames[self.scene] += 1
        self.renderers[self.scene](ms)
