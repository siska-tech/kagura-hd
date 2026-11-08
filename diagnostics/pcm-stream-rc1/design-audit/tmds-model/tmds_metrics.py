import sys
sys.path.insert(0, sys.argv[2]); from tmds_model_lib import enc_stream
root=sys.argv[1]
frame=[int(x,16) for x in open(root+'/frame.hex')]; pal=[int(x,16) for x in open(root+'/palette.hex')]
e=lambda v:(((v>>8)&15)*17,((v>>4)&15)*17,(v&15)*17)
def metrics(rows):
    se=pt=dist=0; n=0; runs=0; maxrun=0; chars=set()
    for row in rows:
        for c in range(3):
            ch=enc_stream([p[c] for p in row])
            bits=[b for w in ch for b in w]
            se+=sum(bits[i]!=bits[i-1] for i in range(1,len(bits)))
            pt+=sum(sum(a!=b for a,b in zip(ch[i],ch[i-1])) for i in range(1,len(ch)))
            r=1
            for i in range(1,len(bits)):
                r = r+1 if bits[i]==bits[i-1] else 1; maxrun=max(maxrun,r)
            chars.update(tuple(w) for w in ch)
            n+=len(ch)
    return dict(serial_edges_per_char=round(se/n,3), parallel_toggles_per_char=round(pt/n,3), max_run=maxrun, distinct_chars=len(chars))
orig=[]
for y in range(0,360,9):
    row=[]
    for x in range(640):
        b=frame[y*320+x//2]; idx=(b>>4) if x%2==0 else (b&15); row += [e(pal[idx])]*2
    orig.append(row)
pats={'black':[[e(0)]*1280],'white':[[e(0xfff)]*1280],'gray555':[[e(0x555)]*1280],
      'stripes':[([e(0)]*2+[e(0xfff)]*2)*320],'original':orig}
for k,v in pats.items(): print(k, metrics(v))
