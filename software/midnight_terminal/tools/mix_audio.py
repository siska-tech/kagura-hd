"""Render C-engine PCM0/PCM1 events to a PC listening WAV (no HDMI claim)."""
import array,json,wave,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
events=json.loads((ROOT/'out/audio-events.json').read_text());names=['bgm','select','talk','alarm','restore'];data=[]
for name in names:
 a=array.array('b');a.frombytes((ROOT/f'generated/{name}.s8').read_bytes());data.append(a)
channels=[array.array('i',[0])*4224000 for _ in range(2)]
state=[None,None]
def render(ch,end):
 if state[ch] is None:return
 sound,start,gain,phase=state[ch];source=data[sound];start_sample=round(start*48);finish=min(4224000,round(end*48));dst=channels[ch]
 for i in range(start_sample,finish):
  off=i-start_sample
  if ch and off>=len(source):break
  dst[i]=source[(off+phase)%len(source)]*gain
for ms,sound,gain in events:
 if sound<0:
  for ch in range(2):render(ch,ms);state[ch]=None
 else:
  ch=0 if sound==0 else 1;old=state[ch];render(ch,ms);phase=(old[3]+round((ms-old[1])*48))%len(data[0]) if sound==0 and old else 0;state[ch]=(sound,ms,gain,phase)
for ch in range(2):render(ch,88000)
out=array.array('h')
for a,b in zip(*channels):
 v=max(-32768,min(32767,((a+b)*180)>>8));out.extend((v,v))
if sys.byteorder!='little':out.byteswap()
with wave.open(str(ROOT/'out/midnight-terminal-pc-mix.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(out.tobytes())
print('88 seconds / signed16 stereo / original 48kHz signed8 sources; PC mix only')

