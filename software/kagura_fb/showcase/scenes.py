# SPDX-License-Identifier: Apache-2.0
"""Six deterministic visual chapters. All rectangles use the hardware FILL API."""
from .gpu_api_adapter import PALETTE
from . import music
from .diagnostics import diff_us

NAMES=('BOOT & TITLE','FILL / GRAPHICS ENGINE','BLIT / WINDOW MOVEMENT',
       'PALETTE / DOUBLE BUFFER','HARDWARE CURSOR','AUDIO / VISUAL SHOWCASE')
FRAMES=(32,48,48,48,48,64)

def panel(g,page,x,y,w,h,color=1):
    g.fill(page,x+4,y+4,w,h,0);g.fill(page,x,y,w,h,3)
    g.fill(page,x+1,y+1,w-2,h-2,color)

def header(g,page,chapter,title,subtitle):
    g.fill(page,0,0,640,360,0)
    g.fill(page,32,21,4,20,9)
    g.text(page,48,24,title,6,0,2)
    g.text(page,48,51,subtitle,4,0)
    g.fill(page,32,331,576,1,3)
    g.text(page,32,343,'KAGURA-HD / ONE TINY FPGA',4,0)
    g.text(page,544,343,'%02d / 06'%chapter,9,0)

def window(g,page,x,y,w,h,title,accent=8):
    panel(g,page,x,y,w,h,1)
    g.fill(page,x+1,y+1,w-2,21,accent)
    g.fill(page,x+w-18,y+6,10,10,0)
    g.text(page,x+8,y+7,title,6,accent)
    for k in range(4): g.fill(page,x+12,y+38+k*16,w-24-k*16,4,2+k)

def template(g,index):
    header(g,0,index+1,NAMES[index],
        ('16 COLORS. ONE TINY FPGA.','RECTANGLES IN HARDWARE / DELTA UPDATES',
         'OVERLAP SAFE / ALL FOUR DIRECTIONS','PALETTE SHADOW + VBLANK PRESENT',
         'DEDICATED 2BPP OVERLAY / FB STAYS STILL','ORIGINAL MUSIC / TWO SIGNED 8-BIT TRACKS')[index])

def clone(g):
    g.copy(0,0,0,1,0,0,640,360);g.present(0)

def blit_background(g,page):
    header(g,page,3,NAMES[2],'OVERLAP SAFE / ALL FOUR DIRECTIONS')
    for x in range(32,609,32):g.fill(page,x,84,1,228,2)
    for y in range(84,313,24):g.fill(page,32,y,576,1,2)
    window(g,page,32,94,256,152,'PATTERN / ROM',7)
    window(g,page,352,142,248,150,'BACKGROUND',10)
    g.text(page,32,308,'GPU COPY + EXPOSED-STRIP RESTORATION',4,0)

