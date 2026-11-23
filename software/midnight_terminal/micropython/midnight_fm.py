# SPDX-License-Identifier: Apache-2.0
"""Seven-voice FM instrument API and Python-authored timed sound effects."""
from midnight_instruments import INSTRUMENTS, presets, dsp_parameters
from kagura_fm import Synth as Engine
from midnight_music import build_score
BLIP, KEY, CHIME, MOVE, THUMP, STING = range(6)


def audio_events(script):
    """Build sample-timed cues from the same Python strings the show renders."""
    s, events = script, []
    if min(s.CHAR_MS, s.TERM_CHAR_MS, s.MESSAGE_CHAR_MS) <= 0:
        raise ValueError('typing intervals must be positive')
    for at, _, text in s.DIALOGUE:
        for i in range(0, len(text), 2):
            events.append((at+i*s.CHAR_MS, BLIP, i&7))
    for at, text in s.TERMINAL:
        for i in range(len(text)):
            events.append((at+i*s.TERM_CHAR_MS, KEY, i&255))
    events.append((s.CHOICE_SHOW, CHIME, 0))
    events.extend((at, MOVE, i) for i, at in enumerate(s.CHOICE_MOVES))
    events.append((s.CHOICE_PICK, CHIME, 1))
    events.extend((s.MESSAGE_START+i*s.MESSAGE_CHAR_MS, KEY, 200) for i in range(len(s.MESSAGE)))
    for at in range(s.MESSAGE_START-600, s.MESSAGE_END, 1150):
        events.extend(((at, THUMP, 0), (at+230, THUMP, 1)))
    events.extend(((s.GLITCH_START, STING, 0), (s.RED_EYES[0], STING, 1)))
    events.sort()
    if len(events) > 768 or any(at < 0 or at > 3600000 for at, _, _ in events):
        raise ValueError('audio cue capacity or time range exceeded')
    return events


class Synth(Engine):
    """Application presets on the generic, configurable KAGURA FM engine."""
    def __init__(self, backend=None, script=None, score=False, autostart=True):
        if score:
            if script is None:
                import story
                script = story
            schedule = build_score(script)
        else:
            schedule = b''
        super().__init__(presets(), schedule, backend, autostart, dsp_parameters())

    def note_on(self, note, voice=0, instrument='ep', velocity=200, gate_ms=0):
        if isinstance(instrument,str):
            instrument=INSTRUMENTS.index(instrument)
        super().note_on(note,voice,instrument,velocity,gate_ms)
