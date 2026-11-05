from pathlib import Path
import subprocess,json
out=Path('software/beyond16/out/youtube');source='build/beyond16-host-ab-2026-11-06/ON/demo-hdmi.mkv'
clips=[(0,4),(14,8),(34,8),(54,8),(76,8),(100,8),(125,8),(144,6)]
f=[]
for i,(start,duration) in enumerate(clips):
 a=3.76+start;b=a+duration
 f += [f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]',f'[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]']
f += [''.join(f'[v{i}][a{i}]' for i in range(len(clips)))+f'concat=n={len(clips)}:v=1:a=1[v][a]','[v]scale=1080:608:flags=neighbor,pad=1080:1920:0:656:color=black,setsar=1[vertical]']
(out/'highlights-edit.json').write_text(json.dumps({'source':source,'source_audio_onset_s':3.76,'clips_timeline_start_duration_s':clips,'duration_s':58,'canvas':[1080,1920],'picture':[1080,608],'top_bottom_margin_px':656,'source':'physical HDMI capture, frame repeats retained'},indent=2))
with (out/'highlights-encode.log').open('wb') as log:subprocess.run(['ffmpeg','-hide_banner','-y','-i',source,'-filter_complex',';'.join(f),'-map','[vertical]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(out/'KAGURA-HD_BEYOND-16-COLORS_vertical-58s.mp4')],stderr=log,stdout=log,check=True)
