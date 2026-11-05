# SPDX-License-Identifier: Apache-2.0
from . import scenes,music
from .diagnostics import diff_us,sleep_us,collect,heap_stats

class Demo:
    def __init__(self, gpu, interval_us=125000):
        if not isinstance(interval_us,int) or interval_us<16667:raise ValueError('Host interval must be >=16667us')
        self.gpu=gpu;self.interval=interval_us;self.halted=False;self.prepared=False

    def run(self, cycles=1, on_frame=None, sleep=sleep_us, should_stop=None):
        if self.halted:raise RuntimeError('fault latched: construct a fresh, externally recovered device; no replay')
        if cycles is not None and (not isinstance(cycles,int) or cycles<1):raise ValueError('cycles must be positive or None')
        g=self.gpu
        try:
            if not self.prepared:
                g.diag.event('asset_start',pcm_bases=music.BASES,bytes_per_channel=music.LENGTH)
                start=g.diag.clock();music.upload(g);self.prepared=True
                g.diag.event('asset_end',duration_us=diff_us(g.diag.clock(),start),bytes=music.LENGTH*2)
                collect()
            cycle=0
            while cycles is None or cycle<cycles:
                for scene in range(6):
                    start=g.diag.clock();commands=sum(g.diag.commands)
                    g.diag.event('scene_start',cycle=cycle,scene=scene+1,name=scenes.NAMES[scene])
                    collect()
                    # Hide setup transfers behind an atomically presented black
                    # palette; no partially built scene is shown during Host I/O.
                    g.palette((0,)*16);g.present(g.page)
                    state=scenes.enter(g,scene)
                    collect()
                    for frame in range(scenes.FRAMES[scene]):
                        if should_stop and should_stop():
                            g.shutdown();g.diag.event('stopped',reason='clean frame boundary');return
                        before=g.diag.clock();n=sum(g.diag.commands)
                        scenes.tick(g,scene,state,frame);status=g.health()
                        if on_frame:on_frame(scene,frame,g)
                        collect()
                        elapsed=max(0,diff_us(g.diag.clock(),before))
                        wait=max(0,self.interval-elapsed)
                        g.diag.event('frame',cycle=cycle,scene=scene+1,frame=frame,commands=sum(g.diag.commands)-n,
                            work_us=elapsed,scheduled_sleep_us=wait,host_interval_us=elapsed+wait,
                            host_update_hz=1000000/max(1,elapsed+wait),hdmi_nominal_hz=60,gpu_status=status,
                            heap_alloc_free=heap_stats())
                        sleep(wait)
                    scenes.leave(g,scene,state)
                    g.diag.event('scene_end',cycle=cycle,scene=scene+1,duration_us=diff_us(g.diag.clock(),start),commands=sum(g.diag.commands)-commands)
                cycle+=1
            g.shutdown();g.diag.event('complete',cycles=cycle,commands=g.diag.commands,calls=g.diag.calls)
        except BaseException as error:
            self.halted=True;g.diag.faulted=True
            g.diag.event('halt',error=repr(error),automatic_retry=False,automatic_bus_cleanup=False,
                recovery='external recovery and fresh Device/Audio/GPU/Demo required')
            # No bus writes here: a timed-out operation may have partially applied.
            raise
