from pathlib import Path
import sys,math,json,hashlib,wave
R=Path(__file__).resolve().parents[1]; M=R.parent/'midnight_terminal'
sys.path[:0]=[str(M/'.deps'),str(M/'tools'),str(R.parent/'kagura_fb/showcase/vendor')]
from PIL import Image,ImageDraw
from ascii_rows import ROWS
from pack_bgm import compress
G=R/'generated';G.mkdir(exist_ok=True)
pal=[0x001,0x113,0x225,0x337,0x449,0x65b,0x94c,0xc5c,0xf7b,0xfbd,0xeff,0x9ef,0x3cd,0x18a,0xf94,0xffc]
rgb=[tuple(((v>>s)&15)*17 for s in (8,4,0)) for v in pal]
def palette(im):im.putpalette([c for p in rgb for c in p]+[0]*720)
def text(im,xy,s,scale=1,col=11,chrome=False):
 d=ImageDraw.Draw(im);ox,oy=xy
 for k,c in enumerate(s):
  for y,row in enumerate(ROWS[(ord(c)-32)*8:(ord(c)-31)*8]):
   for x in range(8):
    if row&(128>>x):
     xx=ox+k*8*scale+x*scale;yy=oy+y*scale
     if chrome:d.rectangle((xx+3,yy+4,xx+scale+2,yy+scale+3),fill=5)
     d.rectangle((xx,yy,xx+scale-1,yy+scale-1),fill=([10,11,12,13,4,8,9,10][y] if chrome else col))
def pack(im):
 b=bytes(im.getdata());return bytes((b[i]<<4)|b[i+1] for i in range(0,len(b),2))
