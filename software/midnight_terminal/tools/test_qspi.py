"""Real C transport with SDK seam + assembled original PIO timing model.
No physical pins/devices, no software sleep-based speed claims.
"""
import ctypes as C,hashlib,importlib.util,json,random,unittest
from preview import ROOT,Engine
from test_device import IO,Device,PCMModel
HEADER=ROOT/'out/rp2040/kagura_host.pio.h'
spec=importlib.util.spec_from_file_location('original_pio_model',ROOT/'vendor/kagura_pio_timing.py');pio=importlib.util.module_from_spec(spec);spec.loader.exec_module(pio)
pio.T=1e9/60000000 # proven RP2040 120MHz / SM divider 2
REG=C.CFUNCTYPE(C.c_int,C.c_int,C.c_uint,C.c_uint)
class Stats(C.Structure):_fields_=[('transactions',C.c_uint64),('wire_bytes',C.c_uint64),('elapsed_us',C.c_uint64),('max_transaction_us',C.c_uint32),('timeouts',C.c_uint32),('faulted',C.c_bool)]
class Tests(unittest.TestCase):
 def setUp(self):
  self.lib=C.CDLL(str(ROOT/'out/qspi-tests/qspi_test.dll'));self.lib.fake_reset();self.lib.mt_qspi_io.restype=IO;self.lib.mt_qspi_statistics.restype=C.POINTER(Stats)
  self.lib.fake_write.argtypes=[C.c_uint,C.c_bool,C.c_void_p,C.c_size_t];self.lib.fake_read.argtypes=self.lib.fake_write.argtypes;self.lib.fake_callback.argtypes=[REG]
 def start(self):self.assertEqual(self.lib.mt_qspi_init(),0)
 def tearDown(self):self.lib.mt_qspi_deinit()
 def get(self,k,i=0):return self.lib.fake_get(k,i)
 def words(self):return [self.get(1,i) for i in range(self.get(0))]
 def write(self,reg,data,inc=False):return self.lib.fake_write(reg,inc,C.create_string_buffer(bytes(data)),len(data))
 def read(self,reg,n,inc=False):
  b=(C.c_uint8*n)();r=self.lib.fake_read(reg,inc,b,n);return r,bytes(b)
 def test_reused_source_and_pin_parameters(self):
  upstream=ROOT.parents[2]/'Kagura/software/pico/kagura_host.pio'
  provenance=json.loads((ROOT/'vendor/qspi-provenance.json').read_text())
  self.assertEqual(hashlib.sha256((ROOT/'vendor/kagura_host.pio').read_bytes()).hexdigest(),provenance['kagura_host.pio']['sha256'])
  if upstream.exists():self.assertEqual((ROOT/'vendor/kagura_host.pio').read_bytes(),upstream.read_bytes())
  self.start()
  self.assertEqual([self.get(k) for k in range(13,21)],[2000,2,4,2,6,1,8,0])
  for pin in range(2,8):self.assertEqual(self.get(3,pin),2);self.assertEqual(self.get(4,pin),0)
  for pin in range(2,6):self.assertEqual(self.get(5,pin),1)
  self.write(1,b'\xaa');self.assertEqual([self.get(10,i) for i in range(self.get(9))],[30,30,5,30]);self.assertEqual(self.get(6),1)
 def test_six_bit_all_registers_increment_wrap(self):
  self.start()
  for reg in range(64):self.assertEqual(self.write(reg,bytes([reg^0xa5])),0)
  self.assertEqual(self.read(0,64,True),(0,bytes(i^0xa5 for i in range(64))))
  self.assertEqual(self.write(62,b'\x11\x22\x33\x44',True),0)
  self.assertEqual(self.read(62,4,True),(0,b'\x11\x22\x33\x44'))
 def test_read_count_dummy_turnaround_and_256(self):
  self.start();self.write(55,b'\x39')
  before=len(self.words());r,data=self.read(55,256);self.assertEqual((r,data),(0,b'\x39'*256));words=self.words()[before:]
  self.assertEqual(len(words),259);self.assertEqual(words[0],0xb7<<22);self.assertEqual(words[1],1<<30);self.assertTrue(all(w==0 for w in words[2:]));self.assertEqual(self.get(7)&60,0)
  self.assertEqual(self.read(55,1),(0,b'\x39'));self.assertEqual(self.write(55,b'\x21'),0);self.assertEqual(self.read(55,1),(0,b'\x21'))
 def test_argument_reject_without_bus_activity(self):
  self.start();before=self.get(0)
  for n in [0,257]:self.assertEqual(self.lib.fake_read(0,False,(C.c_uint8*257)(),n),-1)
  self.assertEqual(self.lib.fake_read(64,False,(C.c_uint8*1)(),1),-1);self.assertEqual(self.lib.fake_write(64,False,None,0),-1);self.assertEqual(self.get(0),before)
 def test_timeout_safe_release_latched_no_retry(self):
  for mode in [1,2,3]:
   self.lib.fake_reset();self.start();self.lib.fake_mode(mode);self.assertEqual(self.write(26,b'\x01'),-3)
   stats=self.lib.mt_qspi_statistics().contents;self.assertTrue(stats.faulted);self.assertEqual(stats.timeouts,1);self.assertEqual(self.get(6),1);self.assertEqual(self.get(7)&60,0);self.assertEqual(self.get(8)&64,0)
   before=self.get(0);self.assertEqual(self.write(26,b'\x01'),-2);self.assertEqual(self.get(0),before)
 def test_wrong_clock_and_no_resource(self):
  self.lib.fake_clock(125000000);self.assertEqual(self.lib.mt_qspi_init(),-1)
  self.lib.fake_clock(120000000)
  for mode in [4,5]:self.lib.fake_mode(mode);self.assertEqual(self.lib.mt_qspi_init(),-2)
  self.lib.fake_mode(0);self.start();self.assertEqual(self.lib.mt_qspi_init(),-1)
 def test_actual_sdk_through_c_transport_to_register_oracle(self):
  self.start();model=PCMModel();errors=[]
  def callback(write,reg,value):
   try:
    if write:model.write(reg,False,bytes([value]));return 0
    return model.read(reg,False,1)[0]
   except Exception as e:errors.append(repr(e));return -1
  cb=REG(callback);self.lib.fake_callback(cb);sdk=Engine().lib;sdk.kfb_init.argtypes=[C.c_void_p,IO,C.c_uint32];dev=Device()
  self.assertEqual(sdk.kfb_init(C.byref(dev),self.lib.mt_qspi_io(),2000),0);self.assertEqual(sdk.kfb_probe(C.byref(dev)),0)
  self.assertEqual(sdk.kfb_fill_rect(C.byref(dev),0,1,2,3,4,7),0);self.assertEqual(model.memory[640:642],b'\xa7\x77')
  payload=(C.c_uint8*5)(1,2,3,4,5);sdk.kfb_write_bytes.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_size_t];sdk.kfb_read_bytes.argtypes=sdk.kfb_write_bytes.argtypes
  self.assertEqual(sdk.kfb_write_bytes(C.byref(dev),0x30003,payload,5),0);received=(C.c_uint8*5)();self.assertEqual(sdk.kfb_read_bytes(C.byref(dev),0x30003,received,5),0);self.assertEqual(bytes(received),bytes(payload))
  self.assertEqual(self.write(54,b'\x6c\x91',True),0);self.assertEqual(self.read(55,1),(0,b'\x91'));self.assertFalse(errors)
 def test_assembled_pio_5mhz_timing(self):
  rng=random.Random(94);worst_setup=1e9;smallest_hold=1e9
  for seed in range(32):
   reply=bytes(rng.randrange(256) for _ in range(7));words=[0xff<<22,(1<<30)|(7<<22)]+[0]*8
   r=pio.run(4,str(HEADER),words,reply,seed=seed);self.assertEqual(r['rx'][3:],list(reply));self.assertFalse(r['contention']);self.assertLess(r['host_rel'],r['fpga_from'])
   self.assertAlmostEqual(min(r['highs']),100,places=5);self.assertGreaterEqual(min(r['lows']),99.9);self.assertAlmostEqual(r['rises'][1]-r['rises'][0],200,places=5);worst_setup=min(worst_setup,r['host_setup']);smallest_hold=min(smallest_hold,r['fpga_from']-r['host_rel'])
  for n in [1,2,64,256]:
   reply=bytes((i*73+11)%256 for i in range(n));r=pio.run(4,str(HEADER),[0xb7<<22,(1<<30)|((n&255)<<22)]+[0]*(n+1),reply);self.assertEqual(r['rx'][3:],list(reply));self.assertFalse(r['contention'])
  (ROOT/'evidence/qspi-timing.json').write_text(json.dumps({'nominal_sck_hz':5000000,'rp2040_hz':120000000,'pio_clkdiv':2,'pio_instruction_hz':60000000,'intra_byte_period_ns':200,'min_high_ns':100,'min_low_ns':100,'min_host_setup_ns':worst_setup,'min_turnaround_margin_ns':smallest_hold,'output_delay_seeds':32,'read_lengths':[1,2,7,64,256],'scope':'assembled original PIO plus inherited delayed-output PC model, not physical HD validation','release_ready':False},indent=2))
if __name__=='__main__':unittest.main(verbosity=2)