def enter(g,index):
    g.palette(PALETTE);template(g,index);state={}
    if index==0:
        g.fill(0,32,108,56,56,9);g.fill(0,36,112,48,48,0)
        g.text(0,40,116,'K',9,0,5)
        g.text(0,112,106,'KAGURA-HD',6,0,6)
        g.text(0,112,166,'16 COLORS, ONE TINY FPGA',9,0,2)
        labels=(('640x360','16 COLORS'),('720p60','HDMI OUTPUT'),('TANG 9K','TINY FPGA'),('2ch PCM','48kHz AUDIO'))
        for i,(a,b) in enumerate(labels):
            x=32+i*148;panel(g,0,x,242,132,58)
            g.text(0,x+8,253,a,6,1,2);g.text(0,x+8,278,b,4,1)
        g.text(0,136,306,'HARDWARE ACCELERATED GRAPHICS',4,0)
    elif index==1:
        for row in range(5):
            for col in range(8):g.fill(0,32+col*50,98+row*39,46,35,2+(row+col)%14)
        panel(g,0,456,98,152,191)
        g.text(0,468,114,'FILL ENGINE',9,1)
        g.text(0,468,142,'RECTS / STEP',4,1);g.text(0,468,158,'0006',6,1,2)
        g.text(0,468,208,'FILL + BLIT',4,1)
        g.text(0,32,306,'LOCAL PATCHES. NO FULL-SCREEN PIXEL UPLOAD.',4,0)
        state['patches']=[]
    elif index==2:
        blit_background(g,0)
        g.copy(0,0,0,1,0,0,640,360)
        # Include the 4px drop shadow in the copied/restored footprint.
        # 228 is even and still legal for same-phase hardware BLIT.
        state['rects']=[(80,136,228,132),(80,136,228,132)]
        for page in (0,1):
            window(g,page,80,136,224,128,'OVERLAP BLIT',8)
            g.text(page,96,230,'MOVE WITHOUT REDRAW',9,1)
        g.present(0)
        return state
    elif index==3:
        for y in range(8):
            for x in range(16):g.fill(0,32+x*36,86+y*26,34,24,7+(x+y)%9)
        panel(g,0,208,151,224,66)
        g.text(0,224,169,'PAGE 0',6,1,4)
        g.text(0,32,306,'FIRST: PALETTE ONLY    THEN: PAGE + PALETTE',4,0)
        g.copy(0,0,0,1,0,0,640,360)
        g.text(1,224,169,'PAGE 1',6,1,4)
        g.present(0);return state
    elif index==4:
        window(g,0,48,94,320,174,'CURSOR LAB',7)
        panel(g,0,400,94,208,174)
        g.text(0,416,114,'32x32 / 2BPP',9,1)
        g.text(0,416,142,'BANK + PALETTE',6,1)
        g.text(0,416,166,'VBLANK COMMIT',4,1)
        g.text(0,416,190,'EDGE CLIPPING',4,1)
        g.fill(0,72,220,104,28,8);g.text(0,80,230,'HOVER',6,8)
        g.fill(0,208,220,128,28,10);g.text(0,216,230,'SELECT',6,10)
        g.text(0,72,288,'CURSOR MOVES. FRAMEBUFFER DOES NOT.',9,0)
        clone(g)
        if g.verify_reads: state['crc']=(g.crc(0),g.crc(1))
        first=g.shape(0);g.cursor(72,140,first)
        second=g.shape(1);state['banks']=(first,second)
        return state
    elif index==5:
        panel(g,0,32,90,576,85)
        g.text(0,48,102,'L',9,1,2);g.text(0,344,102,'R',13,1,2)
        g.text(0,48,151,'LINEAR RMS x4 / SOURCE SAMPLES + CONFIGURED GAINS',4,1)
        panel(g,0,32,186,576,91)
        g.text(0,48,286,'SOURCE TRACE / HOST-TIMED POSITION ESTIMATE',4,0)
        g.text(0,48,308,'PCM0 + PCM1 / 48000 Hz / LOOP',9,0)
    if index==0:g.palette((0,)*16)  # No full-bright title flash before fade-in.
    clone(g)
    if index==5:
        music.start(g);state['epoch']=g.diag.clock()
    return state

def _restore(g,page,old,new):
    x,y,w,h=old;nx,ny,nw,nh=new
    top=max(y,ny);bottom=min(y+h,ny+h)
    strips=[]
    if top>y:strips.append((x,y,x+w,top))
    if bottom<y+h:strips.append((x,bottom,x+w,y+h))
    if bottom>top:
        if nx>x:strips.append((x,top,min(x+w,nx),bottom))
        if nx+w<x+w:strips.append((nx+w,top,x+w,bottom))
    # COPY is opaque. The offset shadow's two 4x4 corner holes carry old
    # background when copied; reconstruct the background at their NEW position.
    strips.extend(((nx+nw-4,ny,nx+nw,ny+4),(nx,ny+nh-4,nx+4,ny+nh)))
    try:
        for strip in strips:
            g.clip=strip;blit_background(g,page)
    finally:g.clip=None

