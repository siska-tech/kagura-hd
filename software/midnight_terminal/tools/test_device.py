"""Actual existing C SDK descriptor -> independent repository register/pixel model.
PCM model checks orchestration, not prefetch/HDMI timing or physical audio.
"""
import sys,ctypes as C,unittest,random,json
from preview import ROOT,Engine,CALL,Backend
sys.path.insert(0,str(ROOT.parent/'kagura_fb/tests'))
from model import BlitModel
READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint8,C.c_bool,C.POINTER(C.c_uint8),C.c_size_t)
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint8,C.c_bool,C.POINTER(C.c_uint8),C.c_size_t)
NOW=C.CFUNCTYPE(C.c_uint32,C.c_void_p)
class IO(C.Structure):_fields_=[('context',C.c_void_p),('read',READ),('write',WRITE),('now',NOW)]
class Device(C.Structure):_fields_=[('io',IO),('timeout',C.c_uint32),('tag',C.c_uint16),('error',C.c_uint8),('connected',C.c_bool)]
class PCMModel(BlitModel):
 def __init__(self):
  super().__init__();self.identity=b'KFB1\x01\x04\xff';self.index=0;self.shadow={};self.active={};self.pcm=[0,0];self.snapshot={};self.commits=[]
 def write(self,a,inc,data):
  if a==54:
   self.index=data[0]
   if len(data)>1:self.write(55,False,data[1:])
   return
  if a==55:
   v=data[0];i=self.index
   if i in (0x6f,0x8f):
    ch=(i-0x6f)//32
    if v==2:self.pcm[ch]=0
    elif v==4:self.pcm[ch]&=7
    elif v==1:
     b=0x60+32*ch;addr=lambda off:sum(self.shadow.get(b+off+j,0)<<(j*8) for j in range(3));s,e,l=addr(0),addr(4),addr(8)
     self.pcm[ch]=1 if 0<=s<e<=0x3fffff and s<=l<e else 16
   else:self.shadow[i]=v
   return
  super().write(a,inc,data)
  if a==26 and self.pending[0][0]==7:self.snapshot=self.shadow.copy()
 def read(self,a,inc,n):
  if a==55:return bytes([self.pcm[(self.index-0x6f)//32] if self.index in (0x6f,0x8f) else self.shadow.get(self.index,0)])
  return super().read(a,inc,n)
 def finish(self):
  if self.pending[0][0]!=7:return super().finish()
  c,d=self.pending;self.pending=(bytes([0])+c[1:],d);super().finish();self.active=self.snapshot.copy();self.commits.append(self.active.copy())
  for ch in range(2):
   if self.active.get(0x6e+32*ch,0)&1:self.pcm[ch]|=2
class Harness:
 def __init__(self,audio=True):
  self.model=PCMModel();self.model.identity=b'KFB1\x01\x04'+bytes([255 if audio else 127]);self.lib=Engine().lib;self.errors=[];self.dev=Device();self.adapter=C.create_string_buffer(128);self.traffic={'read_bytes':0,'write_bytes':0,'transactions':0}
  def read(_,a,inc,p,n):
   self.traffic['read_bytes']+=n;self.traffic['transactions']+=1
   try:C.memmove(p,bytes(self.model.read(a,inc,n)),n);return 0
   except Exception as e:self.errors.append(repr(e));return -1
  def write(_,a,inc,p,n):
   self.traffic['write_bytes']+=n;self.traffic['transactions']+=1
   try:self.model.write(a,inc,C.string_at(p,n));return 0
   except Exception as e:self.errors.append(repr(e));return -1
  self.callbacks=(READ(read),WRITE(write),NOW(lambda _:self.model.now()));self.io=IO(None,*self.callbacks)
  self.lib.kfb_init.argtypes=[C.c_void_p,IO,C.c_uint32];self.lib.mt_device_start.argtypes=[C.c_void_p,C.c_void_p];self.lib.mt_device_emit.argtypes=[C.c_void_p,C.c_int,C.POINTER(C.c_int32),C.POINTER(C.c_uint8),C.c_uint32]
  assert self.lib.kfb_init(C.byref(self.dev),self.io,100)==0
  assert self.lib.mt_device_start(self.adapter,C.byref(self.dev))==0,self.errors
 def emit(self,op,*args):return self.lib.mt_device_emit(self.adapter,op,(C.c_int32*len(args))(*args),None,0)
class Tests(unittest.TestCase):
 def test_hardware_preflight_program(self):
  h=Harness(False);h.model.identity=b'KFB1\x01\x04\xff';h.lib.mt_preflight.argtypes=[C.c_void_p]
  self.assertEqual(h.lib.mt_preflight(C.byref(h.dev)),0,h.errors)
 def test_preflight_stops_on_first_device_error(self):
  h=Harness(False);h.model.identity=b'KFB1\x01\x04\xff';h.model.force_error=3;h.lib.mt_preflight.argtypes=[C.c_void_p];before=len(h.model.commands)
  self.assertEqual(h.lib.mt_preflight(C.byref(h.dev)),-5);self.assertEqual(len(h.model.commands)-before,1)
 def test_random_gpu_and_bounds(self):
  h=Harness(False);b=Backend();b.mem[:]=h.model.memory;rng=random.Random(904)
  # C SDK clipping and hardware model against independent packed-byte backend.
  for i in range(160):
   args=(rng.randrange(2),rng.randrange(-20,620),rng.randrange(-20,340),rng.randrange(1,48),rng.randrange(1,32),rng.randrange(16))
   self.assertEqual(h.emit(1,*args),0);b.emit(None,1,(C.c_int32*6)(*args),None,0);self.assertEqual(h.model.memory[:230400],b.mem[:230400])
  # Initial model memory is A5; align oracle initial untouched pixels explicitly.
  # Re-run after a full clear for snapshot overlap tests.
  h.emit(1,0,0,0,640,360,0);h.emit(1,1,0,0,640,360,0);b.mem[:230400]=bytes(230400)
  for i in range(128):
   x=rng.randrange(0,70)*8;y=rng.randrange(0,300);w=rng.randrange(1,30)*2;ht=rng.randrange(1,35);dx=rng.randrange(0,70)*8;dy=rng.randrange(0,300);src=rng.randrange(2);dst=rng.randrange(2)
   h.emit(1,src,x,y,w,ht,i%16);b.emit(None,1,(C.c_int32*6)(src,x,y,w,ht,i%16),None,0)
   args=(src,x,y,dst,dx,dy,w,ht);self.assertEqual(h.emit(2,*args),0);b.emit(None,2,(C.c_int32*8)(*args),None,0);self.assertEqual(h.model.memory[:230400],b.mem[:230400])
  before=len(h.model.commands)
  for args in [(0,1,0,1,0,0,2,2),(0,0,0,1,2,0,8,8),(0,0,0,1,0,0,3,8),(0,0,0,1,0,359,8,8)]:self.assertEqual(h.emit(2,*args),-1)
  self.assertEqual(before,len(h.model.commands))
  data=(C.c_uint8*5)(1,2,3,4,5);a=(C.c_int32*1)(0x3f003);self.assertEqual(h.lib.mt_device_emit(h.adapter,3,a,data,5),0);self.assertEqual(h.model.memory[0x3f002:0x3f009],b'\xa5\x01\x02\x03\x04\x05\xa5')
 def test_sdk_pixels_and_command_legality(self):
  h=Harness(False);reference=Engine();buf=C.create_string_buffer(h.lib.mt_size());cb=CALL(lambda _,op,a,p,n:h.lib.mt_device_emit(h.adapter,op,a,p,n));h.lib.mt_init(buf,cb,None,1)
  for ms in [0,3000,12000,19000,30000,33000,40000,47000,48000,49000,62000,64000,65000,72000,84000]:
   self.assertEqual(h.lib.mt_tick(buf,ms,0),0,h.errors);reference.tick(ms);b=reference.backend
   self.assertEqual(h.model.memory[:230400],b.mem[:230400],f'pixel oracle ms={ms}');self.assertEqual(h.model.active_palette,b.palette)
  self.assertFalse(h.errors);self.assertTrue(all(c[0] in range(8) for c in h.model.commands))
  (ROOT/'out/sdk-command-trace.json').write_text(json.dumps({'scope':'sparse 15 timestamps, actual C SDK descriptors / PC register model','commands_hex':[c.hex() for c in h.model.commands]}))
 def test_pcm_snapshot_preserves_bgm(self):
  h=Harness();self.assertEqual(h.emit(6,0,155),0);start={k:v for k,v in h.model.active.items() if 0x60<=k<=0x6e}
  for name,addr in [('bgm',0x80000),('select',0xde000),('talk',0xe0000),('alarm',0xe1000),('restore',0xe5000)]:
   source=(ROOT/f'generated/{name}.s8').read_bytes();self.assertEqual(h.model.memory[addr:addr+len(source)],source)
  self.assertEqual(h.emit(6,1,170),0);self.assertTrue(h.model.active[0x6e]&1);self.assertEqual(start,{k:v for k,v in h.model.active.items() if 0x60<=k<=0x6e});self.assertTrue(h.model.active[0x8e]&1)
  self.assertEqual(h.emit(6,-1,0),0);self.assertFalse(h.model.active[0x6e]&1);self.assertFalse(h.model.active[0x8e]&1);self.assertEqual(h.emit(6,0,155),0);self.assertTrue(h.model.pcm[0]&2)
 def test_fault_and_capability_fallback(self):
  h=Harness(False);self.assertEqual(h.emit(6,0,155),0);self.assertFalse(h.model.commits)
  h=Harness();self.assertEqual(h.emit(6,0,155),0);h.model.pcm[0]=8
  h.lib.mt_device_poll.argtypes=[C.c_void_p];self.assertEqual(h.lib.mt_device_poll(h.adapter),-5);self.assertEqual(h.model.pcm,[0,0])
  # Start issue is surfaced through adapter audio_error, and image commands remain usable.
  self.assertEqual(h.emit(1,0,1,1,3,3,7),0)
if __name__=='__main__':unittest.main(verbosity=2)

