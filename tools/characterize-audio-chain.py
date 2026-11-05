"""Quantify saved A0 versus calibration; no capture, no regrading."""
from pathlib import Path
import hashlib,json,wave
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1];out=root/'build/ugreen-audio-calibration-2026-11-05'
analysis=json.loads((out/'analysis.json').read_text());original=root/'build/rmw-campaign-2026-11-05-v1/A0.wav'
def read(p):
 with wave.open(str(p),'rb') as f:return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).astype(float)
a0=read(original);d0=a0[:,0]-a0[:,1];ks=np.arange(-16,17)
def metric(d):
 hist=np.array([np.mean(d==k) for k in ks]);center=d-d.mean()
 return dict(rms=float(np.sqrt(np.mean(d*d))),within2=float(np.mean(abs(d)<=2)),
  lag1=float(center[:-1]@center[1:]/(center@center)),histogram=hist.tolist())
base=metric(d0);rows=[]
for row in analysis['rows']:
 cap=read(out/(row['id']+'.wav'));d=cap[:,0]-cap[:,1];m=metric(d)
 p=np.array(base['histogram']);q=np.array(m['histogram']);mid=(p+q)/2
 def kl(a,b):
  selected=a>0;return float(np.sum(a[selected]*np.log2(a[selected]/b[selected])))
 result=dict(id=row['id'],reference=row['reference'],path=row['path'],metrics=m,
  rms_ratio_to_original=m['rms']/base['rms'],within2_delta_percentage_points=100*(m['within2']-base['within2']),
  histogram_total_variation=float(abs(p-q).sum()/2),histogram_js_bits=(kl(p,mid)+kl(q,mid))/2)
 if 'alignment' in row and row['reference'] in ('quiet_prng','medium_prng','a0_common_dual_mono'):
  blocks=row['alignment']['local_blocks'];x=np.array([b['capture_start'] for b in blocks]);y=np.array([b['offset_samples'] for b in blocks])
  fit=np.polyfit(x,y,1);res=y-np.polyval(fit,x)
  result['alignment_drift']=dict(source_offset_slope_ppm=float(fit[0]*1e6),offset_range_samples=float(np.ptp(y)),
    affine_residual_rms_samples=float(np.sqrt(np.mean(res*res))),
    interpretation='Integer alignment drift in saved PCM; compatible with independent clock/resampling. Not a physical-clock measurement.')
 rows.append(result)
report=dict(original_a0=base,comparisons=rows,
  conclusion='The FPGA-disconnected PC-to-UGREEN path reproduces A0-scale channel differences. Exact sample qualification failed for both paths; FPGA audio campaign and Stage7 remain unstarted.',
  prior_gate='Original A0 FAIL unchanged',physical_source_bits_independently_observed=False)
(out/'characterization.json').write_text(json.dumps(report,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
selected=[('Original FPGA A0',base,'#222222')]
for name,color in [('DirectShow_AV_original-02','#aa4b23'),('WASAPI_exclusive-02','#176b9b')]:
 row=next(r for r in rows if r['id']==name);selected.append((name,row['metrics'],color))
for name,m,color in selected:axes[0].plot(ks,np.array(m['histogram'])*100,marker='o',lw=1,label=name,color=color)
axes[0].set(xlim=(-8,8),xlabel='L-R (signed 16-bit LSB)',ylabel='Samples (%)',title='A0 and known dual-mono calibration distributions');axes[0].legend(fontsize=8)
for id_,color in [('DirectShow_AV_original-03','#aa4b23'),('WASAPI_exclusive-03','#176b9b')]:
 row=next(r for r in analysis['rows'] if r['id']==id_);b=row['alignment']['local_blocks']
 x=np.array([v['capture_start']/48000 for v in b]);y=np.array([v['offset_samples'] for v in b]);axes[1].plot(x,y-y[0],marker='.',lw=1,label=id_,color=color)
axes[1].set(xlabel='Capture time (s)',ylabel='Reference offset change (samples)',title='Known PRNG: integer alignment drifts over time');axes[1].legend(fontsize=8)
for ax in axes:ax.spines[['top','right']].set_visible(False)
fig.savefig(out/'a0-versus-calibration.png',dpi=170);fig.savefig(out/'a0-versus-calibration.pdf');plt.close(fig)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'evidence-sha256.json').write_text(json.dumps({p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
print(json.dumps([r for r in rows if r['reference'] in ('a0_common_dual_mono','quiet_prng')],indent=2))
