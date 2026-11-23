# SPDX-License-Identifier: Apache-2.0
"""Native MicroPython memory smoke test; run with -X heapsize=192K."""
import gc
from kagura_framebuf import FrameBuffer
from kagura_ja import Font

fb = FrameBuffer(None)
with Font('software/kagura_fb/fonts/mplus12.kmf') as font:
    fb.text_jp('日本語表示 ｶｸﾞﾗ', 0, 0, font)
gc.collect()
print('192KiB heap: free bytes', gc.mem_free())
