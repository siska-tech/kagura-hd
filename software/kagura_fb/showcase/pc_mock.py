# SPDX-License-Identifier: Apache-2.0
"""PC-only wire-level behavioral extension of the existing driver test model.
Models command completion/vblank atomically; it is NOT the RTL or an I/O model.
"""
from model import BlitModel

class ShowcaseModel(BlitModel):
    def __init__(self):
        super().__init__()
        self.identity=b'KFB1\x01\x04\xff'
        self.audio_index=0;self.audio_shadow=bytearray(256);self.audio_active=bytearray(256)
        self.pcm_status=[0,0];self.presents=[];self.submissions=[0]*8;self.audio_commits=0
        self.corrupt_next=False

    def finish(self):
        command,payload=self.pending
        op=command[0]
        if op==7:
            self.pending=None;self.tag=int.from_bytes(command[2:4],'little')
            self.error=self.force_error;self.force_error=0
            if not self.error:
                self.audio_active[:]=self.audio_shadow
                for c in (0,1):
                    enable=self.audio_active[0x6e+c*32]&1
                    if enable and not self.pcm_status[c]&1:self.error=4
                    if enable and self.pcm_status[c]&1:self.pcm_status[c]|=2
                    if not enable:self.pcm_status[c]&=~2
                self.audio_commits+=1
            self.sticky=self.error;self.completed=not self.lost_done
        else:
            super().finish()
            if op==3 and not self.error:self.presents.append((self.page,tuple(self.active_palette)))
        if self.corrupt_next and op in (1,4,6):
            self.memory[0]^=1;self.corrupt_next=False

    def read(self,address,increment,length):
        result=bytearray()
        for _ in range(length):
            if address==54:value=self.audio_index
            elif address==55:
                index=self.audio_index
                if index in (0x6f,0x8f):value=self.pcm_status[(index-0x6f)//32]
                elif index==0xe1:value=0
                else:value=self.audio_shadow[index]
            else:value=super().read(address,False,1)[0]
            result.append(value)
            if increment:address=(address+1)&63
        return result

    def write(self,address,increment,data):
        for value in data:
            if address==54:self.audio_index=value
            elif address==55:
                index=self.audio_index
                if index in (0x6f,0x8f):
                    c=(index-0x6f)//32;base=0x60+c*32
                    if value==1:
                        start=int.from_bytes(self.audio_shadow[base:base+3],'little')
                        end=int.from_bytes(self.audio_shadow[base+4:base+7],'little')
                        self.pcm_status[c]=1 if start<end<=0x3fffff else 16
                    elif value==2:self.pcm_status[c]=0
                    elif value==4:self.pcm_status[c]&=0x43
                    else:self.sticky=2
                else:self.audio_shadow[index]=value
            else:
                super().write(address,False,bytes((value,)))
                if address==26 and value==1:
                    self.submissions[self.stage[0]]+=1
                    # The legacy model retains every packet. Bound its trace
                    # for long PC loops; telemetry retains aggregate counts.
                    if len(self.commands)>512:del self.commands[:256]
            if increment:address=(address+1)&63

class VirtualClock:
    def __init__(self):self.value=0
    def now(self):return self.value
    def sleep(self,n):self.value+=n
