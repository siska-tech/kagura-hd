"""Freeze a finite, single-SRAM hardware campaign. Does not access devices."""
from pathlib import Path
import sys,json,shutil,hashlib,zlib,math
r=Path(__file__).resolve().parents[1];out=r/'build/showcase-hardware-2026-11-05-v1'
assert not out.exists(),'Never overwrite/replay a hardware campaign'
out.mkdir();(out/'control').mkdir();(out/'jobs').mkdir();(out/'expected').mkdir()
old=r/'build/upload-rmw-hardware-2026-11-05';prior=r/'build/rmw-campaign-2026-11-05-v1'
for name in ['serial_worker.py','preflight.py','release_pins.py','verify_flash.py','restore_soft_reset.py','recovery_resume.py','recovery_state.py']:
 s=(old/name).read_text();s=s.replace('build/upload-rmw-hardware-2026-11-05',str(out.relative_to(r)).replace('\\','/'))
 if name=='preflight.py':
  s="assert kagura_console.screen.device.abi==(0,6)\nassert kagura_console.last_error is None\nassert not kagura_console.paused\n"+s
  s+="\ngc.collect()\nprint('PREFLIGHT_FREE_HEAP',gc.mem_free())\nassert gc.mem_free()>=100000,'insufficient heap before RAM load; do not program'\nassert hasattr(binascii,'crc32')\n"
 (out/name).write_text(s)
shutil.copytree(r/'build/showcase/ram-loader',out/'ram-loader')
shutil.copy2(prior/'engine.py',out/'engine.py')
(out/'aliases.py').write_text("_kfb_ns=_kagura_ram['kagura_fb']._ns\n_kfb_ns['QSPITransport']=_kagura_ram['rp2040_qspi'].QSPITransport\nprint('RAM_LOADED_HEAP',gc.mem_free())\nassert gc.mem_free()>=65536\n")
identity=(old/'identity.py').read_text().replace("b'KFB1\\x01\\x02\\x7f'","b'KFB1\\x01\\x04\\xff'")
(out/'identity.py').write_text(identity)
preplan=json.loads((prior/'plan.json').read_text())
for c in preplan['cases']:shutil.copy2(prior/'jobs'/(c['id']+'.py'),out/'jobs'/(c['id']+'.py'))
(out/'runtime.py').write_text('''import time,json,gc,binascii
def _sc(record):
 print('SC '+json.dumps(record))
_q=_kagura_ram['rp2040_qspi'].QSPITransport(5)
_dev=_kagura_ram['kagura_fb'].Device(_q,timeout_ms=3000)
_aud=_kagura_ram['kagura_fb_audio'].Audio(_dev)
_diag=_kagura_ram['showcase.diagnostics'].Diagnostics(_sc)
_g=_kagura_ram['showcase.gpu_api_adapter'].GPU(_dev,_aud,_diag,verify=False)
_scenes=_kagura_ram['showcase.scenes']
_music=_kagura_ram['showcase.music']
_scene_state=None
def _hdhealth(tid):
 _g.health()
 _sc({'event':'health','id':tid,'status':_q.read(27,False,1)[0],'error':_q.read(7,False,1)[0],
  'pcm':[_aud.pcm_status(0),_aud.pcm_status(1)],'free_heap':gc.mem_free()})
def _graphics_enter(index):
 global _scene_state
 _g.palette((0,)*16);_g.present(_g.page)
 _scene_state=_scenes.enter(_g,index)
 if index==3:
  _g.fill(0,552,294,48,24,9);_g.fill(1,552,294,48,24,13)
def _graphics_tick(index,start,end):
 for f in range(start,end+1):_scenes.tick(_g,index,_scene_state,f);_g.health()
def _check_crc(tid,page,expected):
 actual=_g.crc(page)
 _sc({'event':'framebuffer_crc','id':tid,'page':page,'expected':expected,'actual':actual})
 assert actual==expected,'framebuffer CRC mismatch; STOP'
def _tone(mode,tone0,tone1):
 _music.quiesce(_g)
 for c in (0,1):_aud.pcm_clear(c)
 if mode==0:
  for c in (0,1):_aud.pcm_enable(c,False)
  _aud.commit();return
 _g.write(0x80000,bytes.fromhex(tone0));_g.write(0xe0000,bytes.fromhex(tone1));_dev.fence()
 for c,h in ((0,tone0),(1,tone1)):
  actual=_dev.read_bytes((0x80000,0xe0000)[c],192)
  assert actual==bytes.fromhex(h),'tone upload mismatch'
 gains=(((160,0),(0,0)),((0,0),(0,160)),((160,32),(32,160)))[mode-1]
 for c in (0,1):
  _aud.pcm_configure(c,(0x80000,0xe0000)[c],(0x80000,0xe0000)[c]+192,loop=(0x80000,0xe0000)[c],
   gain_left=gains[c][0],gain_right=gains[c][1],enabled=(mode==3 or c==mode-1))
  _aud.pcm_prepare(c)
 _aud.master(160);_aud.commit()
_hdhealth('runtime')
''')
sys.path[:0]=[str(r/'software/kagura_fb'),str(r/'software/kagura_fb/tests')]
from kagura_fb import Device
from kagura_fb_audio import Audio
from showcase.gpu_api_adapter import GPU,PALETTE
from showcase.pc_mock import ShowcaseModel,VirtualClock
from showcase.framebuffer_oracle import FramebufferOracle
from showcase.diagnostics import Diagnostics
from showcase import scenes,music
m=ShowcaseModel();clk=VirtualClock();dev=Device(m,now_ms=m.now);g=GPU(dev,Audio(dev),Diagnostics(clock=clk.now),FramebufferOracle())
def crc(page):
 pixels=g.oracle.pages[page];packed=bytes((pixels[i]<<4)|pixels[i+1] for i in range(0,len(pixels),2))
 return zlib.crc32(packed)&0xffffffff
