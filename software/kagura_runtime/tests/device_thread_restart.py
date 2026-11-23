"""Run on an RP2040: idle-core IRQs must never overwrite reclaimed heap.

The clock setter invokes the rp2 flash-timing lockout path, even when the
frequency is unchanged. Reuse the stopped FM worker's heap before that call.
"""
import gc
import hashlib
import machine
from kagura_fm import Synth, Patch, operator, Schedule, NOTE


def _digest(pages):
    digest=hashlib.sha256()
    for page in pages:
        digest.update(page)
    return digest.digest()


def run(cycles=20):
    patch=Patch((operator(level=12000),operator(level=3000),operator(),operator()))
    for cycle in range(cycles):
        with Synth((patch,)) as synth:
            synth.note_on(60,gate_ms=30)
            synth.sleep_ms(40)
        del synth
        gc.collect()
        schedule=Schedule()
        for index in range(1005):
            schedule.add(index*256,NOTE,index%7,0,60+index%12,100,240)
        pages=schedule.pages()
        before=_digest(pages)
        machine.freq(machine.freq())
        assert _digest(pages)==before,'stopped worker IRQ corrupted Python heap'
        with Synth((patch,),pages,autostart=False):
            pass
        del schedule,pages
        gc.collect()
        print('THREAD_RESTART_PASS',cycle+1,gc.mem_free())
    return {'worker_restarts':cycles,'configuration_opens':cycles*2,'heap_intact':True}
