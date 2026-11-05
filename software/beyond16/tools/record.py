"""Record actual C/SDK PC frames. This is not real-time hardware performance evidence."""
from preview import Engine,R
import subprocess,shutil,json,time
ffmpeg=shutil.which('ffmpeg');assert ffmpeg,'ffmpeg required for optional video'
out=R/'out/beyond16-pc.mp4';log=open(R/'evidence/video-encode.log','w');cmd=[ffmpeg,'-hide_banner','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','640x360','-framerate','30','-i','pipe:0','-i',str(R/'out/beyond16-pc.wav'),'-t','150','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log);e=Engine();start=time.perf_counter()
try:
 for frame in range(4500):
  e.tick(frame*1000//30);p.stdin.write(e.image().convert('RGB').tobytes())
finally:p.stdin.close()
assert p.wait()==0;log.close();(R/'evidence/video.json').write_text(json.dumps({'scope':'PC behavioral C/SDK recording; synthetic 30fps schedule, not hardware capture','frames':4500,'seconds':150,'render_seconds':time.perf_counter()-start,'bytes':out.stat().st_size,'audio':'offline original PCM mix'},indent=2));print(out)
