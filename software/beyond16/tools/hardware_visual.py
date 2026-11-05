from pathlib import Path
import sys,json
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'out/analysis-deps'),str(R.parent/'midnight_terminal/.deps')]
import numpy as np
from PIL import Image
ref=np.asarray(Image.open(R/'generated/frame-atlas.png'));roi=np.zeros((360,640),bool);roi[:80]=True;roi[320:]=True;rows=[]
for scene in range(8):
 im=np.asarray(Image.open(R/'evidence/hardware'/f'{scene:02}-hardware.png').convert('RGB')).reshape(360,2,640,2,3).mean(axis=(1,3));centers=np.array([np.median(im[roi&(ref==i)],axis=0) if np.any(roi&(ref==i)) else [-999]*3 for i in range(16)]);error=np.max(np.abs(im-centers[ref]),axis=2);score=float(np.mean(error[roi]<=24));rows.append({'scene':scene,'static_roi_pixels':int(roi.sum()),'within_24_rgb_fraction':score,'median_channel_error':float(np.median(error[roi])),'scope':'static header/source-bank calibrated RGB shape consistency; excludes dynamic stage; not raw framebuffer CRC'})
(R/'evidence/hardware/visual-comparison.json').write_text(json.dumps(rows,indent=2));print(rows)
