"""Host integration checks for the generic REPL, GPU handoff and XLINK input."""
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'software/kagura_runtime'),str(ROOT/'software/kagura_fb'),
              str(ROOT/'software/midnight_terminal/micropython')]
import kagura_repl as repl
from kagura_gpu import Device
from kagura_fm import Synth,Patch,operator,Schedule,NOTE,GAIN
from kagura_keyboard import Keyboard,frame
from memory_gpu import MemoryGPU


class Font:
    height,row_bytes=8,1
    def glyph(self,ch): return (8,b'\x7e\x42\x42\x42\x42\x42\x7e\0')
    _lookup=glyph
    def close(self): self.closed=True


class UART:
    def __init__(self): self.data=bytearray(); self.sent=[]
    def any(self): return len(self.data)
    def readinto(self,buf):
        n=min(len(buf),len(self.data)); buf[:n]=self.data[:n]; del self.data[:n]; return n
    def write(self,data): self.sent.append(bytes(data)); return len(data)


class Backend(MemoryGPU):
    def __init__(self):
        super().__init__(); self.active=False; self.calls=[]; self.saved=None
    def display_open(self):
        if self.active: raise OSError('bus already owned')
        self.active=True; self.calls.append('display_open')
    def open(self,*args):
        if self.active: raise OSError('bus already owned')
        self.active=True; self.calls.append('audio_open'); super().open(*args)
    def start(self): self.calls.append('start'); super().start()
    def close(self):
        assert self.active
        self.calls.append('close'); self.active=False; super().close()
    def bitmap(self,page,x,y,w,h,stride,bits,fg,bg):
        assert self.active
        for r in range(h):
            for c in range(w):
                color=fg if bits[r*stride+c//8]&(128>>(c&7)) else bg
                self.fill(page,x+c,y+r,1,1,color)
    def cursor(self,*args): self.calls.append(('cursor',args))
    def copy_bytes(self,src,dst,n):
        assert self.active and n==115200
        self.calls.append(('snapshot',src,dst))
        if src==0 and dst==repl.SNAPSHOT: self.saved=bytes(self.pages[0])
        elif src==repl.SNAPSHOT and dst==0: self.pages[0][:]=self.saved
        else: raise AssertionError((src,dst,n))
    def fence(self): pass


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.frequency=120000000
        def freq(value=None):
            if value is not None: self.frequency=value
            return self.frequency
        self.notifications=[]
        self.context=patch.dict(sys.modules,{'machine':types.SimpleNamespace(freq=freq)})
        self.context.start(); self.addCleanup(self.context.stop)
        self.notify=patch.object(repl.os,'dupterm_notify',lambda s:self.notifications.append(s),create=True)
        self.notify.start(); self.addCleanup(self.notify.stop)
        self.dup=patch.object(repl.os,'dupterm',lambda *a:None,create=True)
        self.dup.start(); self.addCleanup(self.dup.stop)
        self.ticks=patch.object(time,'ticks_ms',lambda:int(time.monotonic()*1000),create=True)
        self.ticks.start(); self.addCleanup(self.ticks.stop)
        self.diff=patch.object(time,'ticks_diff',lambda a,b:a-b,create=True)
        self.diff.start(); self.addCleanup(self.diff.stop)
        self.addCleanup(setattr,repl,'console',None)
        self.gpu=Backend(); self.uart=UART()
        self.keys=Keyboard(self.uart)
        self.console=repl.Console(self.gpu,Font(),self.keys)
        self.console._open_display()
        repl.console=self.console

    def flush(self):
        while self.console._head!=self.console._tail:
            self.console._flush_display()

    def test_framebuffer_output_and_scroll(self):
        for _ in range(48):
            self.console.write(b'hello {"gpu": 1}\n'); self.flush()
        self.assertTrue(any(self.gpu.pages[0]))
        self.assertEqual(self.console.screen.y,44)
        self.assertFalse(hasattr(self.console.screen.fb,'buffer'))

    def test_idle_ticks_do_not_recommit_cursor(self):
        self.console._tick()
        count=len(self.gpu.calls)
        self.console._tick()
        self.assertEqual(len(self.gpu.calls),count)

    def test_gpu_handoff_preserves_pixels_and_terminal_position(self):
        self.console.write(b'>>> print(1)\r\n'); self.flush()
        pixels=bytes(self.gpu.pages[0]); position=(self.console.screen.x,self.console.screen.y)
        with Device(self.gpu) as gpu:
            self.assertTrue(self.console.paused)
            gpu.fill_rect(0,0,0,640,360,9)
            self.console.write(b'ignored during app')
            before=len(self.gpu.calls); self.console._tick()
            self.assertEqual(len(self.gpu.calls),before)
        self.assertEqual(bytes(self.gpu.pages[0]),pixels)
        self.assertEqual((self.console.screen.x,self.console.screen.y),position)
        self.assertFalse(self.console.paused)
        self.assertTrue(self.gpu.active)

    def test_keyboard_and_ctrl_c_remain_active_during_audio(self):
        p=Patch((operator(level=12000),operator(level=3000),operator(),operator()))
        with self.assertRaises(KeyboardInterrupt):
            with Synth([p],backend=self.gpu) as fm:
                self.assertTrue(self.console.paused)
                self.uart.data.extend(frame(1,bytes((6,1,9,ord('c')))))
                self.console._tick()
                self.assertTrue(self.notifications)
                b=bytearray(1)
                self.assertEqual(self.console.readinto(b),1)
                self.assertEqual(b,b'\x03')
                raise KeyboardInterrupt()
        self.assertFalse(self.console.paused)
        self.assertTrue(self.gpu.active)
        self.assertEqual(self.frequency,120000000)

    def test_start_failure_restores_console(self):
        def fail(): raise OSError('FM producer startup failed')
        self.gpu.start=fail
        p=Patch((operator(),)*4)
        with self.assertRaises(OSError):
            with Synth([p],backend=self.gpu): pass
        self.assertTrue(self.console._display_owned)
        self.assertFalse(self.console.paused)

    def test_snapshot_failure_releases_gpu_without_starting_application(self):
        def fail(*a): raise OSError('snapshot transfer fault')
        self.gpu.copy_bytes=fail
        with self.assertRaises(OSError):
            with Device(self.gpu): pass
        self.assertNotIn('audio_open',self.gpu.calls)
        self.assertFalse(self.gpu.active)
        self.assertFalse(self.console._suspended)
        self.uart.data.extend(frame(1,bytes((4,0,1,97))))
        self.console._tick()
        b=bytearray(1); self.assertEqual(self.console.readinto(b),1); self.assertEqual(b,b'a')
        self.console.close()

    def test_restore_failure_keeps_keyboard_and_allows_console_close(self):
        with Device(self.gpu):
            def fail(*a): raise OSError('restore transfer fault')
            self.gpu.copy_bytes=fail
        self.assertIsNotNone(self.console.last_error)
        self.assertFalse(self.gpu.active)
        self.assertFalse(self.console._closed)
        self.console.close()

    def test_ctrl_c_during_restore_releases_display(self):
        with self.assertRaises(KeyboardInterrupt):
            with Device(self.gpu):
                def interrupt(*a): raise KeyboardInterrupt()
                self.gpu.copy_bytes=interrupt
        self.assertFalse(self.gpu.active)
        self.assertFalse(self.console._suspended)
        self.assertFalse(self.keys._closed)
        self.console.close()

    def test_boot_respects_user_scripts(self):
        with patch.object(repl.os,'stat',return_value=()),patch.object(repl,'start') as start:
            self.assertFalse(repl.autostart()); start.assert_not_called()
        with patch.object(repl.os,'stat',side_effect=OSError()),patch.object(repl,'start') as start:
            self.assertTrue(repl.autostart()); start.assert_called_once()

    def test_packed_patches_and_sorted_commands_are_generic(self):
        p=Patch((operator(ratio=2,level=10000),operator(),operator(),operator()))
        self.assertEqual(len(p.pack()),59)
        s=Schedule().add(0,GAIN,0,value=200,duration=100).add(0,NOTE,0,0,60,180,4800)
        self.assertEqual(len(s.data),32)
        with self.assertRaises(ValueError): s.add(-1,NOTE)
        with self.assertRaises(ValueError): Patch((operator(),)*3)

    def test_schedule_uses_bounded_immutable_pages(self):
        s=Schedule()
        for i in range(1005): s.add(i*8000,NOTE,0,0,60,180,800)
        pages=s.pages()
        self.assertEqual(len(pages),16)
        self.assertTrue(all(isinstance(p,bytes) and len(p)==1024 for p in pages[:-1]))
        self.assertEqual(len(pages[-1]),720)
        self.assertEqual(s.data,b''.join(pages))
        self.assertEqual(len(s._current),1024)

    def test_firmware_boundary_excludes_application_code_and_data(self):
        runtime=ROOT/'software/kagura_runtime'
        for path in [runtime/'micropython.cmake',runtime/'manifest.py']+list((runtime/'native').glob('*')):
            self.assertNotIn('midnight',path.read_text().lower(),str(path))
        self.assertNotIn('assets.c',(runtime/'micropython.cmake').read_text())


if __name__=='__main__': unittest.main()
