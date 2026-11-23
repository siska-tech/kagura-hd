#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the HD M+ 12px font from the pinned upstream 2.2.4 source archive.

python tools/gen-mplus-font.py build/mplus-font/mplus.tar.xz \
    software/kagura_fb/fonts/mplus12.kmf [--check]

Source mirror: https://deb.debian.org/debian/pool/main/x/xfonts-mplus/
No extraction, external packages or network access needed by this converter.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import tarfile
import re

SHA256 = '4c973ef85e3e17cb3894a6193b85256ca75aab94d01919175d308a76fa420b94'
ROOT = 'xfonts-mplus-2.2.4/'
HEIGHT, ASCENT, ROW_BYTES = 13, 11, 2


def apply_context_diff(text, patch):
    """Apply the upstream JIS X 0201 context diff without a system patch tool."""
    source, output, cursor = text.splitlines(), [], 0
    lines = patch.splitlines()
    index = 0
    while index < len(lines):
        match = re.fullmatch(r'\*\*\* (\d+)(?:,(\d+))? \*\*\*\*', lines[index])
        if match is None:
            index += 1
            continue
        start = int(match[1]) - 1
        index += 1
        old = []
        while not re.fullmatch(r'--- \d+(?:,\d+)? ----', lines[index]):
            old.append(lines[index][2:])
            index += 1
        index += 1
        new = []
        while index < len(lines) and lines[index] != '***************':
            new.append(lines[index][2:])
            index += 1
        if source[start:start + len(old)] != old or start < cursor:
            raise ValueError('upstream context diff does not match')
        output.extend(source[cursor:start])
        output.extend(new)
        cursor = start + len(old)
    return '\n'.join(output + source[cursor:])


def parse_bdf(text, japanese=False, halfwidth=False, height=HEIGHT, ascent=ASCENT):
    glyphs = {}
    lines = iter(text.splitlines())
    for line in lines:
        if not line.startswith('STARTCHAR '):
            continue
        code = width = box = None
        for line in lines:
            fields = line.split()
            if fields[0] == 'ENCODING':
                code = int(fields[1])
            elif fields[0] == 'DWIDTH':
                width = int(fields[1])
            elif fields[0] == 'BBX':
                box = tuple(map(int, fields[1:]))
            elif fields[0] == 'BITMAP':
                break
        if code is None or width is None or box is None:
            raise ValueError('incomplete BDF glyph')
        w, h, dx, dy = box
        raw = [next(lines) for _ in range(h)]
        if next(lines) != 'ENDCHAR':
            raise ValueError('unterminated BDF glyph')
        if code < 0:
            continue
        if japanese:
            try:
                char = (b'\x1b$B' + bytes((code >> 8, code & 255)) + b'\x1b(B').decode('iso2022_jp')
            except UnicodeError:
                continue
            code = ord(char)
        elif halfwidth:
            if not (0 <= code < 128 or 161 <= code <= 223):
                continue
            code = ord(bytes((code,)).decode('shift_jis'))
        top = ascent - dy - h
        if not 1 <= width <= 16 or dx < 0 or dx + w > width or top < 0 or top + h > height:
            raise ValueError('glyph outside output cell: U+%04X' % code)
        bitmap = bytearray(height * ROW_BYTES)
        for row, value in enumerate(raw):
            # BDF scanlines are padded to a byte, with the left pixel at bit 7.
            bits = int(value, 16) >> (((w + 7) // 8) * 8 - w)
            bits <<= 16 - w - dx
            struct.pack_into('>H', bitmap, (top + row) * ROW_BYTES, bits)
        if code in glyphs:
            raise ValueError('duplicate Unicode mapping')
        glyphs[code] = (width, bytes(bitmap))
    return glyphs


def convert(path, size=12):
    if size not in (10, 12):
        raise ValueError('size must be 10 or 12')
    height, ascent = (13, 11) if size == 12 else (11, 9)
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('M+ source archive SHA-256 mismatch')
    with tarfile.open(path) as archive:
        def read(name):
            return archive.extractfile(ROOT + name).read().decode('ascii')
        glyphs = parse_bdf(read('fonts_j/mplus_j%dr.bdf' % size), True, height=height, ascent=ascent)
        latin = read('fonts_e/mplus_f12r.bdf') if size == 12 else apply_context_diff(
            read('fonts_j/mplus_j10r-iso-W4'), read('fonts_j/mplus_j10r-iso-W5.diff'))
        glyphs.update(parse_bdf(latin, height=height, ascent=ascent))
        jis0201 = apply_context_diff(latin, read('fonts_j/mplus_f12r-jisx0201.diff' if size == 12 else 'fonts_j/mplus_j10r-jisx0201.diff'))
        glyphs.update(parse_bdf(jis0201, halfwidth=True, height=height, ascent=ascent))
    out = bytearray(struct.pack('<4sBBH', b'KMF1', height, ROW_BYTES, len(glyphs)))
    for code, (width, bitmap) in sorted(glyphs.items()):
        out += struct.pack('<IB', code, width) + bitmap
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--size', type=int, choices=(10, 12), default=12)
    args = parser.parse_args()
    data = convert(args.archive, args.size)
    if args.check:
        if args.output.read_bytes() != data:
            raise SystemExit('generated font differs')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    print('%s: %d glyphs, %d bytes' % (args.output, struct.unpack_from('<H', data, 6)[0], len(data)))


if __name__ == '__main__':
    main()
