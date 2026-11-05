"""Independent pixel/sequence/UTF8/PCM oracles for native C engine, no hardware."""
import ctypes as C,json,unittest,random,wave,zlib,re
from pathlib import Path
from preview import Engine,Backend,ROOT
class Glyph(C.Structure):_fields_=[('cp',C.c_uint32),('advance',C.c_uint8),('rows',C.c_uint16*13)]
class Tests(unittest.TestCase):
 def setUp(self):self.e=Engine();self.lib=self.e.lib
 def decode(self,b):
  self.lib.mt_decode.argtypes=[C.POINTER(C.c_char_p)];self.lib.mt_decode.restype=C.c_uint32;p=C.c_char_p(b);out=[]
  while p.value:out.append(self.lib.mt_decode(C.byref(p)))
  return out
 def test_utf8(self):
  for s in ['日本語、ひらがな。カタカナ ABC ｺｰﾋｰ','\U0001f600', 'a\n雨']:
   self.assertEqual(self.decode(s.encode()),list(map(ord,s)))
  for b in [b'\x80',b'\xc0\xaf',b'\xe0\x80\x80',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe3\x81']:
   self.assertTrue(all(v==0xfffd for v in self.decode(b)))
 def test_font_and_fallback(self):
  self.lib.mt_lookup.argtypes=[C.c_uint32,C.c_int];self.lib.mt_lookup.restype=C.POINTER(Glyph)
  for c,w in [('雨',12),('A',6),('ｺ',6)]:self.assertEqual(self.lib.mt_lookup(ord(c),0).contents.advance,w)
  self.assertEqual(self.lib.mt_lookup(0x10ffff,0).contents.cp,ord('?'))
  self.assertEqual(self.lib.mt_lookup(ord('雨'),1).contents.advance,8)
  report=json.loads((ROOT/'generated/font-report.json').read_text());self.assertFalse(report['mplus']['missing']);self.assertFalse(report['misaki']['missing'])
 def test_original_bdf_baseline_oracle(self):
  self.lib.mt_lookup.argtypes=[C.c_uint32,C.c_int];self.lib.mt_lookup.restype=C.POINTER(Glyph)
  jis='雨'.encode('euc_jp');code=(jis[0]-128)*256+jis[1]-128
  for small,path,enc,height in [(0,ROOT/'vendor/mplus/xfonts-mplus-2.2.4/fonts_j/mplus_j12r.bdf',code,13),(1,ROOT/'vendor/misaki/misaki_gothic.bdf',ord('雨'),8)]:
   raw=path.read_text();block=raw.split('ENCODING '+str(enc)+'\n')[1].split('ENDCHAR')[0];w,h,x,y=map(int,re.search(r'BBX (.*)',block)[1].split());expected=set()
   for row,bits in enumerate(block.split('BITMAP\n')[1].split()):
    for col in range(w):
     if int(bits,16)&(1<<(len(bits)*4-1-col)):expected.add((x+col,height-2-y-h+row))
   g=self.lib.mt_lookup(ord('雨'),small).contents;actual={(x,y) for y in range(height) for x in range(g.advance) if g.rows[y]&(1<<(15-x))};self.assertEqual(actual,expected)
 def layout(self,s,w,small=0):
  x=(C.c_int16*128)();y=(C.c_int16*128)();cp=(C.c_uint32*128)();n=self.lib.mt_layout(s.encode(),w,small,x,y,cp,128);return [(chr(cp[i]),x[i],y[i]) for i in range(n)]
 def test_layout(self):
  rows=self.layout('雨雨、雨「雨」雨\nABC',36)
  for i,(c,x,y) in enumerate(rows):
   if x==0:self.assertNotIn(c,'、。）」')
   if c=='「':self.assertEqual(rows[i+1][2],y)
  self.assertGreater(rows[-1][2],rows[-4][2]);self.assertEqual(self.layout('A雨',16,1)[1][1],8)
 def test_nibbles_fill_blit_palette(self):
  b=Backend();A=lambda *a:(C.c_int32*len(a))(*a)
  self.assertEqual(b.emit(None,1,A(0,1,0,3,1,7),None,0),0);self.assertEqual(b.mem[:3],b'\x07\x77\x00')
  b.mem[:24]=bytes(range(24));old=bytes(b.mem);b.emit(None,2,A(0,0,0,0,8,0,32,1),None,0);self.assertEqual(b.mem[4:20],old[:16])
  b.emit(None,4,A(7,0xabc),None,0);self.assertEqual(b.palette[7],0);b.emit(None,5,A(1),None,0);self.assertEqual(b.palette[7],0xabc)
 def test_warning_sequence_oracle(self):
  # Direct expected row order, independent of overlap BLIT implementation.
  for ms in [47000,48500,53000,60000,61000]:self.e.tick(ms)
  offset=((61000-47000-5590)*8//130)%352;source=(ROOT/'generated/warning.4bpp').read_bytes()[8*320:];expected=(source*2)[offset*320:(offset+352)*320]
  b=self.e.backend;p=b.page;self.assertEqual(b.mem[p*115200+8*320:(p+1)*115200],expected)
  # Each new warning row transfer is 2560 bytes; never a full frame during steady warning.
  self.e.tick(61132);self.e.tick(61165);before=b.bytes;self.e.tick(61198);self.assertLessEqual(b.bytes-before,5120)
  self.e.tick(62000);image=self.e.backend.image();self.assertGreater(sum(v!=0 for v in image.tobytes()),100)
  self.lib.mt_lookup.argtypes=[C.c_uint32,C.c_int];self.lib.mt_lookup.restype=C.POINTER(Glyph)
  message=json.loads((ROOT/'story.json').read_text(encoding='utf-8'))['last'];expected=bytearray(640*360);left=((640-len(message)*16)//2)&~1
  for i,ch in enumerate(message):
   rows=self.lib.mt_lookup(ord(ch),1).contents.rows
   for y in range(8):
    for x in range(8):
     if rows[y]&(1<<(15-x)):
      for dy in range(2):
       for dx in range(2):expected[(172+y*2+dy)*640+left+i*16+x*2+dx]=11
  self.assertEqual(image.tobytes(),expected)
  self.e.tick(64200);self.assertEqual(set(self.e.backend.image().tobytes()),{0})
  self.e.tick(72000);self.assertGreater(len(set(self.e.backend.image().tobytes())),10)
 def test_all_choices_reset_and_clip(self):
  crcs=[]
  for keys in [[],[1],[1,1]]:
   e=Engine();e.tick(30000)
   for i,key in enumerate(keys):e.tick(30100+i*40,key)
   e.tick(31000,3);e.tick(33000);crcs.append(zlib.crc32(e.backend.image().tobytes()))
   e.tick(88000);e.tick(88100);self.assertFalse(e.backend.error)
  self.assertEqual(len(set(crcs)),3)
 def test_pcm(self):
  sizes={'bgm':384000,'select':6720,'talk':1680,'alarm':14400,'restore':11520}
  for k,n in sizes.items():
   data=(ROOT/f'generated/{k}.s8').read_bytes();self.assertEqual(len(data),n);signed=[v if v<128 else v-256 for v in data];self.assertLess(min(signed),0);self.assertGreater(max(signed),0)
   with wave.open(str(ROOT/f'generated/{k}.wav')) as w:self.assertEqual((w.getframerate(),w.getnframes(),w.getsampwidth(),w.getnchannels()),(48000,n,2,1))
  regions=[(0,115200),(115200,230400),(0x40000,0x40000+115200),(0x60000,0x60000+115200),(0x80000,0x80000+384000),(0xde000,0xde000+6720),(0xe0000,0xe0000+1680),(0xe1000,0xe1000+14400),(0xe5000,0xe5000+11520)]
  for i,(a,b) in enumerate(regions):self.assertLess(a,b);self.assertLessEqual(b,0x3fffff);self.assertTrue(all(b<=c or a>=d for c,d in regions[i+1:]))
if __name__=='__main__':unittest.main(verbosity=2)
