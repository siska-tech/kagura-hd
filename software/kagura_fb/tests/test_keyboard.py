# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from kagura_keyboard import Keyboard, frame, crc8

class UART:
    def __init__(self): self.data=bytearray(); self.sent=[]
    def any(self): return len(self.data)
    def readinto(self, buf):
        n=min(len(buf),len(self.data));buf[:n]=self.data[:n];del self.data[:n];return n
    def write(self, data): self.sent.append(bytes(data));return len(data)

def key(usage=4, modifiers=0, flags=1, code=97):
    return frame(1,bytes((usage,modifiers,flags,code)))

class Tests(unittest.TestCase):
    def setUp(self):
        self.time=0;self.uart=UART();self.k=Keyboard(self.uart,lambda:self.time)
    def read(self):
        b=bytearray(128);n=self.k.readinto(b);return bytes(b[:n]) if n else b''
    def test_fragmented_keys_and_release(self):
        for b in key():self.k.feed(bytes((b,)))
        self.k.feed(key(flags=0)+key(flags=3))
        self.assertEqual(self.read(),b'aa')
    def test_control_and_editing(self):
        self.k.feed(key(6,1,9,ord('c')))
        self.assertEqual(self.read(),b'\x03')
        self.k.feed(key(7,1,9,ord('d'))+key(0x28,code=13)+key(0x2a,code=8)+key(0x50,code=0x80))
        self.assertEqual(self.read(),b'\x04\r\x08\x1b[D')
    def test_bad_crc_and_timeout(self):
        bad=bytearray(key());bad[-1]^=1
        self.k.feed(bad+key())
        self.assertEqual(self.read(),b'a');self.assertEqual(self.k.bad_frames,1)
        self.k.feed(key()[:4]);self.time=101;self.k.feed(key())
        self.assertEqual(self.read(),b'a')
    def test_oversize_noise_and_crc_start_byte(self):
        self.k.feed(b'noise\x7e\x01\xff'+key())
        self.assertEqual(self.read(),b'a')
        # A valid CRC equal to the frame marker must not eat the next frame.
        sample=next(frame(0x40,bytes((i,))) for i in range(256) if frame(0x40,bytes((i,)))[-1]==0x7e)
        self.k.feed(sample+key());self.assertEqual(self.read(),b'a')
    def test_status_poll_config(self):
        self.uart.data.extend(frame(0xc5,b'KHDK\x01\x01')+key())
        self.k.poll();self.assertTrue(self.k.connected);self.assertEqual(self.k.bridge_version,1)
        self.assertEqual(self.read(),b'a')
        self.k.configure();self.assertEqual(self.uart.sent[0],frame(0x85,b'KHD1'))
        self.assertEqual(self.uart.sent[1][1],0x83)
    def test_atomic_overflow_and_ctrl_c_priority(self):
        self.k=Keyboard(self.uart,lambda:0,8)
        self.k.feed(key()*6+key(0x50,code=0x80)+key(6,1,9,ord('c')))
        self.assertEqual(self.read(),b'\x03');self.assertEqual(self.read(),b'aaaaaa')
        self.assertEqual(self.k.dropped,3)
    def test_alt_modifiers_and_unsupported_kana(self):
        self.k.feed(key(modifiers=4)+key(0xe1,flags=1)+key(code=0xa1))
        self.assertEqual(self.read(),b'\x1ba')
    def test_unready_uart_is_not_enabled(self):
        pins={}
        class Pin:
            IN,OUT,PULL_DOWN=0,1,2
            def __new__(cls, number, *args, **kwargs):
                if number in pins:return pins[number]
                result=super().__new__(cls);pins[number]=result;result.level=0;return result
            def __init__(self, number, *args, **kwargs):
                if 'value' in kwargs:self.level=kwargs['value']
            def value(self):return self.level
            def init(self,*args):pass
        opened=[]
        def open_uart(*args,**kwargs):opened.append(kwargs);return self.uart
        with patch.dict('sys.modules',{'machine':SimpleNamespace(Pin=Pin,UART=open_uart)}):
            k=Keyboard(now_ms=lambda:self.time);k.configure()
            self.assertIsNone(k.uart);self.assertEqual(pins[0].value(),1)
            k.poll();self.time=100;k.poll();self.assertEqual(opened,[])
            pins[1].level=1;k.poll();self.time=104;k.poll();self.assertEqual(opened,[])
            self.time=105;k.poll();self.assertEqual(len(opened),1)
            self.assertEqual(len(self.uart.sent),2)

if __name__=='__main__':unittest.main()
