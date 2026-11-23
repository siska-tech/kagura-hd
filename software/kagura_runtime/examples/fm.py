"""Define an FM sound entirely in Python and play a chord."""
from kagura_fm import Synth,Patch,operator

sound=Patch((operator(ratio=1,level=16000,attack_ms=5,release_ms=300),
             operator(ratio=2,level=6000,decay_ms=250),
             operator(),operator()))
with Synth([sound],autostart=False) as fm:
    for voice,note in enumerate((60,64,67)):
        fm.note_on(note,voice=voice,gate_ms=500)
    fm.start()
    fm.sleep_ms(1000)
