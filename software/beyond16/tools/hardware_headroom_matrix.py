"""Explicitly authorized eight-firmware campaign. First failure stops; never replay.
No FPGA programming, clock change, rebuild, backup overwrite, or release operation.
"""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[3]; R=ROOT/'software/beyond16'
sys.path.insert(0,str(ROOT/'build/showcase-hardware-deps'))
from serial.tools import list_ports
UID=os.environ['KAGURA_RP2040_UID']
BASE=Path(os.environ['KAGURA_HEADROOM_CAMPAIGN']).resolve()
assert BASE.is_relative_to(ROOT/'build')
RESUME=os.environ.get('KAGURA_RESUME_PRESTART')=='1'
if not RESUME:BASE.mkdir(exist_ok=False)
TOOL=ROOT/'build/midnight-hardware/picotool/picotool/picotool.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
state=dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),release_ready=False,
           authorized_scope='user requested eight-variant physical comparison',variants=[],failure=None,
           fpga_programming=0,fpga_flash_writes=0)
if RESUME:
    state=json.loads((BASE/'campaign.json').read_text())
    assert state['failure'] in ("AssertionError('A-off/demo failed; no retry')", "FileExistsError(17, 'File exists')")
    first=BASE/'A-off'
    assert not (first/'demo.started').exists() and not (first/'demo-result.json').exists()
    assert json.loads((first/'bench-result.json').read_text())['success']
    assert b'STOP rc=0;' in (first/'bench-usb.log').read_bytes()
    state.setdefault('prestart_incidents',[]).append(state['failure']);state['failure']=None
    state['resumed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
def save():(BASE/'campaign.json').write_text(json.dumps(state,indent=2))
def run(folder,name,args,timeout=120):
    print('STAGE',folder.name,name,flush=True)
    with (folder/(name+'.log')).open('xb') as log:
        p=subprocess.run([str(x) for x in args],stdout=log,stderr=subprocess.STDOUT,timeout=timeout,cwd=ROOT)
    assert p.returncode==0,f'{folder.name}/{name}: exit {p.returncode}'
def flash_read(folder,name,force=False):
    path=folder/(name+'.bin');assert not path.exists()
    args=[TOOL,'save','-r','0x10000000','0x10200000','-v',path,'--ser',UID]
    if force:args+=['-F']
    run(folder,name,args);assert path.stat().st_size==2097152
    return path
def wait_usb():
    deadline=time.monotonic()+20
    # reboot -f may return while Windows still exposes the old COM instance.
    # Allow detach/re-enumeration before requiring a stable matching inventory.
    time.sleep(3)
    stable=None
    while time.monotonic()<deadline:
        ports=[p for p in list_ports.comports() if p.vid==0x2e8a and (p.serial_number or '').upper()==UID.upper()]
        if len(ports)==1:
            if stable is None:stable=time.monotonic()
            elif time.monotonic()-stable>=1:return
        else:stable=None
        time.sleep(.25)
    raise RuntimeError('USB enumeration deadline; no stimulus sent')
try:
    run(BASE,('resume-' if RESUME else '')+'offline-protection',[sys.executable,R/'tools/verify_headroom.py'])
    manifests=json.loads((R/'evidence/headroom-firmware.json').read_text(encoding='utf-8-sig'))
    assert len(manifests)==8
    expected=json.loads((R/'evidence/host-ab-ON/flash-write-verified.json').read_text())['after_sha256']
    for item in manifests:
        name=item['variant']['Name'];folder=BASE/name
        resuming=RESUME and name=='A-off'
        if not resuming:folder.mkdir()
        fw=R/'out/headroom-firmware'/name/'beyond16.bin'
        assert sha(fw)==item['bin_sha256']
        assert sha(fw.with_suffix('.elf'))==item['elf_sha256']
        f=fw.read_bytes();erase=(len(f)+4095)&~4095;assert erase<=0xa0000
        if resuming:
            record=state['variants'][0];after=folder/'after.bin'
            current=flash_read(folder,'resume-prestart-check',force=True)
            assert current.read_bytes()==after.read_bytes(),'Flash changed before unstarted demo'
        else:
            record=dict(name=name,firmware_sha256=sha(fw),stage='backup',success=False)
            state['variants'].append(record);save()
            before=flash_read(folder,'before',force=True)
            duplicate=flash_read(folder,'before-confirm')
            assert sha(before)==sha(duplicate)==expected,'unexpected current Flash; no write performed'
            record['backup_sha256']=sha(before);save()
            (folder/'plan.json').write_text(json.dumps(dict(firmware_sha256=sha(fw),backup_sha256=sha(before),release_ready=False,fpga_programming=0),indent=2))
            record['stage']='write';save()
            run(folder,'write',[TOOL,'load','-v',fw,'--ser',UID])
            after=flash_read(folder,'after')
            a,b=before.read_bytes(),after.read_bytes()
            assert b[:len(f)]==f and b[erase:]==a[erase:] and b[0xa0000:]==a[0xa0000:]
            verified=dict(firmware_sha256=sha(fw),backup_sha256=sha(before),after_sha256=sha(after),filesystem_unchanged=True,tail_unchanged=True,erase_end=hex(0x10000000+erase),release_ready=False)
            (folder/'flash-write-verified.json').write_text(json.dumps(verified,indent=2))
        env=dict(os.environ,KAGURA_CAMPAIGN_DIR=str(folder),KAGURA_RP2040_UID=UID)
        for mode in ('bench','demo'):
            if resuming and mode=='bench':continue
            record['stage']=mode;save()
            args=[TOOL,'reboot','--ser',UID]
            if mode=='demo' and not resuming:args+=['-f']
            run(folder,('resume-' if resuming else '')+'reboot-'+mode,args);wait_usb()
            print('RUN',name,mode,flush=True)
            with (folder/(mode+'-runner.log')).open('xb') as runner_log:
                result=subprocess.run([sys.executable,str(R/'tools/hardware_run.py'),mode],env=env,cwd=ROOT,stdout=runner_log,stderr=subprocess.STDOUT)
            assert result.returncode==0,f'{name}/{mode} failed; no retry'
            status=json.loads((folder/(mode+'-result.json')).read_text())
            assert status['success'] and status['failure'] is None
            if mode=='demo':
                run(folder,'present-analysis',[sys.executable,R/'tools/analyze_headroom_log.py',folder/'demo-usb.log','--output',folder/'present.json'])
        record['stage']='final-readback';save()
        final=flash_read(folder,'after-tests',force=True)
        assert final.read_bytes()==after.read_bytes(),'Flash changed during tests'
        record.update(success=True,stage='complete',after_sha256=sha(final),filesystem_unchanged=True,full_readback_unchanged=True)
        expected=sha(final);save();print('COMPLETE',name,flush=True)
    # Last firmware remains installed, waiting at the explicit start gate.
    run(BASE,'final-reboot',[TOOL,'reboot','--ser',UID]);wait_usb()
    run(BASE,'final-protection',[sys.executable,R/'tools/verify_headroom.py'])
    state['success']=True;state['final_state']='work64 installed; explicit g/b gate, PCM stopped, FPGA unchanged'
except BaseException as ex:
    state['failure']=repr(ex);state['success']=False
    print('FIRST FAILURE; CAMPAIGN STOPPED; NO REPLAY:',repr(ex),flush=True)
    raise
finally:
    state['finish_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
