# SPDX-License-Identifier: Apache-2.0
import sys,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'software/kagura_fb'),str(ROOT/'software/kagura_fb/tests')]
from kagura_fb import Device
from kagura_fb_audio import Audio
from showcase.pc_mock import ShowcaseModel,VirtualClock
from showcase.gpu_api_adapter import GPU,PALETTE
from showcase.diagnostics import Diagnostics
from showcase.framebuffer_oracle import FramebufferOracle
from showcase.scene_manager import Demo
from showcase import scenes,music
from showcase.demo_main import run_on_device

def system(verify=True):
    model=ShowcaseModel();clock=VirtualClock();events=[]
    device=Device(model,timeout_ms=30,now_ms=model.now)
    gpu=GPU(device,Audio(device),Diagnostics(events.append,clock.now),FramebufferOracle(),verify)
    return model,clock,events,gpu

class ShowcaseTests(unittest.TestCase):
    def test_all_scenes_two_loops(self):
        m,clock,events,g=system()
        Demo(g).run(2,sleep=clock.sleep)
        starts=[(e['cycle'],e['scene']) for e in events if e['event']=='scene_start']
        self.assertEqual(starts,[(cycle,i) for cycle in (0,1) for i in range(1,7)])
        self.assertEqual(len([e for e in events if e['event']=='scene_end']),12)
        self.assertEqual(len([e for e in events if e['event']=='frame']),576)
        self.assertTrue(all(x>0 for x in g.diag.commands))
        self.assertEqual(m.pcm_status,[0,0]);self.assertFalse(m.cursor_visible)
        self.assertEqual(len([e for e in events if e['event']=='cursor_crc']),2)

    def test_fill_clipping_and_odd_edges(self):
        m,c,e,g=system(False)
        for page in (0,1):
            g.fill(page,0,0,640,360,0)
            for x,y,w,h,k in ((-3,-4,8,9,3),(31,31,3,3,7),(639,359,1,1,15),(400,120,237,189,9)):
                g.fill(page,x,y,w,h,k)
        g.verify()

    def test_overlap_four_directions_and_guards(self):
        m,c,e,g=system(False)
        g.fill(0,0,0,640,360,0)
        for n in range(32):g.fill(0,n*8,64,8,120,n%16)
        for sx,sy,dx,dy in ((32,80,40,80),(40,80,32,80),(32,80,32,84),(32,84,32,80),(32,80,40,84)):
            g.copy(0,sx,sy,0,dx,dy,192,96);g.oracle.verify(g.device,0)
        before=sum(g.diag.commands)
        for args in ((0,32,80,0,34,80,192,96),(0,33,80,0,41,80,192,96),(0,32,80,0,40,80,191,96)):
            with self.assertRaises(ValueError):g.copy(*args)
        self.assertEqual(before,sum(g.diag.commands))

    def test_palette_atomic_present_and_palette_only_phase(self):
        m,c,e,g=system(False)
        g.palette(PALETTE);g.present(0);old=m.active_palette[:]
        colors=tuple(reversed(PALETTE));g.palette(colors)
        self.assertEqual(m.active_palette,old);self.assertEqual(m.page,0)
        command=bytearray(16);command[0]=3;command[1]=1
        tag=g.device.submit(command)
        self.assertEqual(m.page,0);self.assertEqual(m.active_palette,old)
        g.device.wait(tag)
        self.assertEqual(m.page,1);self.assertEqual(tuple(m.active_palette),colors)
        state=scenes.enter(g,3);digest=hashlib.sha256(m.memory[:230400]).digest()
        n=g.diag.commands[1]+g.diag.commands[4]
        for frame in range(24):scenes.tick(g,3,state,frame)
        self.assertEqual(hashlib.sha256(m.memory[:230400]).digest(),digest)
        self.assertEqual(g.diag.commands[1]+g.diag.commands[4],n)
        for frame,(page,palette) in enumerate(m.presents[-24:]):
            accents=list(PALETTE[7:]);shift=frame%9
            self.assertEqual((page,palette),(0,tuple(PALETTE[:7])+tuple(accents[shift:]+accents[:shift])))
        for frame in range(24,48):scenes.tick(g,3,state,frame)
        self.assertEqual([page for page,_ in m.presents[-24:]],[1,0]*12)
        g.verify()

    def test_blit_scene_matches_fresh_composition_including_shadow(self):
        m,c,e,g=system(False);state=scenes.enter(g,2)
        _,_,_,reference=system(False)
        scenes.blit_background(reference,0)
        background=bytes(reference.oracle.pages[0])
        for frame in range(48):
            scenes.tick(g,2,state,frame)
            x,y,_,_=state['rects'][g.page]
            reference.oracle.pages[0][:]=background
            scenes.window(reference,0,x,y,224,128,'OVERLAP BLIT',8)
            reference.text(0,x+16,y+94,'MOVE WITHOUT REDRAW',9,1)
            self.assertEqual(g.oracle.pages[g.page],reference.oracle.pages[0], 'incremental window / shadow trails frame=%d'%frame)
        g.verify()

    def test_cursor_crc_and_locked_bank(self):
        m,c,e,g=system(True);state=scenes.enter(g,4)
        crc=state['crc'];n=g.diag.commands[1]+g.diag.commands[4]+g.diag.commands[6]
        for i in range(48):scenes.tick(g,4,state,i)
        self.assertEqual((g.crc(0),g.crc(1)),crc)
        self.assertEqual(n,g.diag.commands[1]+g.diag.commands[4]+g.diag.commands[6])
        with self.assertRaises(OSError):g.device.cursor_shape(g.bank,bytes(256),(0,0,0))

    def test_audio_parameters_buffers_and_independent_mix(self):
        m,c,e,g=system(True);music.upload(g);music.start(g)
        self.assertEqual(m.pcm_status,[3,3])
        self.assertGreaterEqual(music.BASES[0],230400)
        self.assertLessEqual(music.BASES[0]+music.LENGTH,music.BASES[1])
        self.assertLessEqual(music.BASES[1]+music.LENGTH,4194304)
        for i in range(0,music.LENGTH,997):
            a,b=music.sample(0,i),music.sample(1,i)
            expected=((a*160+b*80)*160//256,(a*96+b*144)*160//256)
            self.assertEqual(music.mix(i),expected)
            for ch,v in enumerate((a,b)):self.assertEqual(m.memory[music.BASES[ch]+i],v&255)
        self.assertEqual(music.mix(0),(0,0));self.assertEqual(music.mix(music.LENGTH-1),(0,0))
        rms,peaks=music.levels(17000)
        samples=[music.mix(17000+i) for i in range(256)]
        self.assertEqual(rms,tuple(int((sum(s[k]*s[k] for s in samples)//256)**0.5) for k in (0,1)))
        self.assertEqual(peaks,tuple(max(abs(s[k]) for s in samples) for k in (0,1)))
        music.stop(g);self.assertEqual(m.pcm_status,[0,0])

    def test_pcm_fault_stops_no_automatic_retry(self):
        m,c,e,g=system(False);state=scenes.enter(g,5)
        m.pcm_status[1]=8
        with self.assertRaises(OSError):scenes.tick(g,5,state,0)

    def test_timeout_and_latched_stop_then_explicit_fresh_recovery(self):
        m,c,e,g=system(False);demo=Demo(g);demo.prepared=True;m.hold=True
        with self.assertRaises(OSError):demo.run(sleep=c.sleep)
        n=sum(g.diag.commands)
        with self.assertRaises(RuntimeError):demo.run(sleep=c.sleep)
        self.assertEqual(sum(g.diag.commands),n)
        self.assertTrue(demo.halted);self.assertFalse(e[-1]['automatic_retry'])
        # A NEW model/device represents externally completed recovery. No reset
        # or automatic retry of the failing model is performed by the demo.
        m2,c2,e2,g2=system(False);d2=Demo(g2);d2.prepared=True
        d2.run(sleep=c2.sleep,should_stop=lambda:True)
        self.assertFalse(d2.halted)

    def test_device_error_no_replay(self):
        m,c,e,g=system(False);d=Demo(g);d.prepared=True;m.force_error=4
        with self.assertRaises(OSError):d.run(sleep=c.sleep)
        self.assertTrue(d.halted);self.assertEqual(sum(g.diag.commands),1)

    def test_busy_before_submit_sends_no_command(self):
        m,c,e,g=system(False);d=Demo(g);d.prepared=True
        m.pending=(bytes(16),bytes(64));m.hold=True
        with self.assertRaises(OSError):d.run(sleep=c.sleep)
        self.assertTrue(d.halted);self.assertEqual(sum(g.diag.commands),0)

    def test_uncertain_submit_not_replayed_or_cleaned_up(self):
        m,c,e,g=system(False);d=Demo(g);d.prepared=True;m.fail_submit=True
        with self.assertRaises(OSError):d.run(sleep=c.sleep)
        self.assertTrue(d.halted);self.assertEqual(sum(g.diag.commands),1)
        self.assertIsNotNone(m.pending)

    def test_pcm_fault_latches_manager(self):
        m,c,e,g=system(False);d=Demo(g);d.prepared=True
        def inject(scene,frame,gpu):
            if scene==5 and frame==0:m.pcm_status[0]=8
        with self.assertRaises(OSError):d.run(on_frame=inject,sleep=c.sleep)
        self.assertTrue(d.halted);self.assertEqual(e[-1]['event'],'halt')

    def test_oracle_detects_corruption(self):
        m,c,e,g=system(False);m.corrupt_next=True;g.fill(0,0,0,8,8,7)
        with self.assertRaises(AssertionError):g.oracle.verify(g.device,0)

    def test_hardware_entry_requires_qualification_without_io(self):
        with self.assertRaises(RuntimeError):run_on_device(None,qualified_bitstream_sha256='',hardware_qualified=False)

    def test_abi_reject_and_memory_structure(self):
        m=ShowcaseModel();d=Device(m,now_ms=m.now);a=Audio(d);m.identity=b'KFB1\x01\x03\xff'
        with self.assertRaises(ValueError):GPU(d,a)
        m,c,e,g=system(False)
        self.assertEqual(len(g.row),320)
        # Runtime modules never import the PC-only unpacked framebuffer oracle.
        for name in ('demo_main.py','scene_manager.py','scenes.py','gpu_api_adapter.py','music.py'):
            text=(ROOT/'software/kagura_fb/showcase'/name).read_text()
            self.assertNotIn('import FramebufferOracle',text)

if __name__=='__main__':unittest.main(verbosity=2)
