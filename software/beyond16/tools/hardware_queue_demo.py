"""User-approved depth-eight SRAM bitstream, finite serial/queue demo comparison.
Stops on first failure; no command or started-demo replay. Never writes FPGA Flash.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'software/beyond16'
sys.path.insert(0,str(ROOT/'build/showcase-hardware-deps'))
from serial.tools import list_ports
args=argparse.ArgumentParser();args.add_argument('--campaign-dir',type=Path,default=ROOT/'build/queue-demo-20261107')
args.add_argument('--expected-flash-sha256',default='0298d14b33e86f470eaa8987d4654e198c9de493d981aec542aa9e03a2226c86')
args.add_argument('--queue-lettering',action='store_true');args.add_argument('--completion-burst',action='store_true');args.add_argument('--abab',action='store_true',help='Repeat identical baseline/burst firmware in A/B/A/B order');opt=args.parse_args()
assert not(opt.queue_lettering and opt.completion_burst)
assert not opt.abab or opt.completion_burst
UID='E663A837CB73512D';BASE=opt.campaign_dir.resolve();assert BASE.is_relative_to(ROOT/'build')
MATRIX=(('baseline','fw-baseline'),('burst','fw-burst')) if opt.completion_burst else (('baseline','fw-baseline'),('merged','fw-merged')) if opt.queue_lettering else (('serial','fw-serial'),('queued','fw-queue8'))
if opt.abab:MATRIX=(('baseline-1','fw-baseline'),('burst-1','fw-burst'),('baseline-2','fw-baseline'),('burst-2','fw-burst'))
OUT=BASE/'hardware';OUT.mkdir(exist_ok=False)
PICOTOOL=ROOT/'build/midnight-hardware/picotool/picotool/picotool.exe'
PROGRAMMER=Path('C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')
BIT=ROOT/'build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8/impl/pnr/kagura_fb.fs'
EXPECTED_BIT='5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77'
EXPECTED_FLASH=opt.expected_flash_sha256;assert len(EXPECTED_FLASH)==64 and all(c in '0123456789abcdef' for c in EXPECTED_FLASH)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
state=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),release_ready=False,
 authorized='User provisionally approved depth 8 and requested queued megademo hardware load validation',
 numeric_timing_gate_passed=False,worst_setup_ns=.050,fpga_flash_writes=0,fpga_sram_programs=0,
 rp2040_uid=UID,bitstream_sha256=sha(BIT),variants=[],success=False,failure=None)
state['experiment']='queue completion burst' if opt.completion_burst else 'sampled queue waits and pixel-equivalent finale lettering' if opt.queue_lettering else 'serial versus queued host'
state['run_order']=[mode for mode,_ in MATRIX]
def save():(OUT/'campaign.json').write_text(json.dumps(state,indent=2))
def run(folder,name,args,timeout=120,env=None):
 print('STAGE',folder.name,name,flush=True)
 with (folder/(name+'.log')).open('xb') as log:
  p=subprocess.run([str(x) for x in args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=env)
 assert p.returncode==0,f'{name}: exit {p.returncode}; stop without replay'
 return (folder/(name+'.log')).read_text(errors='replace')
def read_flash(folder,name,force=False):
 path=folder/(name+'.bin');assert not path.exists()
 args=[PICOTOOL,'save','-r','0x10000000','0x10200000','-v',path,'--ser',UID]
 if force:args+=['-F']
 run(folder,name,args);assert path.stat().st_size==2097152
 return path
def wait_usb():
 time.sleep(3);end=time.monotonic()+20;stable=None
 while time.monotonic()<end:
  ports=[p for p in list_ports.comports() if p.vid==0x2e8a and (p.serial_number or '').upper()==UID]
  if len(ports)==1:
   if stable is None:stable=time.monotonic()
   elif time.monotonic()-stable>1:return
  else:stable=None
  time.sleep(.25)
 raise RuntimeError('USB enumeration failed before stimulus')
try:
 assert sha(BIT)==EXPECTED_BIT
 manifest=json.loads((ROOT/'build/fb-queue-eval-packet-first-p4-r2/source-sha256.json').read_text(encoding='utf-8-sig'))
 assert all(sha(ROOT/i['path']).upper()==i['sha256'].upper() for i in manifest)
 state['firmwares']={name:dict(bin_sha256=sha(BASE/name/'beyond16.bin'),elf_sha256=sha(BASE/name/'beyond16.elf')) for _,name in MATRIX}
 for name in state['firmwares']:assert (BASE/name/'beyond16.bin').stat().st_size<0xa0000
 # Protect immutable published images and prior campaign firmware/backups.
 protected=[*ROOT.glob('artifacts/validated/*'),*R.glob('out/headroom-firmware/*/beyond16.bin')]
 protected=[p for p in protected if p.is_file()]
 state['protected']={p.relative_to(ROOT).as_posix():sha(p) for p in protected};save()
 sources=[R/'CMakeLists.txt',R/'tools/build_rp2040.ps1',ROOT/'software/kagura_fb/kagura_fb.c',ROOT/'software/kagura_fb/kagura_fb.h',*R.glob('src/*')]
 (OUT/'source-sha256.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in sources if p.is_file()},indent=2))
 first=OUT/MATRIX[0][0];first.mkdir()
 before=read_flash(first,'before',True);confirm=read_flash(first,'before-confirm')
 assert sha(before)==sha(confirm)==EXPECTED_FLASH,'Unexpected installed firmware; no write performed'
 state['original_backup']=dict(path=before.relative_to(ROOT).as_posix(),sha256=sha(before));save()
 text=run(OUT,'fpga-sram',[PROGRAMMER,'--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',BIT])
 assert '100%' in text and 'Finished.' in text and '0x1100481B' in text and 'error' not in text.lower()
 state['fpga_sram_programs']=1;save()
 expected=EXPECTED_FLASH
 for mode,fwname in MATRIX:
  folder=OUT/mode
  if mode!=MATRIX[0][0]:folder.mkdir();before=read_flash(folder,'before');confirm=read_flash(folder,'before-confirm')
  assert sha(before)==sha(confirm)==expected
  fw=BASE/fwname/'beyond16.bin';f=fw.read_bytes();erase=(len(f)+4095)&~4095
  assert sha(fw)==state['firmwares'][fwname]['bin_sha256']
  record=dict(name=mode,stage='write',success=False,firmware_sha256=sha(fw));state['variants'].append(record);save()
  (folder/'plan.json').write_text(json.dumps(dict(bitstream_sha256=sha(BIT),firmware_sha256=sha(fw),backup_sha256=sha(before),release_ready=False),indent=2))
  run(folder,'write',[PICOTOOL,'load','-v',fw,'--ser',UID])
  after=read_flash(folder,'after');a,b=before.read_bytes(),after.read_bytes()
  assert b[:len(f)]==f and b[erase:]==a[erase:] and b[0xa0000:]==a[0xa0000:]
  (folder/'flash-write-verified.json').write_text(json.dumps(dict(firmware_sha256=sha(fw),backup_sha256=sha(before),after_sha256=sha(after),filesystem_unchanged=True,tail_unchanged=True,erase_end=hex(0x10000000+erase),release_ready=False),indent=2))
  run(folder,'reboot-demo',[PICOTOOL,'reboot','--ser',UID]);wait_usb()
  record['stage']='demo';save()
  env=dict(os.environ,KAGURA_CAMPAIGN_DIR=str(folder),KAGURA_RP2040_UID=UID)
  run(folder,'runner',[sys.executable,R/'tools/hardware_run.py','demo'],timeout=320,env=env)
  result=json.loads((folder/'demo-result.json').read_text());assert result['success'] and result['failure'] is None
  usb=(folder/'demo-usb.log').read_text(errors='replace')
  assert 'QUEUE_SELFTEST commands=8 readback_bytes=32 rc=0' in usb
  if mode!='serial':
   import re
   q={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',next(line for line in usb.splitlines() if line.startswith('QUEUE depth=')))}
   assert q['peak']==8 and q['pending']==q['errors']==0 and q['submitted']==q['retired']
   record['queue']=q
  if opt.queue_lettering or opt.completion_burst:
   config=(f'CONFIG gpu_queue=8 queue_metrics=1 merged_lettering=1 completion_burst={int(mode.startswith("burst"))}') if opt.completion_burst else f'CONFIG gpu_queue=8 queue_metrics=1 merged_lettering={int(mode=="merged")}'
   assert config in usb
   for prefix,total in (('QRET ',4),('QSYNC ',8)):
    rows=[{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)} for line in usb.splitlines() if line.startswith(prefix)]
    assert len(rows)==total and all(row['samples']==(row['calls']+63)//64 for row in rows)
    record[prefix.strip()]=rows
   if opt.completion_burst:
    qb={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',next(line for line in usb.splitlines() if line.startswith('QBURST ')))}
    assert qb['hits']+qb['misses']==qb['bursts'] and qb['misses']==qb['fallback']
    assert qb['bursts']==(sum(row['calls'] for row in record['QRET']) if mode.startswith('burst') else 0)
    record['completion_burst']=qb
  run(folder,'present-analysis',[sys.executable,R/'tools/analyze_headroom_log.py',folder/'demo-usb.log','--output',folder/'present.json'])
  final=read_flash(folder,'after-tests',True);assert final.read_bytes()==after.read_bytes()
  record.update(success=True,stage='complete',full_flash_after_tests_verified=True,after_sha256=sha(final));expected=sha(final);save()
 assert all(sha(ROOT/p)==h for p,h in state['protected'].items())
 run(OUT,'final-reboot',[PICOTOOL,'reboot','--ser',UID]);wait_usb()
 state['success']=True;state['final_state']='Queue 8 SRAM FPGA and queued RP2040 firmware; PCM stopped, explicit USB start gate'
except BaseException as ex:
 state['failure']=repr(ex);print('FIRST FAILURE; STOPPED; NO REPLAY:',repr(ex),flush=True);raise
finally:
 state['finish_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
