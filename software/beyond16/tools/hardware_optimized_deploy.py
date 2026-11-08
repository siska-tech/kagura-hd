from pathlib import Path
import subprocess,hashlib,json,datetime
repo=Path.cwd();out=repo/'build/beyond16-hardware-optimized-2026-11-06';out.mkdir(exist_ok=True);(out/'recovery').mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tool=repo/'build/midnight-hardware/picotool/picotool/picotool.exe';fw=repo/'software/beyond16/out/rp2040/beyond16.bin';bit=repo/'artifacts/validated/kagura-hd-qspi-pcm2.fs'
assert sha(fw)=='9102def69ab613f53587d2426ec1b08f6105484f2850d427372ea5acae62a574'
assert sha(bit)=='642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7'
assert not(out/'deploy.started').exists();(out/'deploy.started').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
def run(name,args):
 p=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120);(out/(name+'.log')).write_bytes(p.stdout);print(name,p.returncode,p.stdout.decode(errors='replace')[-500:],flush=True);assert p.returncode==0;return p.stdout
backup=out/'recovery/before.bin';run('backup',[tool,'save','-r','0x10000000','0x10200000','-v',backup,'-F','--ser','E663A837CB73512D']);assert backup.stat().st_size==2097152
assert sha(backup)=='29001ff651a227cf2d4d8b2286c4dbc67af385ede3d205e1f124518b4295aa4a','unexpected current Flash; stop before write'
(out/'plan.json').write_text(json.dumps({'backup_sha256':sha(backup),'firmware_sha256':sha(fw),'bitstream_sha256':sha(bit),'release_ready':False},indent=2))
run('fpga-sram',['C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe','--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',bit])
run('write',[tool,'load','-v',fw]);after=out/'recovery/after.bin';run('readback',[tool,'save','-r','0x10000000','0x10200000',after]);a=backup.read_bytes();b=after.read_bytes();f=fw.read_bytes();end=(len(f)+4095)//4096*4096
assert b[:len(f)]==f and b[end:]==a[end:] and b[0xa0000:]==a[0xa0000:]
(out/'flash-write-verified.json').write_text(json.dumps({'firmware_sha256':sha(fw),'backup_sha256':sha(backup),'after_sha256':sha(after),'filesystem_unchanged':True,'tail_unchanged':True,'erase_end':hex(0x10000000+end),'release_ready':False},indent=2))
run('reboot',[tool,'reboot'])
