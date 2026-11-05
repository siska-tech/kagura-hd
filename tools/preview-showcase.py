"""Generate actual wire-Mock screenshots/movie frames + original stereo WAV.
Pure Python stdlib; no drawing substitute for the demo's real Device commands.
"""
from pathlib import Path
import sys,json,zlib,struct,binascii,base64,wave,hashlib,tracemalloc
r=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(r/'software/kagura_fb'),str(r/'software/kagura_fb/tests')]
from kagura_fb import Device
from kagura_fb_audio import Audio
from showcase.pc_mock import ShowcaseModel,VirtualClock
from showcase.gpu_api_adapter import GPU
from showcase.diagnostics import Diagnostics
from showcase.framebuffer_oracle import FramebufferOracle
from showcase.scene_manager import Demo
from showcase import music,scenes
out=r/'build/showcase/preview';out.mkdir(parents=True,exist_ok=True)
(out/'frames').mkdir(exist_ok=True)

def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',binascii.crc32(name+data)&0xffffffff)
def png(rgb,w,h):
    rows=b''.join(b'\0'+rgb[y*w*3:(y+1)*w*3] for y in range(h))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows,6))+chunk(b'IEND',b'')

def render(model):
    palette=[bytes(((c>>8)*17,((c>>4)&15)*17,(c&15)*17)) for c in model.active_palette]
    base=model.page*115200;rgb=bytearray(640*360*3)
    for y in range(360):
        for x in range(640):
            value=model.memory[base+y*320+x//2];index=value>>4 if x%2==0 else value&15
            at=(y*640+x)*3;rgb[at:at+3]=palette[index]
    if model.cursor_visible:
        x,y,bank,_=model.cursor_position;hx,hy=model.cursor_hotspots[bank]
        colors=model.cursor_palettes[bank]
        for yy in range(32):
            for xx in range(32):
                px,py=x-hx+xx,y-hy+yy
                if 0<=px<640 and 0<=py<360:
                    index=(model.cursor_assets[bank][yy*8+xx//4]>>(6-(xx%4)*2))&3
                    if index:
                        color=colors[(index-1)*2]|colors[(index-1)*2+1]<<8
                        at=(py*640+px)*3;rgb[at:at+3]=bytes(((color>>8)*17,((color>>4)&15)*17,(color&15)*17))
    return bytes(rgb)

def upscale(rgb):
    rows=[]
    for y in range(360):
        line=b''.join(rgb[(y*640+x)*3:(y*640+x+1)*3]*2 for x in range(640))
        rows.extend((line,line))
    return b''.join(rows)

model=ShowcaseModel();clock=VirtualClock();frames=[];shots={};audio_events=0
log=(out/'telemetry.jsonl').open('w')
def event(record):
    log.write(json.dumps(record)+'\n')
diag=Diagnostics(event,clock.now)
device=Device(model,timeout_ms=100,now_ms=model.now)
gpu=GPU(device,Audio(device),diag,FramebufferOracle(),True)
def capture(scene,frame,g):
    rgb=render(model);data=png(rgb,640,360)
    number=len(frames);(out/'frames'/('frame_%04d.png'%number)).write_bytes(data)
    frames.append({'scene':scene,'local':frame,'duration_ms':125,'png':base64.b64encode(data).decode()})
    if frame==(42 if scene==4 else scenes.FRAMES[scene]//2):
        shots[scene]=rgb
        (out/('scene_%d.png'%(scene+1))).write_bytes(png(upscale(rgb),1280,720))
Demo(gpu).run(1,capture,clock.sleep)
log.close()
contact=bytearray(1920*720*3)
for scene,rgb in shots.items():
    col,row=scene%3,scene//3
    for y in range(360):
        at=((row*360+y)*1920+col*640)*3
        contact[at:at+1920]=rgb[y*1920:(y+1)*1920]
(out/'contact-sheet.png').write_bytes(png(contact,1920,720))
with wave.open(str(out/'tiny-horizon.wav'),'wb') as wav:
    wav.setparams((2,2,48000,0,'NONE','not compressed'))
    block=bytearray(1024*4);peak=[0,0];clip=0
    for start in range(0,music.LENGTH,1024):
        n=min(1024,music.LENGTH-start)
        for i in range(n):
            l,rr=music.mix(start+i);struct.pack_into('<hh',block,i*4,l,rr)
            peak[0]=max(peak[0],abs(l));peak[1]=max(peak[1],abs(rr));clip+=int(abs(l)>=32767 or abs(rr)>=32767)
        wav.writeframesraw(memoryview(block)[:n*4])
wav_data=base64.b64encode((out/'tiny-horizon.wav').read_bytes()).decode()
html='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>KAGURA-HD — PC Mock Preview</title><style>
body{margin:0;background:#0e101c;color:#def;font:15px system-ui}main{max-width:1280px;margin:30px auto;padding:16px}
h1{letter-spacing:.05em}small{color:#8aa}button{background:#22384b;color:#def;border:1px solid #468;padding:10px;margin:4px;cursor:pointer}
img{width:100%;image-rendering:pixelated;aspect-ratio:16/9;background:#112}#status{padding:8px;color:#0df}</style>
<main><h1>KAGURA-HD <small>16 Colors, One Tiny FPGA</small></h1>
<p>PC wire-Mock preview • NOT an FPGA / HDMI capture • 640×360 framebuffer → 1280×720 • Host update target 8 Hz; HDMI nominal 60 Hz</p>
<img id="screen"><div><button id="play">Play / pause</button><button id="reset">Restart</button><span id="chapters"></span></div>
<div id="status"></div><p>Scene 6 uses original generated stereo PCM. Meters show source RMS/peak with a Host-time position estimate, not captured HDMI samples.</p>
<audio id="music" loop controls src="data:audio/wav;base64,WAVDATA"></audio></main>
<script>const frames=FRAMEDATA;const names=NAMEDATA;let i=0,running=false,timer;
const img=document.querySelector('#screen'),audio=document.querySelector('#music'),status=document.querySelector('#status');
function show(seek=false){let f=frames[i];img.src='data:image/png;base64,'+f.png;status.textContent=(f.scene+1)+'/6 — '+names[f.scene]+' — frame '+f.local;
 if(f.scene===5){if(seek||audio.paused){audio.currentTime=f.local*.125%8;if(running)audio.play().catch(()=>status.textContent+=' (press audio Play to enable sound)')}}else{audio.pause();audio.currentTime=0}}
function step(){if(!running)return;i=(i+1)%frames.length;show(i===0);timer=setTimeout(step,125)}
document.querySelector('#play').onclick=()=>{running=!running;clearTimeout(timer);show(true);if(running)timer=setTimeout(step,125);else audio.pause()};
document.querySelector('#reset').onclick=()=>{i=0;show(true)};
names.forEach((name,scene)=>{let b=document.createElement('button');b.textContent=scene+1;b.title=name;b.onclick=()=>{i=frames.findIndex(f=>f.scene===scene);show(true)};document.querySelector('#chapters').append(b)});show();</script>'''
html=html.replace('WAVDATA',wav_data).replace('FRAMEDATA',json.dumps(frames,separators=(',',':'))).replace('NAMEDATA',json.dumps(scenes.NAMES))
(out/'index.html').write_text(html)
summary={'scope':'PC behavioral wire-Mock using existing Device/Audio SDK; NOT RTL or hardware',
 'frames':len(frames),'nominal_timeline_seconds':clock.value/1000000,'hardware_update_rate_measured':False,
 'opcode_counts':diag.commands,'call_statistics_virtual_time_only':diag.calls,
 'wav':{'rate':48000,'channels':2,'bits':16,'samples':music.LENGTH,'peak':peak,'clipped_samples':clip,
 'sha256':hashlib.sha256((out/'tiny-horizon.wav').read_bytes()).hexdigest()},
 'framebuffer_oracle':'both full pages after each scene','pcm_upload':'every byte readback checked',
 'runtime_buffers_bytes':{'scanline':320,'pcm_generation':256,'pcm_verify':256,'cursor':256},
 'rp2040_heap_measured':False,'release_ready':False}
(out/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
