"""Title and terminal scenes from the project owner's reference artwork
(art/*-reference-640x360.png, image-generation-AI illustrations; see LICENSES.md)."""
import random
from pathlib import Path
import numpy as np
from PIL import Image
from paint import rgb444, quantize
from bar_reference import palette

ART = Path(__file__).resolve().parents[1]/'art'
# Terminal: the CRT glass becomes one flat colour (13) so text (14) can be written
# on it; 11 is the glitch colour, 15 the bright highlight. Text area in mt_show.c.
SCREEN = (186, 58, 454, 222)
TITLE_FREE = 12                      # 12..14 rain phases, 15 runtime title text

def load(name):
    return np.asarray(Image.open(ART/f'{name}-reference-640x360.png').convert('RGB'), np.float32)/255.0

def rain_overlay(idx, seed=5, count=300, free=TITLE_FREE, region=(0, 0, 640, 360), length=(6, 14)):
    """3-phase rain streaks: each streak is 3 stacked segments with successive phase indices."""
    r = random.Random(seed)
    x0, y0, x1, y1 = region
    for _ in range(count):
        x = r.uniform(x0, x1); y = r.uniform(y0, y1); L = r.randint(*length); ph = r.randint(0, 2)
        for seg in range(3):
            for k in range(L):
                yy = int(y+seg*L+k); xx = int(x-(seg*L+k)*0.18)
                if y0 <= yy < y1 and x0 <= xx < x1: idx[yy, xx] = free+((ph+seg) % 3)
    return idx

def _exclude(pal, indices):
    p = pal.copy(); p[list(indices)] = 9.0           # unreachable while quantizing the picture
    return p

def title_indices():
    img = load('title')
    pal = palette(img, roles={0: '000', 1: '102', 10: 'e83', 11: 'e48', 12: '000', 13: '000', 14: '000', 15: 'fff'})
    idx = quantize(img, _exclude(pal, (12, 13, 14, 15)), dither=0.06)
    return rain_overlay(idx), pal

def terminal_indices():
    img = load('terminal')
    x0, y0, x1, y1 = SCREEN
    glass = img[y0:y1, x0:x1]
    lum = glass@np.array([0.30, 0.59, 0.11], np.float32)
    dark = lum < 0.22
    screen = np.round(glass[dark].mean(0)*15)/15
    hexs = '%x%x%x' % tuple(int(v*15) for v in screen)
    pal = palette(img, roles={0: '000', 11: 'e38', 13: hexs, 14: '5fb', 15: 'dff'})
    idx = quantize(img, _exclude(pal, (14, 15)), dither=0.06)
    sub = idx[y0:y1, x0:x1]; sub[dark] = 13                # flat glass, bezel untouched
    return idx, pal
