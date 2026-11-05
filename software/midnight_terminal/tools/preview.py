"""PC-only indexed framebuffer backend for the SAME C engine as RP2040.
python tools/preview.py --headless   or   python tools/preview.py
"""
from pathlib import Path
import sys,ctypes as C,json,time,zlib,argparse,statistics,struct
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.deps'))
from PIL import Image,ImageTk,ImageDraw
CALL=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.POINTER(C.c_int32),C.POINTER(C.c_uint8),C.c_uint32)
class Backend:
 def __init__(self,trace=None):
  self.mem=bytearray(4194304);self.shadow=[0]*16;self.palette=[0]*16;self.page=0;self.trace=trace;self.ops={};self.bytes=0;self.audio=[];self.cursor=(0,0,False);self.ms=0;self.frame_crc=[];self.error=None
 def emit(self,ctx,op,a,d,n):
  try:
   args=[a[i] for i in range({1:6,2:8,3:1,4:2,5:1,6:2,7:3}[op])];self.ops[op]=self.ops.get(op,0)+1
   if self.trace:self.trace.write(json.dumps({'ms':self.ms,'op':op,'a':args,'bytes':n})+'\n')
   if op==1:
    p,x,y,w,h,c=args;assert p in (0,1) and 0<=c<16
    for yy in range(max(0,y),min(360,y+h)):
     for xx in range(max(0,x),min(640,x+w)):self.pixel(p,xx,yy,c)
   elif op==2:
    s,sx,sy,p,x,y,w,h=args
    assert s in (0,1) and p in (0,1) and not ((sx|x|w)&1) and sx%8==x%8 and min(sx,sy,x,y,w,h)>=0 and sx+w<=640 and x+w<=640 and sy+h<=360 and y+h<=360
    # Snapshot oracle: packed rows first, no dependence on hardware traversal.
    rows=[bytes(self.mem[s*115200+(sy+j)*320+sx//2:s*115200+(sy+j)*320+(sx+w)//2]) for j in range(h)]
    for j,row in enumerate(rows):start=p*115200+(y+j)*320+x//2;self.mem[start:start+len(row)]=row
   elif op==3:
    address=args[0];assert 0<=address<=4194304-n;self.mem[address:address+n]=C.string_at(d,n);self.bytes+=n
   elif op==4:
    i,v=args;assert 0<=i<16 and 0<=v<4096;self.shadow[i]=v
   elif op==5:
    assert args[0] in (0,1);self.page=args[0];self.palette=self.shadow.copy();self.frame_crc.append((self.ms,zlib.crc32(self.mem[self.page*115200:(self.page+1)*115200])))
   elif op==6:self.audio.append((self.ms,*args))
   elif op==7:self.cursor=tuple(args)
   return 0
  except Exception as e:self.error=repr(e);return -100
 def pixel(self,p,x,y,v):
  i=p*115200+y*320+x//2;self.mem[i]=(self.mem[i]& (15 if x%2==0 else 240)) | (v<<4 if x%2==0 else v)
 def image(self):
  raw=self.mem[self.page*115200:(self.page+1)*115200];pix=bytearray(230400);pix[::2]=bytes(b>>4 for b in raw);pix[1::2]=bytes(b&15 for b in raw)
  im=Image.frombytes('P',(640,360),bytes(pix));pal=[]
  for v in self.palette:pal.extend([(v>>8)*17,((v>>4)&15)*17,(v&15)*17])
  im.putpalette(pal+[0]*720)
  x,y,visible=self.cursor
  if visible:
   draw=ImageDraw.Draw(im)
   for j in range(9):draw.line((x,y+j,x+4-abs(j-4),y+j),fill=11)
  return im
class Engine:
 def __init__(self,reduced=True,trace=None):
  self.lib=C.CDLL(str(ROOT/'out/midnight.dll'));self.lib.mt_size.restype=C.c_size_t;self.buf=C.create_string_buffer(self.lib.mt_size());self.backend=Backend(trace);self.callback=CALL(self.backend.emit)
  self.lib.mt_init.argtypes=[C.c_void_p,CALL,C.c_void_p,C.c_int];self.lib.mt_tick.argtypes=[C.c_void_p,C.c_uint32,C.c_int]
  assert self.lib.mt_init(self.buf,self.callback,None,reduced)==0
 def tick(self,ms,key=0):
  self.backend.ms=ms;r=self.lib.mt_tick(self.buf,ms,key)
  if r:raise RuntimeError((r,self.backend.error))
def headless():
 out=ROOT/'out';out.mkdir(exist_ok=True);(out/'frames').mkdir(exist_ok=True);times=[];timeline=[];samples={3000:'01-boot',19000:'02-bar',33000:'03-choice',43000:'04-anomaly',48500:'05a-onset',53000:'05b-growth',60000:'05c-overrun',62500:'05d-message',64000:'05e-black',72000:'06-restore',84000:'07-ending'}
 with (out/'commands.jsonl').open('w') as trace:
  e=Engine(trace=trace)
  for ms in range(0,88000,33):
   previous=len(e.backend.frame_crc)
   before=time.perf_counter();e.tick(ms);times.append((time.perf_counter()-before)*1000)
   if len(e.backend.frame_crc)!=previous:
    filename=f'frames/{len(timeline):04d}.png';e.backend.image().save(out/filename);timeline.append([ms,filename])
   for target,name in list(samples.items()):
    if ms>=target:e.backend.image().save(out/(name+'.png'));del samples[target]
 b=e.backend;report={'release_ready':False,'pc_preview_complete':True,'duration_ms':88000,'pc_tick_ms_mean':statistics.mean(times),'pc_tick_ms_p95':sorted(times)[int(len(times)*.95)],'pc_tick_ms_max':max(times),'operations':b.ops,'host_asset_bytes':b.bytes,'present_count':len(b.frame_crc),'hardware_fps':None,'hardware_fence_wait_ms':None,'note':'PC ctypes pixel backend timing includes trace and Python emulation; no SPI, FPGA, HDMI or PCM capture.'}
 (out/'frame-crc.json').write_text(json.dumps(b.frame_crc));(out/'audio-events.json').write_text(json.dumps(b.audio));(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 # Offline contact sheet and browser gallery, no browser/system dependency.
 shots=sorted(out.glob('0*.png'));sheet=Image.new('RGB',(1280,((len(shots)+1)//2)*390),(9,13,25))
 for i,p in enumerate(shots):sheet.paste(Image.open(p).convert('RGB'),((i%2)*640,(i//2)*390))
 sheet.save(out/'contact-sheet.png')
 (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>MIDNIGHT TERMINAL / PC preview</title><style>body{background:#090d19;color:#9edacb;font:16px monospace;margin:30px}img{width:640px;image-rendering:pixelated;max-width:100%}#screen{width:1280px}section{display:inline-block;margin:12px}a,button{color:#e18aaa}button{background:#23243f;padding:10px;border:1px solid #326b7e;margin:6px}</style><h1>MIDNIGHT TERMINAL</h1><p>C engine / PC autoplay recording — 実機未検証 / Release NOT READY</p><img id="screen" src="frames/0000.png"><p><button id="play">PLAY / PAUSE</button><button onclick="seek(0)">RESET</button><input id="seek" type="range" min="0" max="87999" value="0" style="width:50%"><span id="clock"></span></p><p id="chapters"></p><audio id="audio" src="midnight-terminal-pc-mix.wav" preload="metadata"></audio><p>Live interactive choices: tools/run_preview.ps1 · ↑↓ / Enter · R restart · F flash option · S screenshot</p><script>const frames='''+json.dumps(timeline)+''';let running=false,origin=0,offset=0,last=-1;const audio=document.getElementById('audio'),screen=document.getElementById('screen'),slider=document.getElementById('seek');function seek(t){offset=t;origin=performance.now();audio.currentTime=t/1000;last=-1;}document.getElementById('play').onclick=()=>{running=!running;origin=performance.now();if(running){audio.currentTime=offset/1000;audio.play().catch(()=>{});}else{offset=Number(slider.value);audio.pause();}};slider.oninput=()=>seek(Number(slider.value));for(const [name,t] of [['BOOT',0],['BAR',12000],['CHOICE',30000],['ANOMALY',40000],['SYSTEM',47000],['RESTORE',65000],['ENDING',80000]]){let b=document.createElement('button');b.textContent=name;b.onclick=()=>seek(t);document.getElementById('chapters').append(b);}function tick(){let t=running?(offset+performance.now()-origin)%88000:offset;slider.value=t;document.getElementById('clock').textContent=(t/1000).toFixed(1)+' / 88s';let lo=0,hi=frames.length;while(lo<hi){let m=(lo+hi)>>1;if(frames[m][0]<=t)lo=m+1;else hi=m;}let i=Math.max(0,lo-1);if(i!==last){screen.src=frames[i][1];last=i;}requestAnimationFrame(tick);}tick();audio.onended=()=>{seek(0);if(running)audio.play();};</script>'''+''.join(f'<section><p>{p.stem}</p><img src="{p.name}"></section>' for p in shots),encoding='utf-8')
def live(smoke=False):
 import tkinter as tk
 try:
  import pygame
  pygame.mixer.init(frequency=48000,size=-16,channels=2,buffer=1024)
  sounds=[pygame.mixer.Sound(str(ROOT/f'generated/{name}.wav')) for name in ['bgm','select','talk','alarm','restore']]
  channels=[pygame.mixer.Channel(0),pygame.mixer.Channel(1)]
 except Exception:
  pygame=None
 root=tk.Tk();root.title('MIDNIGHT TERMINAL — PC / 実機未検証');root.configure(bg='#090d19');e=Engine();label=tk.Label(root,bg='#090d19');label.pack();key=[0];start=[time.perf_counter()];audio_index=[0];reduced=[True]
 def event(ev):
  if ev.keysym in ('Up','Down','Return'):key[0]={'Up':1,'Down':2,'Return':3}[ev.keysym]
  elif ev.keysym.lower()=='r':start[0]=time.perf_counter();e.lib.mt_init(e.buf,e.callback,None,reduced[0])
  elif ev.keysym.lower()=='s':e.backend.image().save(ROOT/'out/live-capture.png')
  elif ev.keysym.lower()=='f':reduced[0]=not reduced[0];e.lib.mt_init(e.buf,e.callback,None,reduced[0]);start[0]=time.perf_counter()
 root.bind('<Key>',event)
 def loop():
  ms=int((time.perf_counter()-start[0])*1000);e.tick(ms,key[0]);key[0]=0
  if len(e.backend.audio)>audio_index[0]:
   for _,sound,gain in e.backend.audio[audio_index[0]:]:
    if pygame:
     if sound<0:pygame.mixer.stop()
     else:
      ch=channels[0 if sound==0 else 1];ch.set_volume(gain/256*180/256)
      if sound!=0 or not ch.get_busy():ch.play(sounds[sound],loops=-1 if sound==0 else 0)
   audio_index[0]=len(e.backend.audio)
  label.photo=ImageTk.PhotoImage(e.backend.image().resize((1280,720),Image.Resampling.NEAREST));label.configure(image=label.photo);root.after(33,loop)
 if smoke:
  def finish():
   e.backend.image().save(ROOT/'out/gui-smoke.png');(ROOT/'out/gui-smoke.json').write_text(json.dumps({'tk_render':True,'pcm_mixer_initialized':pygame is not None,'integer_scale':2}));root.destroy()
  root.after(3000,finish)
 loop();root.mainloop()
 if pygame:pygame.mixer.quit()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--headless',action='store_true');p.add_argument('--smoke-gui',action='store_true');args=p.parse_args();headless() if args.headless else live(args.smoke_gui)

