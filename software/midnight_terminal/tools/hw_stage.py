"""Explicit user-authorized staging: private backup, then one verified Flash write.
No erase-all, filesystem formatting, FPGA Flash write, or automatic retry.
"""
from pathlib import Path
import os
import sys,subprocess,json,time,hashlib
repo=Path(__file__).resolve().parents[3];app=repo/'software/midnight_terminal';out=repo/'build/midnight-hardware'
sys.path.insert(0,str(repo/'build/showcase-hardware-deps'));sys.path.insert(0,str(repo/'tools'))
import serial
from showcase_raw_session import RawSession
tool=out/'picotool/picotool/picotool.exe';programmer=Path('C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def command(key,args,seconds=90):
 result=subprocess.run([str(a) for a in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=seconds)
 (out/(key+'.log')).write_bytes(result.stdout);print(result.stdout.decode(errors='replace'),flush=True);assert result.returncode==0,(key,result.returncode)
 return result.stdout.decode(errors='replace')
stage=sys.argv[1];marker=out/(stage+'.started');assert not marker.exists(),'No replay '+stage
before=json.loads((out/'before.json').read_text());assert before['uid']==os.environ['KAGURA_RP2040_UID'].lower()
candidate=repo/'artifacts/validated/kagura-hd-qspi-pcm2.fs'
assert sha(candidate)=='642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7'
if stage=='backup':
 marker.write_text('one transition to ROM, then read-only full Flash backup')
 p=serial.Serial('COM7',115200,timeout=.1,write_timeout=5)
 try:
  p.write(b'\r\x03\x03\x02');time.sleep(.3);p.read(p.in_waiting);p.write(b'\x01');banner=bytearray();deadline=time.monotonic()+8
  while not banner.endswith(b'>'):
   assert time.monotonic()<deadline;banner.extend(p.read(1))
  assert b'raw REPL' in banner
  code=b"import machine\nmachine.bootloader()\n"
  p.write(code);p.write(b'\x04');assert p.read(2)==b'OK'
 finally:p.close()
 time.sleep(4)
 info=command('rom-info',[tool,'info','-a']);assert 'RP2040' in info
 command('flash-backup',[tool,'save','-r','0x10000000','0x10200000','-v',out/'recovery/current-flash-2MiB.bin'])
 backup=out/'recovery/current-flash-2MiB.bin';assert backup.stat().st_size==2097152;assert sha(backup)==before['flash_sha256']
 (out/'backup-verified.json').write_text(json.dumps({'sha256':sha(backup),'bytes':2097152,'private_backup':True,'rom_info_verified':True},indent=2));print('BACKUP VERIFIED; FLASH UNMODIFIED')
elif stage=='deploy':
 verified=json.loads((out/'backup-verified.json').read_text());assert sha(out/'recovery/current-flash-2MiB.bin')==verified['sha256']
 elf=app/'out/rp2040/midnight_terminal.elf';binary=app/'out/rp2040/midnight_terminal.bin'
 assert binary.stat().st_size<=0xa0000,'Firmware must not overlap existing KAGURA-9 filesystem'
 plan={'rp2040_flash_authorized':True,'rp2040_elf_sha256':sha(elf),'rp2040_bin_sha256':sha(binary),'fpga_sram_sha256':sha(candidate),'fpga_sram_attempts_max':1,'rp_flash_attempts_max':1,'release_ready':False,'initial_gpio_safe':before['gpio_safe'],'backup_sha256':verified['sha256'],'boot_protocol':'USB gated start, g=preflight+autoplay, q=stop','first_fault':'stop and restore original RP Flash + existing FPGA Flash Reprogram'}
 (out/'deployment-plan.json').write_text(json.dumps(plan,indent=2));marker.write_text('one user-authorized RP Flash load and one FPGA SRAM load')
 result=command('fpga-sram',[programmer,'--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',candidate],180)
 assert 'SRAM Program' in result and 'Finished.' in result and 'Error' not in result
 command('rp-flash-write',[tool,'load','-v',binary])
 command('rp-flash-readback',[tool,'save','-r','0x10000000','0x10200000',out/'recovery/after-native-flash.bin'])
 a=(out/'recovery/after-native-flash.bin').read_bytes();b=binary.read_bytes();old=(out/'recovery/current-flash-2MiB.bin').read_bytes();assert a[:len(b)]==b,'firmware binary readback'
 sector_end=(len(b)+4095)//4096*4096;assert a[sector_end:]==old[sector_end:],'Unexpected write outside firmware sectors'
 assert a[0xa0000:]==old[0xa0000:],'Existing filesystem changed'
 (out/'flash-write-verified.json').write_text(json.dumps({'native_bin_sha256':sha(binary),'full_flash_sha256':hashlib.sha256(a).hexdigest(),'firmware_bytes':len(b),'erased_sectors_end':hex(0x10000000+sector_end),'tail_beyond_sectors_unchanged':True,'filesystem_start':'0x100A0000','filesystem_unchanged':True,'release_ready':False},indent=2))
 command('rp-native-reboot',[tool,'reboot']);print('FLASH VERIFIED AND REBOOTED; waiting for USB g command')
else:raise ValueError(stage)
