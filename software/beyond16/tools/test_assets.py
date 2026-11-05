from pathlib import Path
import sys,ctypes as C,unittest,json
from preview import R,Engine
class Tests(unittest.TestCase):
 def test_signed_pcm_lossless_psram(self):
  e=Engine();ptr=C.addressof(e.lib.pc_memory().contents)
  self.assertEqual(C.string_at(ptr+0x80000,384000),(R/'generated/bgm.s8').read_bytes())
  self.assertEqual(C.string_at(ptr,115200),(R/'generated/frame.4bpp').read_bytes())
  self.assertEqual(C.string_at(ptr+115200,115200),(R/'generated/frame.4bpp').read_bytes())
  for i in range(4):
   fx=(R/'generated'/f'fx{i}.s8').read_bytes();self.assertEqual(C.string_at(ptr+0xe0000+i*16384,len(fx)),fx)
 def test_seed_reproduction(self):
  hashes=[]
  import zlib
  for seed in (0xb1616,0xb1616,123):
   e=Engine(seed=seed);e.tick(12345);hashes.append(zlib.crc32(e.memory()))
  self.assertEqual(hashes[0],hashes[1]);self.assertNotEqual(hashes[0],hashes[2])
 def test_wall_clock_skip_and_end(self):
  e=Engine();e.tick(0);e.tick(130000);self.assertEqual(e.lib.pc_stats().contents.scene,6);self.assertGreater(e.lib.pc_stats().contents.skipped,3000);c=e.counts();e.tick(150000);self.assertEqual(c,e.counts())
 def test_palette_limit(self):
  for p in (R/'evidence').glob('0*.png'):
   from PIL import Image
   im=Image.open(p);self.assertEqual(im.mode,'P');self.assertLessEqual(max(im.getdata()),15);self.assertEqual(im.size,(640,360))
if __name__=='__main__':unittest.main(verbosity=2)
