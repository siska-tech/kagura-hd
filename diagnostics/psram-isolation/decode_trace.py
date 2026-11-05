"""Strict PDT1 parser. Reads a saved file only; never opens a device."""
from pathlib import Path
import struct
import zlib
import json

def decode(raw):
    frames=[]
    while raw:
        if len(raw)<12:
            raise ValueError('truncated header')
        magic,version,source,case_id,count,flags=struct.unpack('<4sBBHHH',raw[:12])
        if magic!=b'PDT1' or version!=1 or source not in (2,3) or case_id!=1 or count!=20 or flags & ~1:
            raise ValueError('invalid header')
        size=12+6*count+4
        frame=raw[:size]
        if len(frame)!=size or zlib.crc32(frame[:-4])!=int.from_bytes(frame[-4:],'little'):
            raise ValueError('truncated frame or CRC mismatch')
        records=[int.from_bytes(frame[12+i*6:18+i*6],'little') for i in range(count)]
        if any(x>>32 for x in records):
            raise ValueError('unexpected snapshot cycle')
        address,meta,mask0,mask1,*data=records
        words=meta & 31
        writing=bool(meta & 32)
        if meta>>6 or writing!=(source==2) or not 1<=words<=16 or address%4:
            raise ValueError('invalid metadata')
        payload=b''.join(x.to_bytes(4,'little') for x in data)
        frames.append(dict(test_id=case_id,source=source,fault=bool(flags),address=address,
            words=words,write=writing,mask=f'{mask0 | mask1<<32:016x}',
            data=payload[:words*4].hex(),payload64=payload.hex()))
        raw=raw[size:]
    if not frames:
        raise ValueError('empty capture')
    if len(frames)>2 or frames[0]['source']!=2 or (len(frames)==2 and (frames[1]['source']!=3 or any(x['fault'] for x in frames))):
        raise ValueError('unexpected frame sequence')
    return frames

if __name__=='__main__':
    import sys
    print(json.dumps(dict(hardware_pass=False,frames=decode(Path(sys.argv[1]).read_bytes())),indent=2))
