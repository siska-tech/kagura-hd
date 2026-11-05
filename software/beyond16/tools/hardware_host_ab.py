from pathlib import Path
import subprocess,os,hashlib,json,time,sys
r=Path.cwd();py=r/'C:/invalid';py=Path(__import__('sys').executable);base=r/'build/beyond16-host-ab-2026-11-06';base.mkdir(exist_ok=True)
cm=r/'software/midnight_terminal/.deps/cmake/data/bin/cmake.exe';tool=r/'build/midnight-hardware/picotool/picotool/picotool.exe';fw=r/'software/beyond16/out/rp2040/beyond16.bin';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def call(args):
 print('RUN',list(map(str,args)),flush=True);subprocess.run(list(map(str,args)),check=True)
os.environ['PICO_SDK_PATH']=str(r/'software/midnight_terminal/toolchain/pico-sdk')
expected='5ee9560e2406fdd4405d7d86ef69666ed6cc75433eccb50fb64c9b80e331b684'
for fast in ('OFF','ON'):
 out=base/fast;out.mkdir(exist_ok=True)
 call([cm,'-S','software/beyond16','-B','software/beyond16/out/rp2040','-DB16_HOST_FAST='+fast])
 call(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','software/beyond16/tools/build_rp2040.ps1'])
 (out/'candidate.bin').write_bytes(fw.read_bytes());(out/'candidate.elf').write_bytes((fw.parent/'beyond16.elf').read_bytes())
 env=os.environ;env['KAGURA_RP2040_UID']='E663A837CB73512D';env['KAGURA_CAMPAIGN_DIR']=str(out);env['KAGURA_FW_SHA']=sha(fw);env['KAGURA_BACKUP_SHA']=expected;env['KAGURA_LOAD_SRAM']='1' if fast=='OFF' else '0'
 if not(out/'flash-write-verified.json').exists():call([py,'software/beyond16/tools/hardware_host_deploy.py'])
 else:
  assert json.loads((out/'flash-write-verified.json').read_text())['firmware_sha256']==sha(fw)
 time.sleep(3)
 if not(out/'bench-result.json').exists():call([py,'software/beyond16/tools/hardware_run.py','bench'])
 else:assert json.loads((out/'bench-result.json').read_text())['success']
 call([tool,'reboot','-f','--ser','E663A837CB73512D']);time.sleep(3)
 call([py,'software/beyond16/tools/hardware_run.py','demo'])
 expected=json.loads((out/'flash-write-verified.json').read_text())['after_sha256']
 print('CANDIDATE COMPLETE',fast,flush=True)
