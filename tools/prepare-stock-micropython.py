"""Stage official same-version Pico FW and a firmware-only exact restore.
NO USB, serial or flash operations. Existing private full backup stays immutable.
"""
from pathlib import Path
import hashlib,json,struct,urllib.request
r=Path(__file__).resolve().parents[1];out=r/'build/showcase-stock-fw-2026-11-05-v1'
assert not out.exists();out.mkdir();(out/'private').mkdir()
sha=lambda data:hashlib.sha256(data).hexdigest()
backup=r/'build/hardware-eval-097/recovery/current-flash-2MiB.bin';original=backup.read_bytes()
assert len(original)==2097152 and sha(original)=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
url='https://micropython.org/resources/firmware/RPI_PICO-20250809-v1.26.0.uf2'
data=urllib.request.urlopen(url,timeout=30).read();assert len(data)%512==0
(out/'RPI_PICO-20250809-v1.26.0.uf2').write_bytes(data)
blocks=[];sectors=set();fsbase=640*1024
for i in range(0,len(data),512):
 block=data[i:i+512];a,b,flags,address,n,index,count,family=struct.unpack_from('<8I',block)
 assert (a,b,struct.unpack_from('<I',block,508)[0])==(0x0a324655,0x9e5d5157,0x0ab16f30)
 assert flags&0x2000 and not flags&1 and family==0xe48bff56 and n==256
 offset=address-0x10000000;assert 0<=offset and offset+n<=fsbase,'official FW overlaps saved filesystem'
 blocks.append((offset,block[32:32+n]));sectors.add(offset//4096)
expected=bytearray(original)
for sector in sectors:expected[sector*4096:(sector+1)*4096]=b'\xff'*4096
for offset,payload in blocks:expected[offset:offset+len(payload)]=payload
assert expected[fsbase:]==original[fsbase:]
(out/'private/expected-stock-full-flash.bin').write_bytes(expected)
restore=bytearray();count=fsbase//256
for i in range(count):
 block=bytearray(512);struct.pack_into('<8I',block,0,0x0a324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
 block[32:288]=original[i*256:(i+1)*256];struct.pack_into('<I',block,508,0x0ab16f30);restore.extend(block)
(out/'private/restore-original-firmware-only.uf2').write_bytes(restore)
plan={'official_url':url,'version':'1.26.0','board':'RPI_PICO RP2040 2MiB (must confirm actual machine before write)',
 'stock_uf2_sha256':sha(data),'uf2_payload_blocks':len(blocks),'touched_sectors':sorted(sectors),
 'filesystem_start':fsbase,'filesystem_bytes':len(original)-fsbase,'filesystem_sha256':sha(original[fsbase:]),
 'old_full_flash_sha256':sha(original),'expected_stock_full_flash_sha256':sha(expected),
 'restore_fw_only_sha256':sha(restore),'restore_writes_filesystem':False,
 'rp2040_fw_write_authorized_by_user':True,'fpga_flash_write_allowed':False,'filesystem_changes_allowed':False,
 'stock_write_attempts_max':1,'original_restore_attempts_max':1,'hardware_actions_performed':False,'release_ready':False}
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
fs=r/'build/hardware-eval-097/recovery/current-flash-2MiB.bin'
proof='''import vfs,os,hashlib,binascii,re
class ReadOnlyFlash:
 def __init__(self):self.f=open(__FLASH_BACKUP_PATH__,'rb')
 def readblocks(self,block,buffer,offset=0):
  self.f.seek(655360+block*4096+offset);self.f.readinto(buffer)
 def writeblocks(self,*args):raise OSError('read-only backup')
 def ioctl(self,op,arg):
  if op==4:return 352
  if op==5:return 4096
  if op==6:raise OSError('erase prohibited')
  return 0
disk=ReadOnlyFlash();fs=vfs.VfsLfs2(disk,progsize=256);vfs.mount(fs,'/saved',readonly=True)
with open('/saved/boot.py','rb') as f:data=f.read()
h=hashlib.sha256(data);digest=binascii.hexlify(h.digest()).decode()
assert digest=='9ef26228ee5039efa193938d4d11cc036d4b2589289250719f484647716b62b0'
text=data.decode();imports=[]
for line in text.splitlines():
 match=re.match(r'\\s*(?:import|from)\\s+([A-Za-z0-9_.]+)',line)
 if match:imports.append(match.group(1))
present=[]
for path in ('/saved/kagura','/saved/lib/kagura'):
 try:os.stat(path);present.append(path)
 except OSError:pass
print('PASS: saved LittleFS mounted READ ONLY, no mkfs/write operations')
print('BOOT_SHA256',digest,'BOOT_IMPORT_MODULES',imports,'FILESYSTEM_KAGURA_PATHS',present)
'''.replace('__FLASH_BACKUP_PATH__',repr(str(fs).replace('C:\\','/mnt/c/').replace('\\','/')))
# The offline proof runs under WSL with a POSIX path.
proof=proof.replace(repr(str(fs)),repr('/mnt/c/'+str(fs)[3:].replace('\\','/')))
(out/'filesystem-readonly-proof.py').write_text(proof)
print(json.dumps(plan,indent=2))
