import ctypes as C,json
from pathlib import Path
R=Path('software/beyond16');results=[]
for fast in (0,1):
 l=C.CDLL(str((R/f'out/host-tests/host{fast}.dll').resolve()));l.fake_write.argtypes=[C.c_uint,C.c_bool,C.c_void_p,C.c_size_t];l.fake_read.argtypes=l.fake_write.argtypes
 l.fake_reset();assert l.mt_qspi_init()==0
 for n in (1,2,4,8,16,64,512):
  a=(C.c_uint8*n)(*[i%256 for i in range(n)]);assert l.fake_write(24,False,a,n)==0
 a=(C.c_uint8*1)(57);assert l.fake_write(55,False,a,1)==0
 for n in (1,2,4,8,16,64,256):
  b=(C.c_uint8*n)();assert l.fake_read(55,False,b,n)==0;assert bytes(b)==bytes([57])*n
 assert [l.fake_get(10,i) for i in range(4)]==[30,30,5,30]
 for mode in (1,2,3):
  l.fake_reset();assert l.mt_qspi_init()==0;l.fake_mode(mode);assert l.fake_write(26,False,a,1)==-3
  assert l.fake_get(6,0)==1 and l.fake_get(7,0)&60==0
  before=l.fake_get(0,0);assert l.fake_write(26,False,a,1)==-2;assert before==l.fake_get(0,0)
 l.fake_reset();l.fake_clock(125000000);assert l.mt_qspi_init()==-1
 results.append({'fast':fast,'lengths_and_data':'PASS','wait_cycles':'PASS','three_fault_modes_no_retry':'PASS','wrong_clock':'PASS'})
(R/'evidence/host-fixed-cost-tests.json').write_text(json.dumps(results,indent=2));print(results)
