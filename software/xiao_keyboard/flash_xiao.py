#!/usr/bin/env python3
"""Back up one explicitly selected BOOTSEL XIAO, flash verified UF2, verify all Flash.

Run only after isolating the XIAO from the powered carrier and identifying its
ROM serial number with picotool info -a. Never targets the live Pico implicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial',required=True)
    p.add_argument('--exclude-serial',action='append',default=[])
    p.add_argument('--picotool',type=Path,required=True)
    p.add_argument('--uf2',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.serial.upper() in [s.upper() for s in args.exclude_serial]:
        p.error('serial belongs to an excluded device')
    out=args.out.resolve()
    if not out.is_relative_to(ROOT/'build') or out.exists():
        p.error('output must be a new directory inside this repository build/')
    uf2=args.uf2.resolve();data=uf2.read_bytes()
    if not data or len(data)%512:raise ValueError('invalid UF2 length')
    writes=[]
    for i in range(0,len(data),512):
        block=data[i:i+512]
        a,b,flags,address,n,index,count,family=struct.unpack_from('<8I',block)
        if ((a,b,struct.unpack_from('<I',block,508)[0])!=(0x0a324655,0x9e5d5157,0x0ab16f30)
            or not flags&0x2000 or flags&1 or family!=0xe48bff56 or n!=256
            or index!=i//512 or count!=len(data)//512
            or not 0x10000000<=address<address+n<=0x10040000):
            raise ValueError('UF2 block outside the XIAO firmware partition or invalid format')
        writes.append((address-0x10000000,block[32:288]))
    if len({address for address,_ in writes})!=len(writes):raise ValueError('duplicate UF2 addresses')
    out.mkdir(parents=True)
    def call(label,*command):
        result=subprocess.run([str(args.picotool.resolve()),*map(str,command),'--ser',args.serial],capture_output=True,timeout=60)
        (out/(label+'.log')).write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(label+' failed; no automatic retry')
        return result.stdout.decode(errors='replace')
    info=call('device','info','-a')
    if 'RP2040' not in info or '2048K' not in info:
        raise ValueError('expected a 2 MiB RP2040 XIAO; see device.log')
    before=out/'before.bin';after=out/'after.bin'
    call('backup','save','-r','0x10000000','0x10200000','-v',before)
    original=before.read_bytes()
    if len(original)!=2097152:raise ValueError('incomplete Flash backup')
    expected=bytearray(original)
    for sector in {address//4096 for address,_ in writes}:
        expected[sector*4096:(sector+1)*4096]=b'\xff'*4096
    for address,payload in writes:expected[address:address+len(payload)]=payload
    if expected[0x40000:]!=original[0x40000:]:raise ValueError('storage would change')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    record={'serial':args.serial,'uf2_sha256':sha(data),'before_sha256':sha(original),
            'expected_after_sha256':sha(expected),'flash_write_attempts':0,'storage_preserved':None}
    def save(): (out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    save()
    (out/'flash.started').write_text('one firmware-only write; no replay\n')
    record['flash_write_attempts']=1;save()
    call('write','load','-v',uf2)
    call('readback','save','-r','0x10000000','0x10200000','-v',after)
    actual=after.read_bytes()
    record['after_sha256']=sha(actual)
    record['all_flash_matches_expected']=actual==expected
    record['storage_preserved']=actual[0x40000:]==original[0x40000:]
    save()
    if actual!=expected:raise RuntimeError('readback mismatch; left in BOOTSEL, no automatic retry')
    call('reboot','reboot')
    record['rebooted']=True;save()
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
