"""Bar scene from the project owner's reference artwork (art/bar-reference-640x360.png,
an image-generation-AI illustration supplied for MIDNIGHT TERMINAL; see LICENSES.md).
Builds the 16-colour palette with fixed UI roles and the blink / red-eye variants."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from paint import rgb444, quantize

ART = Path(__file__).resolve().parents[1]/'art/bar-reference-640x360.png'
# Fixed roles used by src/mt_show.c: 1 dialogue box, 5 choice highlight,
# 6 borders/marker, 7 text, 14 name plate. Others are chosen from the picture.
ROLES = {0: '000', 1: '102', 5: '33a', 6: '8ad', 7: 'eef', 14: 'c23'}
EYES = [  # centre x, y, half width, half height, tilt (deg) in 640x360 pixels
    (166.0, 131.0, 11.0, 6.5, 8.0),
    (206.0, 122.5, 12.0, 6.0, 8.0)]
EYE_RECT = (150, 112, 224, 142)       # patch rectangle, x even

def load():
    return np.asarray(Image.open(ART).convert('RGB'), np.float32)/255.0

def _mask(draw_fn, scale=4, blur=0.0):
    im = Image.new('L', (640*scale, 360*scale), 0)
    draw_fn(ImageDraw.Draw(im), scale)
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur*scale))
    return np.asarray(im.resize((640, 360), Image.BOX), np.float32)/255.0

def _ellipse_pts(cx, cy, rx, ry, tilt, s, n=40):
    t = np.radians(tilt)
    pts = []
    for k in range(n):
        a = 2*np.pi*k/n
        x, y = rx*np.cos(a), ry*np.sin(a)
        pts.append(((cx+x*np.cos(t)-y*np.sin(t))*s, (cy+x*np.sin(t)+y*np.cos(t))*s))
    return pts

BLINK = Path(__file__).resolve().parents[1]/'art/blink-reference-eyes.png'
BLINK_OFFSET = (480, 300)                 # crop origin in the 1671x941 closed-eyes illustration
# Anchors: base = just below each open eye's dark centroid; reference = each closed lash line.
BASE_ANCHOR = ((162.0, 133.0), (206.5, 121.5))
REF_ANCHOR = ((566.8, 377.4), (749.5, 349.9))

def closed_eyes(img):
    """Paste the closed eyes of the owner's reference (same character, other framing),
    scaled/rotated so both lash lines land on this picture's eyes, colour-matched."""
    (qx0, qy0), (qx1, qy1) = BASE_ANCHOR
    (px0, py0), (px1, py1) = REF_ANCHOR
    s = np.hypot(qx1-qx0, qy1-qy0)/np.hypot(px1-px0, py1-py0)
    th = np.arctan2(qy1-qy0, qx1-qx0)-np.arctan2(py1-py0, px1-px0)
    c, n = np.cos(th), np.sin(th)
    a, b, d, e = c/s, n/s, -n/s, c/s                       # base -> reference (inverse map)
    cx = px0-a*qx0-b*qy0-BLINK_OFFSET[0]; fy = py0-d*qx0-e*qy0-BLINK_OFFSET[1]
    ref = Image.open(BLINK).convert('RGB')
    # supersample: warp at 4x then box-reduce
    k = 4
    warped = ref.transform((640*k, 360*k), Image.AFFINE, (a/k, b/k, cx, d/k, e/k, fy), resample=Image.BICUBIC)
    warped = np.asarray(warped.resize((640, 360), Image.BOX), np.float32)/255.0
    tilt = np.degrees(np.arctan2(qy1-qy0, qx1-qx0))
    m = np.zeros((360, 640), np.float32)
    for (ax, ay) in BASE_ANCHOR:
        m = np.maximum(m, _mask(lambda dr, sc, ax=ax, ay=ay: dr.polygon(_ellipse_pts(ax, ay-1.5, 12.5, 8.0, tilt, sc), fill=255), blur=1.2))
    # colour match the pasted skin to this picture (mean over the mask, excluding dark lashes)
    L = lambda x: x@np.array([0.30, 0.59, 0.11], np.float32)
    sel = (m > 0.5) & (L(warped) > 0.45) & (L(img) > 0.45)
    if sel.sum() > 20:
        warped = np.clip(warped+(img[sel].mean(0)-warped[sel].mean(0)), 0, 1)
    return img*(1-m[..., None])+warped*m[..., None]

def red_eyes(img):
    out = img.copy()
    for cx, cy, rx, ry, tilt in EYES:
        m = _mask(lambda d, s: d.polygon(_ellipse_pts(cx+1, cy, rx*0.55, ry*0.95, tilt, s), fill=255))[..., None]
        L = (img*np.array([0.30, 0.59, 0.11], np.float32)).sum(-1, keepdims=True)
        red = np.concatenate([np.clip(L*1.9+0.25, 0, 1), L*0.15, L*0.2], -1)
        out = out*(1-m)+red*m
    return out

def palette(img, iters=24, seed=3, roles=None):
    """16 colours: fixed roles plus k-means picks (RGB444), free slots sorted by luminance."""
    rs = np.random.RandomState(seed)
    px = img.reshape(-1, 3); sample = px[rs.choice(len(px), 60000, replace=False)]
    roles = ROLES if roles is None else roles
    fixed = rgb444(list(roles.values()))
    k = 16-len(fixed)
    cent = sample[rs.choice(len(sample), k, replace=False)].copy()
    wts = np.array([0.30, 0.59, 0.11], np.float32)*3
    for _ in range(iters):
        allc = np.vstack([fixed, cent])
        lab = ((((sample[:, None, :]-allc[None])**2)*wts).sum(-1)).argmin(1)
        for j in range(k):
            sel = sample[lab == j+len(fixed)]
            cent[j] = sel.mean(0) if len(sel) else sample[rs.randint(len(sample))]
    cent = np.round(np.clip(cent, 0, 1)*15)/15
    free = sorted(cent.tolist(), key=lambda c: (np.array(c)*wts).sum())
    pal = np.zeros((16, 3), np.float32)
    for i, h in roles.items(): pal[i] = rgb444([h])[0]
    slots = [i for i in range(16) if i not in roles]
    for i, c in zip(slots, free): pal[i] = c
    return pal

def bar_indices(pal=None, eyes_closed=False, anomaly=False):
    img = load()
    if pal is None: pal = palette(img)
    if eyes_closed: img = closed_eyes(img)
    if anomaly: img = red_eyes(img)
    return quantize(img, pal, dither=0.06), pal
