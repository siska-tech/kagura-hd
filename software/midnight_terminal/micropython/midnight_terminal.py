# SPDX-License-Identifier: Apache-2.0
"""MIDNIGHT TERMINAL: Python owns the script, scenes and render loop."""
from midnight_fm import Synth, audio_events
from midnight_show import Show


def run(script=None, on_frame=None, backend=None, asset_dir='mt_data'):
    """Play the Python script; on_frame(show, ms, synth) can customize each frame."""
    if script is None:
        import story
        script = story
    import gc
    gc.collect()
    use_graphics=backend is None
    if use_graphics:
        import _kagura
        from midnight_graphics import Graphics
        backend = _kagura
        graphics = Graphics(backend,asset_dir)
    else:
        graphics = backend
    show = Show(graphics, script)
    synth = Synth(backend=backend,script=script,score=True,autostart=False)
    if use_graphics:
        graphics.backend=synth
    with synth:
        show.preload()
        synth.start()
        next_us = 0
        while True:
            ms = backend.elapsed_us()//1000
            if ms >= script.END_MS:
                break
            show.frame(ms)
            if on_frame is not None:
                on_frame(show, ms, synth)
            next_us = max(next_us+33333, backend.elapsed_us())
            backend.wait_until(next_us)
        backend.check()
        result = synth.stats()
    result['frames'], result['scene_frames'] = show.frames, tuple(show.scene_frames)
    return result
