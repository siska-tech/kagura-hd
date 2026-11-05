"""Offline integer PCM mix, matching gain scale; never HDMI capture."""
from preview import R,SCENES
import json,wave,array
bgm=[v if v<128 else v-256 for v in (R/'generated/bgm.s8').read_bytes()];gains=[150,165,175,160,180,195,170,185];clipped=peak=0
with wave.open(str(R/'out/beyond16-pc.wav'),'wb') as w:
 w.setparams((2,2,48000,0,'NONE',''))
 for scene,(_,a,b) in enumerate(SCENES):
  fx=[v if v<128 else v-256 for v in (R/'generated'/f'fx{scene%4}.s8').read_bytes()];out=array.array('h');gain=gains[scene]
  for i in range((b-a)*48):
   v=bgm[(a*48+i)%len(bgm)]*gain*180//256
   if i<len(fx):v+=fx[i]*90*180//256
   peak=max(peak,abs(v));clipped+=int(v< -32768 or v>32767);v=max(-32768,min(32767,v));out.extend((v,v))
  w.writeframes(out.tobytes())
(R/'evidence/audio.json').write_text(json.dumps({'scope':'offline integer PCM mix; no device or hardware timing','sample_rate':48000,'channels':2,'frames':7200000,'seconds':150,'pcm0_loop_frames':len(bgm),'pcm1_events':8,'clipped_samples':clipped,'peak':peak,'hardware_underrun':None},indent=2));print('audio 150s generated, clipping',clipped)