def tick(g,index,state,frame):
    if index==0:
        page=1-g.page
        if frame<10:
            gain=frame+1
            g.palette(tuple((((c>>8)&15)*gain//10<<8)|(((c>>4)&15)*gain//10<<4)|((c&15)*gain//10) for c in PALETTE))
        for i in range(16):g.fill(page,32+i*36,214,32,6,7+(i+frame)%9)
        g.present(page)
    elif index==1:
        page=1-g.page
        for patch in state['patches']:g.fill(page,*patch)
        patches=[]
        for i in range(6):
            cell=(frame*7+i*11)%40;col,row=cell%8,cell//8
            patch=(32+col*50,98+row*39,46,35,2+(frame+i*3)%14)
            g.fill(page,*patch);patches.append(patch)
        g.text(page,468,228,'%06d'%((g.diag.commands[1]+g.diag.commands[6])%1000000),6,1,2)
        g.present(page);state['patches']=patches
    elif index==2:
        phase=frame%48
        x=80+8*(phase if phase<24 else 48-phase)
        q=(frame+6)%24;y=112+4*(q if q<12 else 24-q)
        page=1-g.page;old=state['rects'][page];new=(x,y,228,132)
        if old!=new:
            g.copy(page,old[0],old[1],page,x,y,new[2],new[3])
            _restore(g,page,old,new)
        state['rects'][page]=new
        g.present(page)
    elif index==3:
        colors=list(PALETTE)
        for i in range(7,16):colors[i]=PALETTE[7+(i-7+frame)%9]
        g.palette(colors)
        if frame<24:g.present(0)  # No framebuffer writes in this phase.
        else:
            page=1-g.page
            g.fill(page,48,262,544,28,1)
            g.fill(page,56+8*(frame%48),270,96,12,9)
            g.present(page)
    elif index==4:
        points=((-12,-12),(320,8),(648,80),(638,354),(320,368),(-12,180),(120,234),(264,234),(-12,-12))
        part=frame//6;fraction=frame%6
        a,b=points[part],points[part+1]
        x=a[0]+(b[0]-a[0])*fraction//6;y=a[1]+(b[1]-a[1])*fraction//6
        g.cursor(x,y,state['banks'][0 if frame<24 else 1])
    else:
        statuses=tuple(g.audio.pcm_status(c) for c in (0,1))
        if any(s & 0x3c or not s & 2 for s in statuses):raise OSError(4,'PCM inactive/DONE/underrun/config/memory fault')
        index_sample=max(0,diff_us(g.diag.clock(),state['epoch']))*48//1000
        rms,peak=music.levels(index_sample)
        page=1-g.page
        for side in (0,1):
            x=48+296*side;g.fill(page,x,126,232,14,2)
            g.fill(page,x,126,min(232,rms[side]*232//8192),14,9 if side==0 else 13)
            g.text(page,x+32,106,'RMS %05d'%rms[side],6,1)
        g.fill(page,48,200,544,65,1)
        for k in range(48):
            value=music.mix(index_sample+k*32)[0]
            height=min(29,abs(value)//512)
            g.fill(page,52+k*11,232-(height if value>0 else 0),8,max(1,height),9 if value>0 else 15)
        g.text(page,48,308,'PCM0 %02X + PCM1 %02X / MASTER %03d'%(statuses[0],statuses[1],music.MASTER),9,0)
        g.present(page)
        g.diag.event('audio',source_sample_estimate=index_sample%music.LENGTH,rms=rms,peak=peak,
            pcm_status=statuses,fifo_level=None,fifo_reason='not exposed by ABI',meter_source='generated PCM + committed gains, Host-time estimate')

def leave(g,index,state):
    if index==4:
        g.cursor(0,0,visible=False)
        if g.verify_reads:
            actual=(g.crc(0),g.crc(1))
            if actual!=state['crc']:raise AssertionError('cursor changed framebuffer CRC')
            g.diag.event('cursor_crc',before=state['crc'],after=actual,pass_crc=True)
    if index==5:music.stop(g)
    g.verify()
