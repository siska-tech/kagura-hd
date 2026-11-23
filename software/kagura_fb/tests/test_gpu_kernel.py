# SPDX-License-Identifier: Apache-2.0
"""Run the real GPU kernel control flow against the existing register model."""
import ast
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import BlitModel

source=Path('software/kagura_fb/rp2040_pio.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_gpu_kernel')
node.decorator_list=[]
class Clock:
 def __init__(self): self.value=0xfffffff0
 def __getitem__(self,index):
  assert index==10
  self.value=(self.value+10)&0xffffffff
  return self.value

def run(model,command,payload=b'',timeout=1000,fail_at=None):
 settings=[0]*17;clock=Clock();calls=[]
 def transaction(src,dst,c):
  calls.append((c[4],c[2]))
  if len(calls)==fail_at:return -2
  address=c[4]&63;increment=bool(c[4]&64)
  if c[6]:
   data=model.read(address,increment,c[2]-3)
   dst[:len(data)]=data
  else:model.write(address,increment,bytes(src[:c[2]-1]))
  return 0
 env={'ptr32':lambda x:clock if isinstance(x,int) else x,'ptr8':lambda x:x,
      'uint':lambda x:x&0xffffffff,'_transaction_kernel':transaction,'sleep_ms':lambda x:None}
 exec(compile(ast.Module(body=[node],type_ignores=[]),'<gpu kernel>','exec'),env)
 result=env['_gpu_kernel'](command,payload,bytearray(4),settings,timeout)
 return result,calls

m=BlitModel()
for tag in (65535,0,1):
 cmd=bytearray(16);cmd[2:4]=tag.to_bytes(2,'little')
 result,calls=run(m,cmd)
 assert result==0 and m.tag==tag and not m.completed
cmd=bytearray(16);cmd[0]=4;cmd[1]=2;cmd[4:8]=(0x3f0000).to_bytes(4,'little')
assert run(m,cmd,b'abcdefgh')[0]==0
assert m.memory[0x3f0000:0x3f0008]==b'abcdefgh'
m.force_error=9
assert run(m,bytearray(16))[0]==9 and not m.completed
m.late=True
assert run(m,bytearray(16))[0]==-4
m.late=False;m.hold=True
assert run(m,bytearray(16),timeout=100)[0]==-3
m=BlitModel();m.lost_done=True
assert run(m,bytearray(16),timeout=100)[0]==-3
class StaleTag(BlitModel):
 def read(self,address,increment,length):
  data=super().read(address,increment,length)
  if address==28 and length==3:data[0]^=1
  return data
m=StaleTag()
assert run(m,bytearray(16),timeout=100)[0]==-3 and m.completed
m=BlitModel()
assert run(m,bytearray(16),fail_at=4)[0]==-2
assert len(m.commands)==0  # failed before submit, never retried
m=BlitModel()
result,calls=run(m,bytearray(16),fail_at=6)
assert result==-2 and len(m.commands)==1  # submit may have reached FPGA
print('GPU kernel register protocol / tag wrap / payload / error ack / timeout / no retry PASS')
