import sys
def enc_stream(vals):
    cnt=0; out=[]
    for D in vals:
        n1=bin(D).count('1'); xnor = n1>4 or (n1==4 and (D&1)==0)
        q=[D&1]
        for i in range(1,8):
            b=(D>>i)&1; q.append(1-(q[-1]^b) if xnor else q[-1]^b)
        q8=0 if xnor else 1
        n1q=sum(q); n0q=8-n1q
        if cnt==0 or n1q==n0q:
            o9=1-q8; low=q if q8 else [1-x for x in q]
            cnt += (n1q-n0q) if q8 else (n0q-n1q)
        elif (cnt>0 and n1q>n0q) or (cnt<0 and n0q>n1q):
            o9=1; low=[1-x for x in q]; cnt += 2*q8 + (n0q-n1q)
        else:
            o9=0; low=q; cnt += -2*(1-q8) + (n1q-n0q)
        out.append(low+[q8,o9])
    return out
def edges(vals):
    bits=[b for ch in enc_stream(vals) for b in ch]
    return sum(bits[i]!=bits[i-1] for i in range(1,len(bits)))/len(vals)
def line_rate(rgbs):  # rgbs: list of (r,g,b) per HDMI pixel; returns edges/pixel summed over 3 ch
    return sum(edges([p[c] for p in rgbs]) for c in range(3))
root=sys.argv[1]
frame=[int(x,16) for x in open(root+'/frame.hex')]; pal=[int(x,16) for x in open(root+'/palette.hex')]
e=lambda v:(((v>>8)&15)*17,((v>>4)&15)*17,(v&15)*17)
tot=0
for y in range(0,360,9):
    row=[]
    for x in range(640):
        b=frame[y*320+x//2]; idx=(b>>4) if x%2==0 else (b&15)
        row += [e(pal[idx])]*2
    tot+=line_rate(row)
orig=tot/40
print('original',round(orig,3))
for name,c in [('black',(0,0,0)),('white',(255,255,255)),('red',(255,0,0))]:
    print(name, round(line_rate([c]*1280),3))
res=[]
for v in range(4096):
    c=e(v); res.append((line_rate([c]*256),v))
res.sort()
print('uniform min',res[:3],'max',res[-5:])
# two-color stripes at FB pixel pitch (2 HDMI px) between black and white, and others
for a,b in [(0x000,0xfff),(0x000,0x00f),(0xfff,0x000)]:
    print('stripe',hex(a),hex(b), round(line_rate(([e(a)]*2+[e(b)]*2)*320),3))
