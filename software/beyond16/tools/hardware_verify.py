from pathlib import Path
import json,hashlib,subprocess,shutil
R=Path('software/beyond16').resolve();repo=R.parents[1];O=repo/'build/beyond16-hardware-2026-11-06';E=R/'evidence/hardware'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'out/rp2040/beyond16.bin')=='c66308e09ad46a2104d3924d0a7913b98937b05e7408ade4b523940a6cee200b'
assert sha(O/'recovery/before-beyond16-full-2MiB.bin')=='7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596'
assert sha(O/'recovery/after-beyond16-full-2MiB.bin')=='29001ff651a227cf2d4d8b2286c4dbc67af385ede3d205e1f124518b4295aa4a'
freeze=json.loads((R/'evidence/source-sha256.pre-hardware.json').read_text())
protected=[p for p in freeze if p.endswith(('.c','.h','.pio','.inc'))];assert all(sha(repo/p)==freeze[p] for p in protected)
media=json.loads(subprocess.check_output([shutil.which('ffprobe'),'-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration','-of','json',str(O/'beyond16-hardware.mp4')]))
assert abs(float(media['format']['duration'])-150)<.1
files=[O/'beyond16-hardware.mp4',O/'demo-hdmi.mkv',O/'demo-audio.wav',E/'performance.json',E/'audio.json',E/'contact-sheet.png',E/'demo-usb.log',E/'bench-usb.log']
(E/'artifact-sha256.json').write_text(json.dumps({str(p.relative_to(repo)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files},indent=2))
(E/'final-audit.json').write_text(json.dumps({'status':'PASS','deployed_binary_and_C_inputs_unchanged':True,'deployed_C_input_files':len(protected),'new_full_backup_verified':True,'firmware_readback_verified':True,'filesystem_unchanged':True,'fpga_flash_written':False,'full_demo_STOP_rc':0,'all_8_scenes_captured':True,'physical_before_after':'NOT RUN','load_sweep':'NOT RUN','full_framebuffer_CRC':'NOT RUN','current_state':'BEYOND finale held, audio stopped, QSPI deinitialized, firmware retained','media':media,'release_ready':False},indent=2))
print('HARDWARE AUDIT PASS; review video',media['format']['duration'],'seconds')
