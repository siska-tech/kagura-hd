"""Capture-only static background index classification; not framebuffer readback."""
from pathlib import Path
import numpy as np,json
from PIL import Image
repo=Path(__file__).resolve().parents[3];app=repo/'software/midnight_terminal';ev=app/'evidence/hardware'
expected=np.asarray(Image.open(app/'generated/bar.png'))
captured=np.asarray(Image.open(ev/'bar.png').convert('RGB')).reshape(360,2,640,2,3).mean(axis=(1,3))
mask=np.zeros((360,640),bool);mask[26:255]=True;mask[119:128,120:168]=False
for x in (306,371):mask[49:94,x:x+2]=False
centers=[];labels=[]
for index in range(16):
 samples=captured[(expected==index)&mask]
 if len(samples):labels.append(index);centers.append(np.median(samples,axis=0))
centers=np.asarray(centers);nearest=np.asarray(labels)[((captured[:,:,None,:]-centers[None,None,:,:])**2).sum(axis=3).argmin(axis=2)]
score=float((nearest[mask]==expected[mask]).mean());result={'scope':'HDMI capture static bar ROI y26..254, excluding rain/eyes; per-color median capture calibration, nearest-color index comparison','roi_pixels':int(mask.sum()),'matched_pixels':int((nearest[mask]==expected[mask]).sum()),'match_fraction':score,'calibrated_rgb_centers':centers.tolist(),'not_full_framebuffer_crc':True,'release_ready':False}
(ev/'visual-comparison.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='calibrated_rgb_centers'},indent=2))