def snapshot(tid):
 palette=m.active_palette;pixels=g.oracle.pages[g.page];rois=[];colors=set()
 for y in range(90,325,18):
  for x in range(48,602,24):
   index=pixels[y*640+x]
   if all(pixels[yy*640+xx]==index for yy in range(y-4,y+5) for xx in range(x-4,x+5)):
    color=palette[index];rgb=[(color>>8)*17,((color>>4)&15)*17,(color&15)*17]
    if color not in colors:rois.append([x,y,rgb]);colors.add(color)
 if len(rois)<4:
  for x,y in [(16,80),(16,320),(620,320)]:
   color=palette[pixels[y*640+x]];rois.append([x,y,[(color>>8)*17,((color>>4)&15)*17,(color&15)*17]])
 cursor=[]
 if m.cursor_visible:
  x,y,bank,_=m.cursor_position;hx,hy=m.cursor_hotspots[bank];cp=m.cursor_palettes[bank]
  for yy in range(0,32,2):
   for xx in range(0,32,2):
    px,py=x-hx+xx,y-hy+yy;idx=(m.cursor_assets[bank][yy*8+xx//4]>>(6-2*(xx%4)))&3
    if idx and 0<=px<640 and 0<=py<360:
     c=cp[(idx-1)*2]|cp[(idx-1)*2+1]<<8
     cursor.append([px,py,[(c>>8)*17,((c>>4)&15)*17,(c&15)*17]])
 if tid.startswith('G4'):rois.append([576,306,[(palette[(9,13)[g.page]]>>8)*17,((palette[(9,13)[g.page]]>>4)&15)*17,(palette[(9,13)[g.page]]&15)*17]])
 return {'rois':rois,'cursor_points':cursor,'page':g.page,'crc':[crc(0),crc(1)]}
graphics=[]
for scene,ends in [(0,[9]),(1,[23,47]),(2,[11,23,47]),(3,[23,47]),(4,[5,23,42,47])]:
 g.palette((0,)*16);g.present(g.page);st=scenes.enter(g,scene)
 if scene==3:g.fill(0,552,294,48,24,9);g.fill(1,552,294,48,24,13)
 cursor_before=[crc(0),crc(1)] if scene==4 else None
 start=0
 for n,end in enumerate(ends):
  tid='G%d-%02d'%(scene+1,end)
  source=('_graphics_enter(%d)\n'%scene if n==0 else '')+'_graphics_tick(%d,%d,%d)\n_hdhealth(%r)\n'%(scene,start,end,tid)
  for f in range(start,end+1):scenes.tick(g,scene,st,f)
  expected=snapshot(tid)
  (out/'jobs'/(tid+'.py')).write_text(source)
  do_crc=(end==ends[-1] or scene==3)
  graphics.append({'id':tid,'job':tid+'.py','expected':expected,'crc_check':do_crc})
  start=end+1
 if scene==4:assert cursor_before==[crc(0),crc(1)]
 scenes.leave(g,scene,st)
 (out/'jobs'/('G%d-leave.py'%(scene+1))).write_text('_scenes.leave(_g,%d,_scene_state)\n_hdhealth(%r)\n'%(scene,'G%d-leave'%(scene+1)))
tones=[]
for freq,amp in [(1000,64),(1500,48)]:tones.append(bytes(round(amp*math.sin(2*math.pi*freq*i/48000))&255 for i in range(192)).hex())
for mode in range(4):
 (out/'jobs'/('A%d.py'%mode)).write_text('_tone(%d,%r,%r)\n_hdhealth(%r)\n'%(mode,*tones,'A%d'%mode))
guard=[{'address':a,'data':bytes((i*17+0x53)&255 for i in range(16)).hex()} for a in (0x7fff0,0xddc00,0xdfff0,0x13dc00)]
(out/'jobs'/'BGM-init.py').write_text("_music.quiesce(_g)\n"+'\n'.join("_dev.write_bytes(%d,bytes.fromhex(%r));assert _dev.read_bytes(%d,16)==bytes.fromhex(%r)"%(x['address'],x['data'],x['address'],x['data']) for x in guard)+"\n_hdhealth('BGM-init')\n")
chunks=[]
for channel in (0,1):
 for offset in range(0,music.LENGTH,32768):
  length=min(32768,music.LENGTH-offset);data=bytes(music.sample(channel,offset+i)&255 for i in range(length));expected=zlib.crc32(data)&0xffffffff
  tid='BGM-%d-%06d'%(channel,offset)
  code="_block=bytearray(256)\nfor _pos in range(%d,%d,256):\n _music.fill_block(%d,_pos,_block);_g.write(%d+_pos,_block)\n"%(offset,offset+length,channel,music.BASES[channel])
  code+="_read=bytearray(64);_crc=0\nfor _pos in range(%d,%d,64):\n _dev.read_into(%d+_pos,_read);_crc=binascii.crc32(_read,_crc)\n"%(offset,offset+length,music.BASES[channel])
  code+="_sc({'event':'pcm_crc','id':%r,'channel':%d,'offset':%d,'length':%d,'expected':%d,'actual':_crc&0xffffffff})\nassert (_crc&0xffffffff)==%d,'PCM CRC mismatch'\n"%(tid,channel,offset,length,expected,expected)
  code+='\n'.join("assert _dev.read_bytes(%d,16)==bytes.fromhex(%r),'PCM guard mismatch'"%(x['address'],x['data']) for x in guard)
  code+="\ngc.collect();_hdhealth(%r)\n"%tid
  (out/'jobs'/(tid+'.py')).write_text(code);chunks.append({'id':tid,'job':tid+'.py','channel':channel,'offset':offset,'length':length,'crc32':expected})
(out/'jobs'/'BGM-play.py').write_text("_scene_state=_scenes.enter(_g,5)\nfor _i in range(8):_scenes.tick(_g,5,_scene_state,_i);_g.health()\n_hdhealth('BGM-play')\n")
(out/'jobs'/'BGM-stop.py').write_text("_scenes.leave(_g,5,_scene_state)\n_hdhealth('BGM-stop')\n")
(out/'jobs'/'FULL.py').write_text("_g.verify_reads=True\n_demo=_kagura_ram['showcase.scene_manager'].Demo(_g)\n_demo.prepared=True\n_demo.run(cycles=1)\n_hdhealth('FULL')\n")
plan={'id':'SHOWCASE-HW-01','bitstream_sha256':'642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7',
 'sram_programs_max':1,'retries':0,'campaign_max_seconds':3600,'job_max_seconds':120,'full_loop_max_seconds':900,
 'command_timeout_ms':3000,'transport_half_period_us':5,'memory_cases':preplan['cases'],'scratch':[299968,326143],
 'graphics':graphics,'tone_hex':tones,'bgm_chunks':chunks,'bgm_guards':guard,
 'rgb_component_tolerance':50,'cursor_color_tolerance':60,'cursor_match_minimum':0.8,
 'audio':{'capture_seconds':3,'discard_seconds':0.25,'silence_rms_max':8,'frequency_search_hz':3,'search_step_hz':0.25,'amplitude_relative_tolerance':0.25,'pan_ratio':5,'pan_ratio_relative_tolerance':0.15,'muted_rms_max_floor':20,'muted_rms_relative_max':0.01,'explained_energy_minimum':0.85},
 'recovery_fpga_file_hash_exception':'Prior user waiver retained; use known existing Flash Reprogram, do not load alternative recovery fs',
 'capture_audio_limit':'Functional amplitude/frequency/pan only; UGREEN is not bit transparent','release_ready':False,'flash_fw_filesystem_writes':False}
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
(out/'DO_NOT_RELEASE.txt').write_text('release_ready=false. One authorized SRAM candidate, no Flash/FW/filesystem writes. No replay.\n')
print('Prepared',len(plan['memory_cases']),'memory cases,',len(graphics),'graphics snapshots,',len(chunks),'PCM chunks; no hardware access')