def inc(name,data):return 'static const uint8_t '+name+'[]={\n'+',\n'.join(','.join(map(str,data[i:i+64])) for i in range(0,len(data),64))+'\n};\n'
im=Image.new('P',(640,360));palette(im);d=ImageDraw.Draw(im)
# Faceted mechanical frame, carefully limited to immutable header/footer.
for y in range(80):
 for x in range(640):
  if y<9 or x<16 or x>623:im.putpixel((x,y),1+((x//32+y//6)%3))
for x in range(12,628,16):d.line((x,8,x+8,0),fill=12)
d.polygon([(18,16),(602,16),(622,36),(604,70),(18,70)],fill=2)
d.line((18,16,602,16,622,36),fill=12,width=2)
text(im,(42,22),'KAGURA-HD',6,chrome=True)
text(im,(43,72),'B E Y O N D   1 6   C O L O R S',1,12)
d.rectangle((0,80,639,303),fill=0)
for y in (81,302):d.line((16,y,623,y),fill=4)
text(im,(24,307),'ONE TINY FPGA. A WHOLE WORLD OF PIXELS.',1,11)
# The source bank is intentionally displayed as a hardware asset gallery.
for a in range(16):
 cx=a*40+16;cy=336
 for y in range(-15,16):
  for x in range(-15,16):
   rr=x*x+y*y
   if a>=8:
    phase=(a-8)*math.pi/4
    value=math.sin((x+15)*math.pi/16+phase)+math.cos((y+15)*math.pi/16-phase)+math.sin((x+y)*math.pi/32+phase)
    im.putpixel((a*40+x+15,320+y+15),3+int((value+3)*1.5))
   elif a%4==3 and abs(x)<14 and abs(y)<12:
    c=11 if abs(x)==13 or abs(y)==11 else 3
    if y< -6:c=6 if a==3 else 13
    if -3<y<0 and -9<x<7:c=12
    if 3<y<5 and -9<x<4:c=8
    im.putpixel((cx+x,cy+y),c)
   elif rr<210:
    z=math.sqrt(210-rr);light=max(0,min(1,(-x-y+z*1.6)/42));c=3+int(light*7)
    if a%4==1:c=12 if abs(x)+abs(y)<13 else 4
    elif a%4==2:c=14 if abs(x)<3 or abs(y)<3 else 5
    elif a%4==3:c=6+((x//4+y//4)&3)
    if ((x*3+y*5+a)&15)==0 and c<10:c+=1
    im.putpixel((cx+x,cy+y),c)
 d.line((a*40,354,a*40+30,354),fill=13)
im.save(G/'frame-atlas.png');raw=pack(im);(G/'frame.4bpp').write_bytes(raw)
# Small plasma map and roto texture: Flash references; dynamic assembly uses FILL runs.
tex=Image.new('P',(32,16));palette(tex)
for y in range(16):
 for x in range(32):tex.putpixel((x,y),3+int((math.sin(x*.35)+math.sin(y*.5)+math.sin((x+y)*.21)+3)*1.2))
tex.save(G/'plasma.png')
# 120 BPM, 4 bars / eight seconds. Original FM bass, arp, pad and deterministic percussion.
N=384000;pcm=bytearray();notes=[40,40,47,43,36,36,43,38,45,45,52,48,38,38,45,47]
for i in range(N):
 t=i/48000;step=int(t*4);p=t*4-step;f=440*2**((notes[step%16]-69)/12)
 bass=math.sin(2*math.pi*f*t+2.4*math.sin(2*math.pi*f*2*t)*math.exp(-p*5))*math.exp(-p*4)
 arpn=[64,67,71,76,62,67,69,74][int(t*8)%8];af=440*2**((arpn-69)/12);q=(t*8)%1
 arp=math.sin(2*math.pi*af*t+1.7*math.sin(2*math.pi*af*3*t))*math.exp(-q*5)
 beat=(t*2)%1;k=math.sin(2*math.pi*(42*(beat/2)+13*(1-math.exp(-beat*18))))*math.exp(-beat*18)
 noise=(((i*1103515245+12345) >> 12)&65535)/32768-1
 hat=noise*math.exp(-q*35);sn=noise*math.exp(-beat*22) if int(t*2)%2 else 0
 pad=.5*math.sin(2*math.pi*130.8128*t)+.5*math.sin(2*math.pi*195.9977*t)
 v=.32*bass+.19*arp+.28*k+.07*hat+.13*sn+.055*pad
 # loop endpoint taper (2ms), avoids a discontinuity without silent beats
 v*=min(1,i/96,(N-1-i)/96)
 pcm.append(int(max(-127,min(127,round(v*110))))&255)
packed=compress(bytes(pcm));(G/'bgm.s8').write_bytes(pcm);(G/'bgm.lz').write_bytes(packed)
with wave.open(str(G/'bgm.wav'),'wb') as w:w.setparams((1,1,48000,0,'NONE',''));w.writeframes(bytes(v^128 for v in pcm))
sounds=[]
for j in range(4):
 n=[4096,2048,8192,8192][j];b=bytes(int(math.sin(2*math.pi*(180+j*140)*i/48000+4*math.sin(i*.05))*math.exp(-i/(n/4))*65)&255 for i in range(n));sounds.append(b);(G/f'fx{j}.s8').write_bytes(b)
code='#include <stdint.h>\n'+inc('frame_lz',compress(raw))+inc('song_lz',packed)
for i,b in enumerate(sounds):code+=inc('fx'+str(i),b)
code+='static const uint16_t b16_pal[16]={'+','.join(map(str,pal))+'};\n'
code+='static const int16_t sine[256]={'+','.join(str(round(math.sin(i*math.tau/256)*1024)) for i in range(256))+'};\n'
code+='static const uint8_t plasma[512]={'+','.join(map(str,tex.getdata()))+'};\n'
code+='static const uint8_t ascii_rows[768]={'+','.join(map(str,ROWS))+'};\n'
(G/'assets.inc').write_text(code)
(G/'asset-report.json').write_text(json.dumps({'original':True,'seed':0xB1616,'palette_rgb444':pal,'frame_bytes':len(raw),'frame_lz_bytes':len(compress(raw)),'bgm_bytes':len(pcm),'bgm_lz_bytes':len(packed),'bgm_seconds':8,'bpm':120,'sfx_bytes':list(map(len,sounds)),'no_full_frame_runtime_upload':True},indent=2))
print('assets',len(code),'BGM packed',len(packed))

