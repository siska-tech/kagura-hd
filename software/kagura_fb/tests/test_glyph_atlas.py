# SPDX-License-Identifier: Apache-2.0
from model import BlitModel
from kagura_fb import Device
from kagura_framebuf import FrameBuffer
from kagura_ja import Font
from kagura_glyph_atlas import GlyphAtlas
from kagura_terminal import Terminal
from kagura_console import Console

model = BlitModel()
dev = Device(model, now_ms=model.now)
fb = FrameBuffer(dev)
with Font('software/kagura_fb/fonts/mplus12.kmf') as font:
    atlas = GlyphAtlas(dev, font)
    while not atlas.ready:
        atlas.prewarm_step()
    assert atlas.uploaded_bytes == 19 * 13 * 320
    assert len(atlas._map) == 380
    assert atlas.advance('A') == 6 and atlas.advance('日') == 12
    dev.fill_rect(0, 0, 0, 640, 360, 3)
    fb.fill(3)
    uploaded = atlas.uploaded_bytes
    for index, phase in enumerate((0, 2, 4, 6)):
        font.draw(fb, 'A', 16 + phase, index * 13, 15, 0)
        assert atlas.draw('A', 16 + phase, index * 13, 6)
    assert atlas.hits == 4 and atlas.misses == 0
    assert atlas.uploaded_bytes == uploaded
    for index, ch in enumerate('日本語'):
        x = 12 + index * 12
        font.draw(fb, ch, x, 65, 15, 0)
        assert atlas.draw(ch, x, 65, 12)
    assert model.memory[:115200] == fb.buffer
    count, uploaded = len(model.commands), atlas.uploaded_bytes
    assert atlas.draw('日', 12, 65, 12)
    assert len(model.commands) == count + 1
    assert atlas.uploaded_bytes == uploaded
    assert not atlas.draw('A', 1, 0, 6)
    assert not atlas.draw('A', 0, 0, 5)
    dev.fill_rect(0, 0, 0, 640, 360, 0)
    terminal = Terminal(fb, font, atlas=atlas)
    terminal.feed('AB日'.encode())
    terminal.flush()
    reference = FrameBuffer(None)
    font.draw(reference, 'AB日', 0, 0, 15, 0)
    assert model.memory[:115200] == reference.buffer
    assert fb.buffer == bytearray(115200)  # cached glyphs are not rasterized on Pico
    terminal.feed(b'\x1b[2J')
    assert model.memory[:115200] == bytearray(115200)
    terminal.feed('AB日'.encode())
    terminal.flush()
    reference.fill(0)
    font.draw(reference, 'AB日', 24, 0, 15, 0)
    console = Console(dev, fb, font, atlas=atlas)
    console.pause()
    assert fb.buffer == reference.buffer  # application handoff snapshots actual GPU pixels
    atlas.reset()
    assert not atlas.ready and not atlas._map
print('glyph atlas phases / Japanese cache / BLIT-only hits / reset PASS')
