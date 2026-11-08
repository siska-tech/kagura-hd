"""BDF loading for the distributed M+ 12px and Misaki 8px fonts (vendor archives in
vendor/, licences preserved there). Returns {codepoint: (advance, rows)}
where rows are ints with bit (advance-1-x) set for pixel x."""
import re, tarfile, zipfile, hashlib, json
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1]/'vendor'
WORK = Path(__file__).resolve().parents[3]/'build/midnight-terminal/fonts'

def _check():
    prov = json.loads((VENDOR/'provenance.json').read_text())
    for name, entry in prov.items():
        assert hashlib.sha256((VENDOR/name).read_bytes()).hexdigest() == entry['sha256'], f'font source changed: {name}'

def parse_bdf(text):
    head = text.split('STARTCHAR')[0]
    ascent = int(re.search(r'FONT_ASCENT (\d+)', text)[1]); height = ascent+int(re.search(r'FONT_DESCENT (\d+)', text)[1])
    jis = 'jisx0208' in head; kana = 'jisx0201' in head
    out = {}
    for g in text.split('STARTCHAR ')[1:]:
        code = int(re.search(r'ENCODING (\d+)', g)[1]); adv = int(re.search(r'DWIDTH (\d+)', g)[1])
        w, h, x, y = map(int, re.search(r'BBX ([-\d ]+)', g)[1].split())
        try:
            if jis: cp = ord(bytes([code//256+128, code % 256+128]).decode('euc_jp'))
            elif kana: cp = ord(bytes([code]).decode('shift_jis'))
            else: cp = code
        except (UnicodeError, ValueError):
            continue
        rows = [0]*height
        for yy, s in enumerate(g.split('BITMAP\n')[1].split('ENDCHAR')[0].split()):
            bits = int(s, 16); n = len(s)*4
            for xx in range(w):
                dx = x+xx; dy = ascent-y-h+yy
                if 0 <= dx < adv and 0 <= dy < height and bits & (1 << (n-1-xx)):
                    rows[dy] |= 1 << (adv-1-dx)
        out[cp] = (adv, rows)
    return out, height

def _apply_context_diff(base, diff):
    result = []; cursor = 0; i = 0
    while i < len(diff):
        m = re.match(r'\*\*\* (\d+)(?:,(\d+))? \*\*\*\*', diff[i])
        if not m: i += 1; continue
        start = int(m[1])-1; end = int(m[2] or m[1]); result.extend(base[cursor:start]); cursor = end
        i += 1
        while not re.match(r'--- \d', diff[i]): i += 1
        i += 1
        while i < len(diff) and not diff[i].startswith('***************'):
            if diff[i][:2] in ('  ', '+ ', '! '): result.append(diff[i][2:])
            i += 1
    result.extend(base[cursor:])
    return result

def load():
    _check()
    WORK.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(VENDOR/'misaki.zip') as z: z.extractall(WORK/'misaki')
    with tarfile.open(VENDOR/'mplus.tar.xz') as t: t.extractall(WORK/'mplus', filter='data')
    mp = WORK/'mplus/xfonts-mplus-2.2.4'
    mplus, h1 = parse_bdf((mp/'fonts_j/mplus_j12r.bdf').read_text(encoding='ascii', errors='replace'))
    f12, _ = parse_bdf((mp/'fonts_e/mplus_f12r.bdf').read_text(encoding='ascii', errors='replace'))
    mplus.update(f12)
    kana = _apply_context_diff((mp/'fonts_e/mplus_f12r.bdf').read_text().splitlines(),
                               (mp/'fonts_j/mplus_f12r-jisx0201.diff').read_text().splitlines())
    k, _ = parse_bdf('\n'.join(kana)+'\n'); mplus.update(k)
    misaki, h2 = parse_bdf((WORK/'misaki/misaki_gothic.bdf').read_text(encoding='ascii', errors='replace'))
    return (mplus, h1), (misaki, h2)
