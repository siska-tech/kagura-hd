"""Reproducible BDF subset, indexed pixel art and original PCM. No system fonts."""
from pathlib import Path
import sys, json, hashlib, re, math, struct, wave, zipfile, tarfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'.deps'))
from PIL import Image, ImageDraw
OUT=ROOT/'generated'; OUT.mkdir(exist_ok=True)
if (ROOT/'vendor/provenance.json').exists():
    for filename,entry in json.loads((ROOT/'vendor/provenance.json').read_text()).items():
        assert hashlib.sha256((ROOT/'vendor'/filename).read_bytes()).hexdigest()==entry['sha256'], f'font source changed: {filename}'
story=json.loads((ROOT/'story.json').read_text(encoding='utf-8'))
PAL=['090d19','141b30','23243f','393453','56506b','80738b','b9afbe','ece8db','223e55','326b7e','58a6aa','9edacb','5e3563','a45283','e18aaa','673443']
palette=[tuple(round(v/17)*17 for v in bytes.fromhex(x)) for x in PAL]
(OUT/'palette.inc').write_text('static const uint16_t normal_pal[16]={'+','.join(hex((r//17<<8)|(g//17<<4)|(b//17)) for r,g,b in palette)+'};\n')
def bdf(path):
    text=path.read_text(encoding='ascii',errors='replace'); ascent=int(re.search(r'FONT_ASCENT (\d+)',text)[1]); height=ascent+int(re.search(r'FONT_DESCENT (\d+)',text)[1]); glyph={}
    jis='jisx0208' in text.split('STARTCHAR')[0]; kana='jisx0201' in text.split('STARTCHAR')[0]
    for g in text.split('STARTCHAR ')[1:]:
        code=int(re.search(r'ENCODING (\d+)',g)[1]); adv=int(re.search(r'DWIDTH (\d+)',g)[1]); w,h,x,y=map(int,re.search(r'BBX ([-\d ]+)',g)[1].split())
        try:
            if jis: cp=ord(bytes([code//256+128,code%256+128]).decode('euc_jp'))
            elif kana: cp=ord(bytes([code]).decode('shift_jis'))
            else: cp=code
        except (UnicodeError, ValueError): continue
        rows=g.split('BITMAP\n')[1].split('ENDCHAR')[0].split(); im=Image.new('1',(adv,height))
        for yy,s in enumerate(rows):
            bits=int(s,16); n=len(s)*4
            for xx in range(w):
                dx=x+xx; dy=ascent-y-h+yy
                if 0<=dx<adv and 0<=dy<height and bits&(1<<(n-1-xx)): im.putpixel((dx,dy),1)
        glyph[cp]=(adv,height,im)
    return glyph
with zipfile.ZipFile(ROOT/'vendor/misaki.zip') as z: z.extractall(ROOT/'vendor/misaki')
with tarfile.open(ROOT/'vendor/mplus.tar.xz') as t: t.extractall(ROOT/'vendor/mplus',filter='data')
mp=ROOT/'vendor/mplus/xfonts-mplus-2.2.4'
normal=bdf(mp/'fonts_j/mplus_j12r.bdf'); normal.update(bdf(mp/'fonts_e/mplus_f12r.bdf'))
# JIS X0201 halfwidth kana uses original M+ diff rows, applied offline.
import subprocess, shutil
# Apply the original context diff without an external patch dependency.
base=(mp/'fonts_e/mplus_f12r.bdf').read_text().splitlines()
diff=(mp/'fonts_j/mplus_f12r-jisx0201.diff').read_text().splitlines()
result=[]; cursor=0; i=0
while i<len(diff):
    m=re.match(r'\*\*\* (\d+)(?:,(\d+))? \*\*\*\*',diff[i])
    if not m: i+=1; continue
    start=int(m[1])-1; end=int(m[2] or m[1]); result.extend(base[cursor:start]); cursor=end
    i+=1
    while not re.match(r'--- \d',diff[i]): i+=1
    i+=1
    while i<len(diff) and not diff[i].startswith('***************'):
        if diff[i][:2] in ('  ','+ ','! '): result.append(diff[i][2:])
        i+=1
result.extend(base[cursor:]); p=OUT/'kana.bdf'; p.write_text('\n'.join(result)+'\n')
normal.update(bdf(p))
misaki=bdf(ROOT/'vendor/misaki/misaki_gothic.bdf')
alltext=''.join(s for group in story.values() for s in (group if isinstance(group,list) else [group]))
required=sorted(set(map(ord,alltext+' '+''.join(chr(i) for i in range(33,127)))))
fonts=[]; manifest={}
for name,source,H in [('mplus',normal,13),('misaki',misaki,8)]:
    missing=[chr(c) for c in required if c not in source]; manifest[name]={'height':H,'missing':missing,'glyphs':len(required),'advances':sorted(set(v[0] for v in source.values()))}
    if missing: raise RuntimeError(f'{name} missing {missing}')
    records=[]; atlas=Image.new('P',(256,((len(required)+15)//16)*H)); atlas.putpalette(sum((list(c) for c in palette),[])+[0]*(768-48))
    for i,cp in enumerate(required):
        adv,h,im=source[cp]; rows=[]
        for y in range(H): rows.append(sum((1<<(15-x)) for x in range(adv) if im.getpixel((x,y))))
        records.append('{%du,%d,{%s}}'%(cp,adv,','.join(str(x) for x in rows+[0]*(13-H))))
        atlas.paste(7,(i%16*16,i//16*H),im)
    atlas.save(OUT/f'{name}-atlas.png')
    fonts.append('const mt_glyph mt_%s[%d]={\n%s\n};'%(name,len(required),',\n'.join(records)))
    (OUT/f'{name}-font.inc').write_text(fonts[-1],encoding='utf-8')
if '--font' in sys.argv:
    selected=sys.argv[sys.argv.index('--font')+1]
    assert selected in ('mplus','misaki')
    print(json.dumps(manifest[selected],ensure_ascii=False));print(OUT/f'{selected}-font.inc');sys.exit(0)
def text(im,pos,s,font=normal,color=7,scale=1):
    x,y=pos
    for ch in s:
        adv,h,g=font[ord(ch)]; mask=g.resize((adv*scale,h*scale),Image.Resampling.NEAREST); im.paste(color,(x,y),mask); x+=adv*scale
def canvas():
    im=Image.new('P',(640,360)); im.putpalette(sum((list(c) for c in palette),[])+[0]*(768-48)); return im
im=canvas(); d=ImageDraw.Draw(im)
d.rectangle((0,26,639,254),fill=1)
# City, behind rain-streaked glass.
d.rectangle((275,38,620,224),fill=0)
for i in range(17):
    x=282+i*20; top=64+(i*37)%83; d.rectangle((x,top,x+16,222),fill=[2,8,3][i%3])
    for yy in range(top+7,216,11):
        for xx in range(x+3,x+15,6):
            if (xx*yy+i)%5<2:d.rectangle((xx,yy,xx+1,yy+2),fill=9 if i%3 else 12)
d.rectangle((285,172,618,222),fill=8)
for y in range(176,224,5):d.line((285,y,618,y),fill=1 if y%2 else 2)
for x in (274,450,622):d.rectangle((x,34,x+4,231),fill=4); d.line((x+1,35,x+1,226),fill=8)
d.line((276,126,622,126),fill=4)
for i in range(48):
    x=284+(i*79)%328; y=43+(i*41)%174; d.line((x,y,x-3,y+13),fill=9)
# neon sign, editable geometric asset
d.rectangle((477,58,596,104),fill=2,outline=12,width=2); d.rectangle((480,61,593,101),outline=13)
text(im,(489,70),'NOCT / 09',color=14); text(im,(498,86),'OPEN LATE',color=10)
# shelves, bottles and warm hanging lamps
d.rectangle((14,44,252,193),fill=2)
for y in (92,150,194):d.rectangle((14,y,252,y+4),fill=4)
for i in range(16):
    x=21+(i%8)*29; y=66+(i//8)*57; c=[8,12,9,15][i%4]
    d.rectangle((x+4,y,x+9,y+7),fill=c);d.rectangle((x,y+8,x+13,y+25),fill=c);d.rectangle((x+2,y+14,x+11,y+20),fill=5)
for x in (72,240):
    d.line((x,26,x,46),fill=5);d.polygon([(x-17,58),(x-7,45),(x+7,45),(x+17,58)],fill=12);d.line((x-16,59,x+16,59),fill=14)
# Original attendant Mio: clean pixel silhouette, hair, face, apron, hands.
d.ellipse((94,64,196,159),fill=0);d.polygon([(94,121),(97,87),(113,64),(161,59),(187,78),(202,150),(180,174),(99,157)],fill=3)
d.polygon([(111,93),(173,86),(182,116),(174,148),(154,162),(129,154),(113,134)],fill=6)
d.polygon([(99,111),(107,77),(146,65),(179,77),(185,108),(167,91),(151,112),(144,86),(129,110),(119,96),(111,125)],fill=2)
d.line((109,83,141,69,170,78),fill=12,width=3);d.rectangle((176,99,181,123),fill=13);d.rectangle((178,113,184,117),fill=10)
d.line((121,122,132,120),fill=3,width=2);d.line((154,119,166,121),fill=3,width=2);d.rectangle((126,122,129,125),fill=9);d.rectangle((157,122,160,125),fill=9)
d.line((143,127,140,136,145,136),fill=5);d.line((137,145,149,145),fill=15)
d.polygon([(129,153),(127,170),(96,176),(73,231),(209,231),(187,176),(157,167),(155,155),(144,167)],fill=8)
d.polygon([(116,176),(141,187),(168,175),(182,230),(103,230)],fill=4);d.line((117,177,141,189,166,177),fill=10,width=2)
d.rectangle((132,199,158,214),fill=2); text(im,(136,200),'MIO',color=11)
d.polygon([(83,215),(100,216),(123,231),(99,235),(79,228)],fill=6);d.polygon([(184,215),(199,215),(209,228),(188,235),(170,232)],fill=6)
# counter, terminal, glass and reflections
d.rectangle((0,234,639,254),fill=3);d.line((0,234,639,234),fill=13,width=2);d.line((0,238,639,238),fill=5)
for x in range(12,640,61):d.line((x,248,x+28,248),fill=12)
d.polygon([(478,196),(556,196),(568,234),(472,234)],fill=4);d.rectangle((484,180,556,220),fill=2,outline=5,width=2);d.rectangle((489,185,551,214),fill=8)
text(im,(495,190),'WAIT',color=11);d.line((495,207,540,207),fill=10)
d.rectangle((345,210,362,232),outline=10,width=2); d.rectangle((347,220,360,229),fill=12);d.line((344,209,363,209),fill=11)
# UI
d.rectangle((0,0,639,25),fill=0);text(im,(16,6),'MIDNIGHT TERMINAL',color=11);text(im,(429,6),'00:47 / NIGHT SERVICE',color=5);d.line((0,25,639,25),fill=9)
d.rectangle((8,262,631,351),fill=1,outline=9);d.rectangle((11,265,628,348),outline=3);d.rectangle((22,257,146,275),fill=8);text(im,(30,260),'店員 / ミオ',color=11)
text(im,(497,333),'ENTER / NEXT',color=5)
im.save(OUT/'bar.png')
for name,box in {'attendant':(70,59,211,234),'window':(274,34,627,232),'neon':(477,58,597,105),'terminal':(472,180,569,235),'dialogue-ui':(8,257,632,352),'logo':(12,0,240,25)}.items():im.crop(box).save(OUT/f'{name}.png')
face=im.crop((120,119,168,128));fd=ImageDraw.Draw(face);fd.rectangle((0,0,47,8),fill=6);fd.line((3,5,13,5),fill=3);fd.line((35,5,45,5),fill=3);face.save(OUT/'expression-blink.png')
face=im.crop((120,119,168,128));fd=ImageDraw.Draw(face);fd.rectangle((5,3,10,7),fill=11);fd.rectangle((35,3,40,7),fill=11);face.save(OUT/'expression-anomaly.png')
# all binary assets use high nibble at even X, row stride 320, opaque COPY only.
def packed(im):
    a=list(im.get_flattened_data()); return bytes((a[i]<<4)|a[i+1] for i in range(0,len(a),2))
bar=packed(im); (OUT/'bar.4bpp').write_bytes(bar)
warn=canvas()
for row in range(44):
    # exactly 80 eight-pixel cells; ASCII expanded into 8-cell too.
    s=f'{row:02X} '+story['logs'][row%len(story['logs'])]+' // '+story['logs'][(row*7+3)%len(story['logs'])]+' // '
    s=(s*4)[:80]
    for col,ch in enumerate(s):
        g=misaki[ord(ch)][2];warn.paste(13 if (col//8+row)%13==0 else (11 if row%5==0 else 7),(col*8,8+row*8),g)
text(warn,(8,0),'FICTION / 架空ログ',misaki,11)
warn.save(OUT/'warning.png'); warning=packed(warn);(OUT/'warning.4bpp').write_bytes(warning)
def pcm(duration,kind):
    n=round(duration*48000); out=bytearray(n)
    for i in range(n):
        t=i/48000
        if kind=='bgm':
            beat=int(t*2); f=[130.8128,155.5635,174.6141,116.5409][beat//4%4]; phase=t%0.5
            v=14*math.sin(2*math.pi*f*t)+7*math.sin(2*math.pi*f*1.5*t)+10*math.exp(-phase*9)*math.sin(2*math.pi*f*4*t)
            v*=min(1,t*5,(duration-t)*5)
        else:
            f={'select':740,'talk':920,'alarm':196,'restore':523}[kind]; v=42*math.sin(2*math.pi*(f*t+70*t*t))*math.exp(-t*(12 if kind!='alarm' else 5))*min(1,t*500)
        out[i]=max(-127,min(127,round(v)))&255
    return bytes(out)
sounds={k:pcm(d,k) for k,d in [('bgm',8),('select',.14),('talk',.035),('alarm',.3),('restore',.24)]}
for k,v in sounds.items():
    (OUT/f'{k}.s8').write_bytes(v)
    with wave.open(str(OUT/f'{k}.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b''.join(struct.pack('<h',(b if b<128 else b-256)*256) for b in v))
def array(name,data):return 'const uint8_t '+name+'['+str(len(data))+']={\n'+',\n'.join(','.join(str(x) for x in data[i:i+64]) for i in range(0,len(data),64))+'\n};\n'
(OUT/'assets.inc').write_text('\n'.join(fonts)+array('mt_bar',bar)+array('mt_warning',warning)+''.join(('#ifndef MT_COMPRESSED_BGM\n'+array('mt_pcm_'+k,v)+'#endif\n') if k=='bgm' else array('mt_pcm_'+k,v) for k,v in sounds.items()),encoding='utf-8')
(OUT/'story.inc').write_text('\n'.join('const char *const mt_'+k+'[]={'+','.join(json.dumps(s,ensure_ascii=False) for s in v)+'};' for k,v in story.items() if isinstance(v,list))+'\nconst char mt_last[]='+json.dumps(story['last'],ensure_ascii=False)+';\n',encoding='utf-8')
(OUT/'counts.h').write_text(f'#define MT_GLYPHS {len(required)}\n')
(OUT/'font-report.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
sources={'misaki.zip':'https://littlelimit.net/arc/misaki/misaki_bdf_2021-05-05.zip','mplus.tar.xz':'https://deb.debian.org/debian/pool/main/x/xfonts-mplus/xfonts-mplus_2.2.4.orig.tar.xz'}
provenance={k:{'url':v,'sha256':hashlib.sha256((ROOT/'vendor'/k).read_bytes()).hexdigest()} for k,v in sources.items()}
for p in [mp/'LICENSE_E',mp/'LICENSE_J',ROOT/'vendor/misaki/misaki.txt']:shutil.copy(p,ROOT/'vendor'/p.name)
(ROOT/'vendor/provenance.json').write_text(json.dumps(provenance,indent=2))
(OUT/'palette.json').write_text(json.dumps(palette))
print(json.dumps(manifest,ensure_ascii=False)); print('Generated original indexed bar, 3520-cell warning page and 5 PCM assets')

