# SPDX-License-Identifier: Apache-2.0
"""The complete MIDNIGHT TERMINAL score, authored and scheduled by Python."""
from kagura_fm import (Schedule,NOTE,GAIN,DRUM,NOISE,PITCH,MASTER,CRUSH,STUTTER,
                       PITCH_RAMP,MASTER_RAMP,ALL_OFF,DELAY)

VOICING = ((58,62,65,69),(58,64,69,74),(57,60,64,67),(60,64,65,69),(58,62,64,69),(59,65,71,77),(58,64,70,76))
ROOTS = (43,48,41,50,46,40,39)
WALK = ((43,46,50,53),(48,52,43,46),(41,45,48,52),(50,48,45,42))
GROOVE = (0,1,2,3)
INTRO = (2,3,0,1)
STEP = 8000


def music_events(s):
    # Separate deterministic score RNG: no dependence on a C audio loop's RNG.
    seed = 0x2545f491
    def random():
        nonlocal seed
        seed = (seed^(seed<<13))&0xffffffff
        seed ^= seed>>17
        seed = (seed^(seed<<5))&0xffffffff
        return seed
    gains = ((225,225),(240,140),(205,205),(170,240),(140,240),(200,200),(200,200))
    for voice, (left,right) in enumerate(gains):
        yield (0,GAIN,voice,0,0,left,right)
    yield (0,MASTER,0,0,0,200,0)
    yield (0,DELAY,0,0,0,100,120)
    noise = None
    for k in range((s.END_MS*48+STEP-1)//STEP):
        at, bar, st = k*STEP, k//16, k%16
        events = []
        def add(op, channel=0, a=0, b=0, value=0, duration=0, delay=0):
            events.append((at+delay,op,channel,a,b,value,duration))
        def note(v, p, n, velocity, gate=0):
            add(NOTE,v,p,n,velocity,gate)
        def chord(c, velocity, gate):
            for i, n in enumerate(VOICING[c]):
                note(i+1,0,n,velocity,gate)
        target = 9000 if bar<=3 else 3500 if bar<=16 else 0 if bar<=30 else 1500 if bar>=37 else 4000
        if target != noise:
            add(NOISE,value=target)
            noise = target
        if bar<=3:
            if st==0:
                chord(INTRO[bar],150 if bar else 120,15*STEP)
                if bar>=2:
                    note(0,1,ROOTS[INTRO[bar]],160,14*STEP)
        elif bar<=16:
            c=GROOVE[(bar-4)%4]
            if st==0: chord(c,175,5*STEP)
            if st==10: chord(c,140,3*STEP)
            if st%4==0: note(0,1,WALK[(bar-4)%4][st//4],200 if st else 225,3*STEP)
            if st in (0,7) or (st==10 and bar%2): add(DRUM,a=0,b=150 if st else 185)
            if st in (4,12): add(DRUM,a=1,b=210,delay=600)
            if st%2==0: add(DRUM,a=2,b=110 if st%4==2 else 150,delay=2400 if st%4==2 else 0)
        elif bar<=21:
            c=4 if bar%2 else 3
            if st==0: note(0,1,38,190 if bar>=20 else 150,15*STEP)
            if st%2==0: note(1+(st//2)%4,0,VOICING[c][(st//2*3)%4]+12*((st//8)&1),120+st*3,3*STEP)
            if bar>=20 and st%8==4: note(5,2,71+(st==12),120,6*STEP)
        elif bar<=27:
            if bar==22 and st==0:
                add(CRUSH,value=4); add(MASTER,value=150)
                add(GAIN,6,value=230,duration=230)
                stop=((s.ANOMALY_END-600)*48+STEP-1)//STEP*STEP
                note(6,6,66,210,max(0,stop-at))
            if st%4==0: add(DRUM,a=0,b=255,value=1)
            if st%8==4: add(DRUM,a=1,b=255)
            if st%3==0:
                c=5 if (k//3)%2 else 6
                for i,n in enumerate(VOICING[c]):
                    note(i+1,0,n+(0 if random()>>30 else 12),200,STEP)
            if st%8==0: note(0,1,40-(st==8),240,7*STEP)
            if st in (6,14) and random()&3:
                add(STUTTER,value=1000 if random()&1 else 2000,duration=2*STEP)
        elif bar<=30:
            if bar==28 and st==0:
                add(CRUSH,value=0); add(MASTER,value=200); add(ALL_OFF)
                stop=(s.MESSAGE_END*48+STEP-1)//STEP*STEP
                note(0,7,26,200,max(0,stop-at))
        elif bar<=38:
            c=2 if bar==38 else INTRO[(bar-31)%4]
            if st==0:
                chord(c,170 if bar==38 else 150,(30 if bar==38 else 15)*STEP)
                if bar>=35: note(0,1,ROOTS[c],190,(28 if bar==38 else 14)*STEP)
            if 35<=bar<38:
                if st in (4,12): add(DRUM,a=1,b=150,delay=600)
                if st%4==2: add(DRUM,a=2,b=90,delay=2400)
        for mb, step, n, length in VIB_MELODY:
            if mb==bar and step==st:
                add(GAIN,5,value=200,duration=240)
                note(5,2,n,210,length*STEP)
        events.sort(key=lambda e:e[0])
        for event in events:
            yield event


def effect_events(s):
    from midnight_fm import audio_events
    for ms, kind, arg in audio_events(s):
        at = ms*48
        if kind==0:
            yield (at,GAIN,6,0,0,170,170)
            yield (at,NOTE,6,3,84+(arg&3)*2,150,0)
        elif kind==1:
            yield (at,DRUM,0,3,120 if arg==200 else 70+((arg*37)&31),0,0)
        elif kind==2: yield (at,NOTE,6,4,81 if arg else 76,200,0)
        elif kind==3: yield (at,NOTE,6,3,79+arg*3,190,0)
        elif kind==4: yield (at,DRUM,0,0,120 if arg else 170,0,0)
        elif kind==5:
            gate=((at+700*48+STEP-1)//STEP)*STEP-at
            yield (at,NOTE,6,5,38 if arg else 45,230,gate)
            yield (at,STUTTER,0,0,0,1600 if arg else 2400,(300 if arg else 500)*48)


def automation_events(s):
    yield ((s.ANOMALY_START-1300)*48,PITCH_RAMP,0,0,0,13536,1200*48)
    yield ((s.ANOMALY_START-100)*48,PITCH,0,0,0,65536,0)
    yield ((s.END_MS-3000)*48,MASTER_RAMP,0,0,0,0,3000*48)


def build_score(s):
    streams = [iter(music_events(s)),iter(effect_events(s)),iter(automation_events(s))]
    heads = [next(g,None) for g in streams]
    result = Schedule()
    while any(h is not None for h in heads):
        choice = min((i for i,h in enumerate(heads) if h is not None),key=lambda i:heads[i][0])
        result.add(*heads[choice])
        heads[choice] = next(streams[choice],None)
    return result

VIB_MELODY = ((8, 0, 74, 6), (8, 6, 77, 2), (8, 8, 81, 8), (9, 0, 79, 4), (9, 4, 76, 4), (9, 8, 74, 8), (10, 0, 72, 4), (10, 4, 76, 4), (10, 8, 79, 4), (10, 12, 81, 4), (11, 0, 77, 8), (11, 8, 76, 4), (11, 12, 74, 4), (12, 0, 70, 4), (12, 4, 74, 4), (12, 8, 77, 8), (13, 0, 76, 6), (13, 6, 79, 2), (13, 8, 82, 8), (14, 0, 81, 12), (14, 12, 79, 4), (15, 0, 77, 16), (35, 0, 81, 8), (35, 8, 79, 8), (36, 0, 77, 8), (36, 8, 76, 8), (37, 0, 74, 16), (38, 0, 77, 24))
