"""Independent repository packed-pixel model versus the actual C SDK and native preview.
No timing equivalence to RTL, PSRAM or PCM prefetch is asserted.
"""
import sys,ctypes as C,json,unittest,time,statistics,zlib
from preview import R,Engine,run
sys.path.insert(0,str(R.parent/'kagura_fb/tests'))
from model import BlitModel
READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint8,C.c_bool,C.POINTER(C.c_uint8),C.c_size_t)
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint8,C.c_bool,C.POINTER(C.c_uint8),C.c_size_t)
NOW=C.CFUNCTYPE(C.c_uint32,C.c_void_p)
class IO(C.Structure):_fields_=[('context',C.c_void_p),('read',READ),('write',WRITE),('now',NOW)]
class Device(C.Structure):_fields_=[('io',IO),('timeout',C.c_uint32),('tag',C.c_uint16),('error',C.c_uint8),('connected',C.c_bool)]
class PCM(BlitModel):
 def __init__(self):
  super().__init__();self.memory[:]=bytes(len(self.memory));self.identity=b'KFB1\x01\x04\xff';self.index=0;self.shadow={};self.active={};self.pcm=[0,0];self.snap={}
 def write(self,a,inc,data):
  if a==54:
   self.index=data[0]
   if len(data)>1:self.write(55,False,data[1:])
   return
  if a==55:
   i=self.index;v=data[0]
   if i in (0x6f,0x8f):
    ch=(i-0x6f)//32;b=0x60+ch*32
    if v==2:self.pcm[ch]=0
    elif v==4:self.pcm[ch]&=7
    elif v==1:
     value=lambda off:sum(self.shadow.get(b+off+j,0)<<(8*j) for j in range(3));s,e,l=value(0),value(4),value(8);self.pcm[ch]=1 if 0<=s<e<=0x3fffff and s<=l<e else 16
   else:self.shadow[i]=v
   return
  super().write(a,inc,data)
  if a==26 and self.pending[0][0]==7:self.snap=self.shadow.copy()
 def read(self,a,inc,n):
  if a==55:return bytes([self.pcm[(self.index-0x6f)//32] if self.index in (0x6f,0x8f) else self.shadow.get(self.index,0)])
  return super().read(a,inc,n)
 def finish(self):
  if self.pending[0][0]!=7:return super().finish()
  c,d=self.pending;self.pending=(bytes([0])+c[1:],d);super().finish();self.active=self.snap.copy()
  for ch in range(2):
   if self.active.get(0x6e+32*ch,0)&1:self.pcm[ch]|=2
class Harness:
 def __init__(self,variant):
  self.model=PCM();self.lib=C.CDLL(str(R/'out'/(f'{variant}.dll' if sys.platform=='win32' else f'lib{variant}.so')));self.errors=[];self.dev=Device();self.engine=C.create_string_buffer(8192)
  def read(_,a,inc,p,n):
   try:C.memmove(p,bytes(self.model.read(a,inc,n)),n);return 0
   except Exception as ex:self.errors.append(str(ex));return -1
  def write(_,a,inc,p,n):
   try:self.model.write(a,inc,C.string_at(p,n));return 0
   except Exception as ex:self.errors.append(str(ex));return -1
  self.callbacks=READ(read),WRITE(write),NOW(lambda _:self.model.now());self.io=IO(None,*self.callbacks);self.lib.kfb_init.argtypes=[C.c_void_p,IO,C.c_uint32];self.lib.b16_init.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];self.lib.b16_tick.argtypes=[C.c_void_p,C.c_uint32]
  assert self.lib.kfb_init(C.byref(self.dev),self.io,100)==0
  assert self.lib.b16_init(self.engine,C.byref(self.dev),0xB1616)==0,self.errors
class Tests(unittest.TestCase):
 def test_independent_pixel_oracle(self):
  results=[]
  for variant in ('baseline','optimized'):
   h=Harness(variant);native=Engine(variant);self.assertEqual(bytes(h.model.memory[:230400]),native.memory())
   for ms in [0,1000,10000,11111,30000,33333,50000,55555,70000,78888,95000,101111,120000,127777,134444,138888,139999,140000,145555,149999]:
    self.assertEqual(h.lib.b16_tick(h.engine,ms),0,h.errors);native.tick(ms);self.assertEqual(bytes(h.model.memory[:230400]),native.memory(),f'{variant} {ms}');self.assertEqual(h.model.active_palette,list(native.lib.pc_palette()[:16]));self.assertEqual(h.model.page,native.lib.pc_page())
    self.assertEqual(h.model.active.get(0x6e),3,'PCM1 COMMIT lost BGM enable/loop');self.assertEqual(h.model.pcm[0]&0x38,0)
   self.assertFalse(h.errors);self.assertTrue(all(c[0] in range(8) for c in h.model.commands));results.append({'variant':variant,'commands':len(h.model.commands),'timestamps':20,'pixel_oracle':'PASS'})
   if variant=='optimized':(R/'evidence/oracle-command-trace.jsonl').write_text('\n'.join(json.dumps({'descriptor':c.hex()}) for c in h.model.commands))
  (R/'evidence/oracle.json').write_text(json.dumps(results,indent=2))
 def test_fault_stop_no_retry(self):
  rows=[]
  for mode in (1,2,3,4):
   e=Engine();e.lib.pc_fault(mode);r=e.lib.pc_tick(0);self.assertNotEqual(r,0);c=e.counts();self.assertEqual(e.lib.pc_tick(1000),r);self.assertEqual(c,e.counts());rows.append({'fault':mode,'return':r,'stopped_without_retry':True})
  (R/'evidence/fault-tests.json').write_text(json.dumps(rows,indent=2))
 def test_sdk_timeout_tag_wrap_and_bounds(self):
  h=Harness('optimized');l=h.lib;l.kfb_copy_rect.argtypes=[C.c_void_p]+[C.c_int32]*8;l.kfb_fill_rect.argtypes=[C.c_void_p]+[C.c_int32]*6
  for args in [(0,1,0,1,0,0,2,2),(0,0,0,1,2,0,8,8),(0,0,0,1,0,0,3,8),(0,0,0,1,0,359,8,8)]:self.assertEqual(l.kfb_copy_rect(C.byref(h.dev),*args),-1)
  h.dev.tag=65535;self.assertEqual(l.kfb_fence(C.byref(h.dev)),0);self.assertEqual(l.kfb_fence(C.byref(h.dev)),0);self.assertEqual(h.dev.tag,1)
  h.model.lost_done=True;self.assertEqual(l.kfb_fence(C.byref(h.dev)),-3)
 def test_full_autoplay_equivalence(self):
  a=run('baseline');b=run('optimized');self.assertEqual(a['frame_crc32'],b['frame_crc32']);self.assertLess(b['runtime_counts'][0],a['runtime_counts'][0]);self.assertEqual(a['runtime_counts'][2],b['runtime_counts'][2]);self.assertEqual(a['runtime_counts'][5],0);self.assertEqual(b['runtime_counts'][5],0)
  (R/'evidence/before-after.json').write_text(json.dumps({'conditions':'same C scene functions, seed 0xB1616, 33ms logical schedule, 3 status polls per model command; baseline uncached and original SDK; optimized CAPS cache and packed descriptor','baseline':a['runtime_counts'],'optimized':b['runtime_counts'],'transaction_reduction_percent':100*(1-b['runtime_counts'][0]/a['runtime_counts'][0]),'pixel_crc_equal':True,'physical_speedup':None},indent=2))
if __name__=='__main__':unittest.main(verbosity=2)
