from pathlib import Path
import sys,ctypes as C,time,json,statistics,zlib,argparse
R=Path(__file__).resolve().parents[1]
if sys.platform=='win32':sys.path.insert(0,str(R.parent/'midnight_terminal/.deps'))
try:from PIL import Image
except ImportError:Image=None # Headless pixel/command verification needs only stdlib.
class Stats(C.Structure):_fields_=[('commands',C.c_uint64),('blit_pixels',C.c_uint64),('upload_bytes',C.c_uint64),('frames',C.c_uint32),('skipped',C.c_uint32),('scene',C.c_uint32),('now_ms',C.c_uint32),('error',C.c_int)]
class Engine:
 def __init__(self,variant='optimized',seed=0xB1616):
  self.lib=C.CDLL(str(R/'out'/(f'{variant}.dll' if sys.platform=='win32' else f'lib{variant}.so')));l=self.lib;l.pc_memory.restype=C.POINTER(C.c_uint8);l.pc_palette.restype=C.POINTER(C.c_uint16);l.pc_counts.restype=C.POINTER(C.c_uint64);l.pc_stats.restype=C.POINTER(Stats);l.pc_trace.argtypes=[C.c_char_p]
  assert l.pc_init(seed,variant=='optimized')==0
 def tick(self,t):
  r=self.lib.pc_tick(t)
  if r:raise RuntimeError(f'GPU error {r} at {t}ms')
 def counts(self):return list(self.lib.pc_counts()[:8])
 def memory(self):return C.string_at(self.lib.pc_memory(),230400)
 def image(self):
  p=self.lib.pc_page();b=C.string_at(C.addressof(self.lib.pc_memory().contents)+p*115200,115200);pix=bytearray(230400);pix[0::2]=bytes(v>>4 for v in b);pix[1::2]=bytes(v&15 for v in b);im=Image.frombytes('P',(640,360),bytes(pix));pal=self.lib.pc_palette()[:16];im.putpalette([((v>>s)&15)*17 for v in pal for s in (8,4,0)]+[0]*720);return im
SCENES=[('BOOT',0,10000),('HYPERSPACE',10000,30000),('RASTER WAVES',30000,50000),('PLASMA ENGINE',50000,70000),('ROTOZOOM',70000,95000),('BLIT STORM',95000,120000),('VECTOR WORLD',120000,140000),('FINALE',140000,150000)]
def run(variant='optimized',save=True):
 e=Engine(variant);before=e.counts();init=before.copy();rows=[];crc=[];start=time.perf_counter()
 for scene,(name,a,b) in enumerate(SCENES):
  ts=[];c=e.counts();frames=0
  for t in range(a,b,33):
   clock=time.perf_counter_ns();e.tick(t);ts.append((time.perf_counter_ns()-clock)/1e6);frames+=1
   if t>=a+(b-a)//2 and (not crc or crc[-1][0]!=scene):
    crc.append((scene,zlib.crc32(e.memory())))
    if save and Image is not None:e.image().save(R/'evidence'/f'{scene:02}-{name.replace(" ","-")}.png')
  after=e.counts();delta=[x-y for x,y in zip(after,c)];seconds=(b-a)/1000
  rows.append({'scene':scene,'name':name,'logical_seconds':seconds,'frames':frames,'transactions':delta[0],'wire_bytes':delta[1],'gpu_commands':delta[2],'blit_pixels':delta[4],'transactions_per_logical_second':delta[0]/seconds,'wire_bytes_per_logical_second':delta[1]/seconds,'cpu_frame_mean_ms':statistics.mean(ts),'cpu_frame_worst_ms':max(ts),'cpu_frame_p95_ms':sorted(ts)[int(len(ts)*.95)],'logical_update_fps':frames/seconds,'fence_wait_hardware_ms':None,'pcm_underrun_hardware':None})
 total=[x-y for x,y in zip(e.counts(),before)];assert total[6:]==[0,0];e.lib.pc_finish()
 report={'scope':'native C engine + existing C SDK + behavioral register model; no physical wait, PIO or PSRAM arbitration','variant':variant,'release_ready':False,'initial_load_counts':init,'runtime_counts':total,'wall_seconds':time.perf_counter()-start,'scenes':rows,'frame_crc32':crc,'hardware':'NOT RUN','pcm_model_faults':0,'pcm_underrun':None}
 if save:(R/'evidence'/f'pc-{variant}.json').write_text(json.dumps(report,indent=2))
 return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--headless',action='store_true');p.add_argument('--smoke-gui',action='store_true');p.add_argument('--scene',type=int,choices=range(8));p.add_argument('--seed',type=lambda x:int(x,0),default=0xB1616);p.add_argument('--capture',type=Path);args=p.parse_args()
 if args.headless:print(json.dumps(run(),indent=2));return
 import tkinter as tk
 from PIL import ImageTk
 if args.smoke_gui:
  e=Engine(seed=args.seed);e.tick(145000);app=tk.Tk();app.withdraw();im=ImageTk.PhotoImage(e.image());label=tk.Label(app,image=im);label.pack();app.update()
  import pygame
  pygame.mixer.init(48000,-16,2,512);sound=pygame.mixer.Sound(str(R/'generated/bgm.wav'))
  (R/'evidence/gui-smoke.json').write_text(json.dumps({'tk_image_size':[im.width(),im.height()],'mixer':pygame.mixer.get_init(),'bgm_seconds':sound.get_length(),'listening_test':False,'hardware_access':False},indent=2));pygame.mixer.quit();app.destroy();return
 e=Engine(seed=args.seed);app=tk.Tk();app.title('KAGURA-HD — BEYOND 16 COLORS / PC behavioral preview');label=tk.Label(app);label.pack();offset=SCENES[args.scene][1] if args.scene is not None else 0;start=time.perf_counter();paused=False
 try:
  import pygame,wave
  pygame.mixer.init(48000,-16,2,512)
  if (R/'out/beyond16-pc.wav').exists():
   with wave.open(str(R/'out/beyond16-pc.wav')) as w:w.setpos(offset*48);sound=pygame.mixer.Sound(buffer=w.readframes(w.getnframes()-offset*48))
   sound.play()
  else:pygame.mixer.music.load(str(R/'generated/bgm.wav'));pygame.mixer.music.play(-1)
 except Exception as ex:print('PC audio unavailable:',ex)
 start=time.perf_counter()
 def capture(_=None):e.image().save(args.capture or R/'out/capture.png')
 def update():
  t=int((time.perf_counter()-start)*1000)+offset
  if args.scene is not None and t>=SCENES[args.scene][2]:app.destroy();return
  if t>=150000:app.destroy();return
  e.tick(t);im=ImageTk.PhotoImage(e.image().resize((1280,720),Image.Resampling.NEAREST));label.configure(image=im);label.image=im;app.after(16,update)
 app.bind('s',capture);app.bind('<Escape>',lambda _:app.destroy());update();app.mainloop();e.lib.pc_finish()
if __name__=='__main__':main()
