# SPDX-License-Identifier: Apache-2.0
"""Original 'Tiny Horizon': 120 BPM, four bars, two signed8 mono tracks.
Integer/stateless generation streams directly to PSRAM; no song-sized Host RAM.
"""
RATE=48000
LENGTH=384000
BASES=(0x80000,0xe0000)
GAINS=((160,96),(80,144))
MASTER=160
MELODY=(587,440,523,659,587,440,392,440,698,659,587,523,440,523,587,440,
        587,784,698,659,523,587,440,392,440,523,587,659,698,659,523,587)
BASS=(147,147,131,131,175,175,131,147,147,147,196,175,131,131,110,147)
TRI=(0,16,32,48,64,80,96,112,127,112,96,80,64,48,32,16,
     0,-16,-32,-48,-64,-80,-96,-112,-127,-112,-96,-80,-64,-48,-32,-16)

def sample(channel, index):
    index%=LENGTH
    if channel==0:
        step,t=divmod(index,12000)
        env=min(480,t,12000-t)*128//480
        sustain=128-(t*48//12000)
        value=TRI[(t*MELODY[step]*32//RATE)&31]*env*sustain//(128*128)*64//127
    else:
        beat,t=divmod(index,24000)
        bass=TRI[(t*BASS[beat]*32//RATE)&31]*38//127
        # Bound arithmetic below signed31 small-int range on the RP2040 VM.
        noise=(((index&4095)*25173+13849)>>8)&255
        noise-=128
        kick=TRI[((t*110-t*t//480)*32//RATE)&31]*max(0,6000-t)//16000
        hat=noise*max(0,1800-(t%12000))//16000
        snare=noise*max(0,3500-t)//18000 if beat&1 else 0
        value=bass+kick+hat+snare
    # Whole-loop fade to exactly zero avoids a discontinuity at the wrap.
    fade=min(256,index,LENGTH-1-index)
    return max(-127,min(127,value*fade//256))

def fill_block(channel, position, buffer):
    for i in range(len(buffer)): buffer[i]=sample(channel,position+i)&255

def mix(index):
    a,b=sample(0,index),sample(1,index)
    return tuple(max(-32768,min(32767,(a*GAINS[0][side]+b*GAINS[1][side])*MASTER >> 8)) for side in (0,1))

def levels(index, count=256):
    # RMS/peak of actual generated samples and configured gains. The index
    # is a Host-time estimate, not an exposed FPGA sample-position register.
    sums=[0,0]; peaks=[0,0]
    for i in range(count):
        values=mix(index+i)
        for side in (0,1):
            sums[side]+=values[side]*values[side];peaks[side]=max(peaks[side],abs(values[side]))
    return (int((sums[0]//count)**0.5),int((sums[1]//count)**0.5)),tuple(peaks)

def upload(gpu):
    # Both 384000-byte buffers are disjoint from pages and diagnostic scratch.
    statuses=tuple(gpu.audio.pcm_status(c) for c in (0,1))
    gpu.diag.event('pcm_preflight',status=statuses)
    if any(s&0x38 for s in statuses):raise OSError(4,'existing PCM fault; preserve evidence before recovery')
    quiesce(gpu)
    block=bytearray(256)
    for channel in (0,1):
        gpu.audio.pcm_stop(channel)
        gpu.audio.pcm_clear(channel)
        for position in range(0,LENGTH,256):
            fill_block(channel,position,block);gpu.write(BASES[channel]+position,block)
            if position%32768==0:gpu.diag.event('pcm_upload',channel=channel,bytes=position+256,total=LENGTH)
        if gpu.verify_reads:
            actual=bytearray(256)
            for position in range(0,LENGTH,256):
                fill_block(channel,position,block)
                gpu.device.read_into(BASES[channel]+position,actual)
                if block!=actual: raise AssertionError('PCM upload mismatch ch=%d offset=%d'%(channel,position))
    gpu.device.fence()

def quiesce(gpu):
    for c in (0,1):gpu.audio.pcm_stop(c)
    started=gpu.device._now()
    while any(gpu.audio.pcm_status(c)&0x42 for c in (0,1)):
        if gpu.device._expired(started):raise OSError(110,'PCM STOP timeout; no retry')

def start(gpu):
    quiesce(gpu)
    for channel in (0,1):
        gpu.audio.pcm_stop(channel);gpu.audio.pcm_clear(channel)
        gpu.audio.pcm_configure(channel,BASES[channel],BASES[channel]+LENGTH,
            loop=BASES[channel],gain_left=GAINS[channel][0],gain_right=GAINS[channel][1],enabled=True)
        gpu.audio.pcm_prepare(channel)
    gpu.audio.master(MASTER)
    gpu.audio.commit()

def stop(gpu):
    for channel in (0,1): gpu.audio.pcm_enable(channel,False)
    gpu.audio.commit()
    for channel in (0,1): gpu.audio.pcm_stop(channel)
