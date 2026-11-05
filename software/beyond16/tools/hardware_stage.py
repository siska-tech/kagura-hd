from pathlib import Path
import os
import sys,hashlib,json,subprocess,time,datetime
repo=Path(__file__).resolve().parents[3];out=repo/'build/beyond16-hardware-2026-11-06';app=repo/'software/beyond16';sys.path.insert(0,str(repo/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tool=repo/'build/midnight-hardware/picotool/picotool/picotool.exe'
programmer=Path('C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')
bit=repo/'artifacts/validated/kagura-hd-qspi-pcm2.fs'
assert sha(bit)=='642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7'
meta=json.loads((app/'evidence/rp2040-build.json').read_text());binary=app/'out/rp2040/beyond16.bin';assert sha(binary)==meta['bin_sha256'];assert meta['bin_sha256']=='c66308e09ad46a2104d3924d0a7913b98937b05e7408ade4b523940a6cee200b';assert (binary.stat().st_size+4095)//4096*4096<=0xa0000
for p,h in json.loads((app/'evidence/source-sha256.json').read_text()).items():assert sha(repo/p)==h,p

def run(name,args,timeout=120):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout);(out/(name+'.log')).write_bytes(r.stdout)
 print(name,r.returncode,r.stdout.decode(errors='replace')[-1000:],flush=True);assert r.returncode==0,(name,r.returncode);return r.stdout
stage=sys.argv[1];marker=out/(stage+'.started');assert not marker.exists(),'Stage already attempted; inspect logs, never automatically replay'
if stage=='backup':
 ports=[p for p in list_ports.comports() if p.vid==0x2e8a and p.serial_number.upper()==os.environ['KAGURA_RP2040_UID'].upper()];assert len(ports)==1
 marker.write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
 ff=(repo/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip()
 run('before-capture',[ff,'-hide_banner','-y','-f','dshow','-rtbufsize','256M','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)','-t','3','-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','pcm_s16le',out/'before.mkv'],30)
 with serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=5) as p:
  p.write(b'q');raw=bytearray();deadline=time.monotonic()+20
  while b'STOP error=' not in raw:
   assert time.monotonic()<deadline,'previous demo safe-stop not confirmed';raw.extend(p.read(8192))
  (out/'stop-previous.log').write_bytes(raw);assert b'STOP error=0' in raw,raw[-1000:]
 run('flash-backup',[tool,'save','-r','0x10000000','0x10200000','-v',out/'recovery/before-beyond16-full-2MiB.bin','-F','--ser',os.environ['KAGURA_RP2040_UID'].upper()])
 backup=out/'recovery/before-beyond16-full-2MiB.bin';assert backup.stat().st_size==2097152;assert sha(backup)=='7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596','Unexpected current Flash; STOP'
 info=run('rom-info',[tool,'info','-a']);assert b'RP2040' in info and bos.environ['KAGURA_RP2040_UID'].upper() in info
 (out/'backup-verified.json').write_text(json.dumps({'bytes':2097152,'sha256':sha(backup),'picotool_verify':True,'uid':os.environ['KAGURA_RP2040_UID'].lower(),'restore_target':'this immediate pre-campaign native MIDNIGHT TERMINAL image','flash_written':False,'release_ready':False},indent=2));print('NEW BACKUP VERIFIED; device idle in ROM; Flash unchanged',flush=True)
elif stage=='backup-read':
 assert b'STOP error=0' in (out/'stop-previous.log').read_bytes()
 assert not (out/'recovery/before-beyond16-full-2MiB.bin').exists()
 marker.write_text('Resume backup after CLI argument parsing failure, no previous device transfer')
 run('flash-backup-corrected',[tool,'save','-r','0x10000000','0x10200000','-v',out/'recovery/before-beyond16-full-2MiB.bin','-F','--ser',os.environ['KAGURA_RP2040_UID'].upper()])
 backup=out/'recovery/before-beyond16-full-2MiB.bin';assert backup.stat().st_size==2097152;assert sha(backup)=='7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596','Unexpected current Flash; STOP'
 info=run('rom-info',[tool,'info','-a']);assert b'RP2040' in info and bos.environ['KAGURA_RP2040_UID'].upper() in info
 (out/'backup-verified.json').write_text(json.dumps({'bytes':2097152,'sha256':sha(backup),'picotool_verify':True,'uid':os.environ['KAGURA_RP2040_UID'].lower(),'restore_target':'immediate pre-campaign MIDNIGHT TERMINAL image','flash_written':False,'release_ready':False},indent=2));print('NEW BACKUP VERIFIED; device idle in ROM; Flash unchanged',flush=True)
elif stage=='deploy':
 backup=out/'recovery/before-beyond16-full-2MiB.bin';verified=json.loads((out/'backup-verified.json').read_text());assert sha(backup)==verified['sha256']
 plan={'user_authorization':'実機にいきましょう','restore_target_sha256':sha(backup),'binary_sha256':sha(binary),'elf_sha256':meta['elf_sha256'],'bitstream_sha256':sha(bit),'bin_bytes':binary.stat().st_size,'erase_end':'0x1004e000','filesystem_start':'0x100a0000','fpga_flash_write':False,'release_ready':False}
 (out/'deployment-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2));marker.write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
 result=run('fpga-sram',[programmer,'--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',bit],180)
 assert b'SRAM Program' in result and b'Finished.' in result and b'Error' not in result
 run('rp-flash-write',[tool,'load','-v',binary]);run('rp-flash-readback',[tool,'save','-r','0x10000000','0x10200000',out/'recovery/after-beyond16-full-2MiB.bin'])
 old=backup.read_bytes();new=(out/'recovery/after-beyond16-full-2MiB.bin').read_bytes();fw=binary.read_bytes();end=(len(fw)+4095)//4096*4096
 assert len(new)==2097152 and new[:len(fw)]==fw;assert new[end:]==old[end:],'write outside firmware erase sectors';assert new[0xa0000:]==old[0xa0000:],'filesystem changed'
 (out/'flash-write-verified.json').write_text(json.dumps({'firmware_bytes':len(fw),'firmware_sha256':sha(binary),'full_flash_sha256':hashlib.sha256(new).hexdigest(),'erase_end':hex(0x10000000+end),'tail_unchanged':True,'filesystem_unchanged':True,'fpga_flash_written':False,'release_ready':False},indent=2));run('rp-reboot',[tool,'reboot']);print('DEPLOY VERIFIED, USB command gate waiting',flush=True)
else:raise ValueError(stage)
