from pathlib import Path
import struct,zlib,json,sys

def decode(raw):
    if len(raw)!=136:raise ValueError('one complete 136B ISO2 frame required')
    magic,version,source,test,count,flags=struct.unpack('<4sBBHHH',raw[:12])
    if (magic,version,source,test,count)!=(b'PDT1',1,4,2,20) or flags & ~1:raise ValueError('header')
    if zlib.crc32(raw[:-4])!=int.from_bytes(raw[-4:],'little'):raise ValueError('CRC')
    records=[int.from_bytes(raw[12+i*6:18+i*6],'little') for i in range(20)]
    if any(v>>32 for v in records):raise ValueError('snapshot cycle')
    if records[:4]!=[300032,9,0,0]:raise ValueError('metadata')
    words=records[4:]
    values=[v.to_bytes(4,'little').hex() for v in words[:6]]
    return dict(test_id='ISO2-1',boundaries=dict(zip(
        ['transport_rx','csr_accept','upload_settled','upload_first_read','csr_response','transport_response'],values)),
        tx_count=words[6],csr_count=words[7]&255,write_count=(words[7]>>8)&255,
        rx_count=(words[7]>>16)&255,flags=words[7]>>24,read_count=words[8],header_fault=bool(flags),
        all_six_match=all(v=='ed0f2143' for v in values))

if __name__=='__main__':print(json.dumps(decode(Path(sys.argv[1]).read_bytes()),indent=2))
