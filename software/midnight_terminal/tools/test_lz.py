import unittest,ctypes as C,random
from preview import ROOT,Engine
from pack_bgm import compress
SINK=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(C.c_uint8),C.c_uint32)
class Tests(unittest.TestCase):
 def setUp(self):
  self.lib=Engine().lib;self.lib.mt_lz_decode.argtypes=[C.c_void_p,C.c_uint32,C.c_uint32,SINK,C.c_void_p]
 def decode(self,packed,n,fail=False):
  out=bytearray();calls=[]
  def sink(_,p,size):
   calls.append(size);out.extend(C.string_at(p,size));return -2 if fail and len(calls)==2 else 0
  cb=SINK(sink);r=self.lib.mt_lz_decode(C.create_string_buffer(packed),len(packed),n,cb,None);return r,bytes(out),calls
 def test_exact_original_bgm_and_history_wrap(self):
  src=(ROOT/'generated/bgm.s8').read_bytes();r,data,calls=self.decode((ROOT/'generated/bgm.lz').read_bytes(),len(src));self.assertEqual(r,0);self.assertEqual(data,src);self.assertEqual(calls,[64]*6000)
 def test_independent_roundtrip_patterns_and_overlap(self):
  rng=random.Random(15)
  for data in [b'a'*70000,bytes(range(256))*200,bytes(rng.randrange(256) for _ in range(7000)),b'ababa'*1000,b'x']:
   self.assertEqual(self.decode(compress(data),len(data))[:2],(0,data))
  self.assertEqual(self.decode(b'\x00a\xff\x00\x00',131)[:2],(0,b'a'*131))
 def test_reject_malformed_streams(self):
  for packed,size in [(b'\x80\x00\x00',3),(b'\x80',3),(b'\x05x',6),(b'\x00x',0),(b'\x00x',2)]:self.assertEqual(self.decode(packed,size)[0],-1)
 def test_sink_error_stops_without_replay(self):
  r,data,calls=self.decode(compress(b'a'*1000),1000,True);self.assertEqual(r,-2);self.assertEqual(calls,[64,64]);self.assertEqual(len(data),128)
if __name__=='__main__':unittest.main(verbosity=2)
