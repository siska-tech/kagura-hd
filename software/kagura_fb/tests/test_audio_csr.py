import ctypes as C
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kagura_fb import Device
from kagura_fb_audio import Audio
from test_drivers import CDriver
from model import Model

class AudioModel(Model):
    def __init__(self):
        super().__init__()
        self.identity=b'KFB1\x01\x04\xff'
        self.index=0; self.shadow={}; self.snapshot={};self.active={};self.saved=None
    def write(self,a,inc,data):
        if a==54:
            self.index=data[0]
            if len(data)==2:
                assert inc
                self.shadow[self.index]=data[1]
            return
        super().write(a,inc,data)
        if a==26:
            assert self.pending[0][0]==7
            self.saved=bytes(self.pending[0]);self.snapshot=dict(self.shadow)
    def read(self,a,inc,n):
        if a==55:return bytes([self.shadow.get(self.index,0)])
        return super().read(a,inc,n)
    def finish(self):
        command,data=self.pending
        assert command[0]==7 and command[1]==0 and not any(command[4:])
        self.pending=(bytes([0])+command[1:],data)
        super().finish()
        self.active=dict(self.snapshot)

class Tests(unittest.TestCase):
    def test_python_shadow_snapshot_and_tag_wrap(self):
        m=AudioModel();d=Device(m,now_ms=m.now);a=Audio(d)
        d._tag=65535;a.write(0x6c,10);t=a.commit(wait=False)
        a.write(0x6c,77);self.assertEqual(a.read(0x6c),77)
        a.wait(t);self.assertEqual(t,65535);self.assertEqual(m.active[0x6c],10)
        self.assertEqual(a.commit(),0);self.assertEqual(m.active[0x6c],77)
    def test_python_timeout_no_resubmit(self):
        m=AudioModel();d=Device(m,timeout_ms=4,now_ms=m.now);a=Audio(d);m.hold=True
        with self.assertRaises(OSError):a.commit()
        self.assertEqual(len(m.commands),1)
    def test_python_uncertain_submission_no_retry(self):
        m=AudioModel();d=Device(m,now_ms=m.now);a=Audio(d);m.fail_submit=True
        with self.assertRaises(OSError):a.commit()
        self.assertEqual(len(m.commands),1)
    def test_python_invalid_pcm_no_writes(self):
        m=AudioModel();d=Device(m,now_ms=m.now);a=Audio(d)
        with self.assertRaises(ValueError):a.pcm_configure(0,1,0x400000)
        self.assertEqual(m.shadow,{})
    def test_python_old_abi_reject(self):
        m=AudioModel();d=Device(m,now_ms=m.now);m.identity=b'KFB1\x01\x02\x7f'
        with self.assertRaises(ValueError):Audio(d)
        self.assertEqual(m.shadow,{})
    def test_c_index_data_and_existing_wait(self):
        m=AudioModel();c=CDriver(m)
        c.lib.kfb_audio_write.argtypes=[C.c_void_p,C.c_uint8,C.c_uint8]
        c.lib.kfb_audio_read.argtypes=[C.c_void_p,C.c_uint8,C.POINTER(C.c_uint8)]
        c.lib.kfb_audio_commit.argtypes=[C.c_void_p,C.POINTER(C.c_uint16)]
        p=C.byref(c.device);v=C.c_uint8();t=C.c_uint16()
        self.assertEqual(c.lib.kfb_audio_write(p,0x8c,55),0)
        self.assertEqual(c.lib.kfb_audio_read(p,0x8c,C.byref(v)),0);self.assertEqual(v.value,55)
        self.assertEqual(c.lib.kfb_audio_commit(p,C.byref(t)),0)
        self.assertEqual(c.lib.kfb_audio_write(p,0x8c,99),0)
        self.assertEqual(c.lib.kfb_wait(p,t),0);self.assertEqual(m.active[0x8c],55)
        self.assertEqual(c.callback_errors,[])
    def test_c_old_abi_and_null_reject(self):
        m=AudioModel();c=CDriver(m);m.identity=b'KFB1\x01\x02\x7f'
        self.assertEqual(c.lib.kfb_audio_write(C.byref(c.device),0x6c,2),-4)
        self.assertEqual(c.lib.kfb_audio_commit(C.byref(c.device),None),-1)
        self.assertEqual(m.shadow,{})

    def test_python_synth_api_rejected_before_writes(self):
        m=AudioModel();d=Device(m,now_ms=m.now);a=Audio(d)
        with self.assertRaises(NotImplementedError):a.channel(0,step=1)
        with self.assertRaises(ValueError):a.write(0x04,255)
        self.assertEqual(m.shadow,{})
    def test_c_synth_index_rejected(self):
        m=AudioModel();c=CDriver(m)
        self.assertEqual(c.lib.kfb_audio_write(C.byref(c.device),4,255),-1)
        self.assertEqual(m.shadow,{})
    def test_old_six_voice_prototype_rejected(self):
        m=AudioModel();d=Device(m,now_ms=m.now);m.identity=b'KFB1\x01\x03\xff'
        with self.assertRaises(ValueError):Audio(d)

if __name__=='__main__':unittest.main()
