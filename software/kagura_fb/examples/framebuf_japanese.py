# SPDX-License-Identifier: Apache-2.0
"""Copy modules and fonts/ to the board; call run(existing_device)."""
from kagura_framebuf import FrameBuffer
from kagura_ja import Font


def run(device, font_path='fonts/mplus12.kmf', page=1):
    fb = FrameBuffer(device, page=page)
    # RGB444 palette entries; committed together by show()/PRESENT.
    device.palette(0, 0x012)
    device.palette(1, 0x28b)
    device.palette(14, 0xfd6)
    device.palette(15, 0xfff)
    fb.fill(0)
    fb.rect(12, 12, 616, 336, 1)
    with Font(font_path) as font:
        fb.text_jp('KAGURA-HD / M+ BITMAP FONT', 24, 24, font, 14)
        fb.text_jp('実機基板で日本語を表示します。\nひらがな・カタカナ・漢字\n半角英数字 ABC 012 / ｶｸﾞﾗ',
                   24, 52, font, 15)
        fb.text('MicroPython framebuf', 24, 112, 1)
        fb.line(24, 132, 300, 132, 14)
        fb.show()
    return fb
