"""Prepare one bounded trial directory. Offline; refuses to replace it."""
from pathlib import Path
import ast,sys,json
root=Path(__file__).resolve().parents[2]
out=root/'build/host-window-observe'/sys.argv[1]
out.mkdir(exist_ok=False);(out/'control').mkdir()
old=root/'build/host-isolation-hardware-2026-11-05'
for name in ('serial_worker.py','dispatch.py','preflight.py','release_pins.py','verify_flash.py'):
    (out/name).write_bytes((old/name).read_bytes())
source=(old/'ram-jobs/034.py').read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef))
(out/'load_adapter.py').write_text('import gc\n'+ast.get_source_segment(source,node)+"\nprint('PIO_ADAPTER_IN_RAM',gc.mem_free())\n")
(out/'identity.py').write_text('''from machine import Pin
assert Pin(9,Pin.IN).value(),'READY low'
_q=KFBPIO()
_id=_q.read(32,True,7)
print('ISO2_IDENTITY',_id.hex(),'PIO_HZ',_q.p.baudrate)
assert _id==b'ISO2\\x00\\x02\\x04','unexpected identification/state'
''')
(out/'trial.py').write_text('''_expected=bytes.fromhex('ed0f2143')
_q.write(39,False,b'\\x01')
_q.write(25,False,b'\\x00')
_q.write(24,False,_expected)
_q.write(25,False,b'\\x00')
_actual=_q.read(24,False,4)
print('ISO2_ECHO EXPECTED',_expected.hex(),'ACTUAL',_actual.hex())
assert _actual==_expected,'ISO2 upload echo mismatch; STOP, no retry'
print('ISO2_HOST_ECHO_PASS')
''')
soft=(old/'restore_soft_reset.py').read_text().replace('build/host-isolation-hardware-2026-11-05/restore-soft-reset.log',out.relative_to(root).as_posix()+'/restore-soft-reset.log')
(out/'restore_soft_reset.py').write_text(soft)
print(str(out))
