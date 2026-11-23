"""Compare Python scenes against the C renderer and exercise the real FM engine.

Builds temporary host shared libraries in build/, using MSVC on Windows or CC
on Linux. No hardware or firmware writes. Requires only Python's standard lib.
"""
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import struct
import sys

MT = Path(__file__).resolve().parents[1]
ROOT = MT.parents[1]
sys.path[:0] = [str(MT/'micropython'), str(MT/'generated'), str(MT/'tools'),str(ROOT/'software/kagura_runtime')]
import story
from midnight_fm import audio_events
from midnight_show import Show
from memory_gpu import MemoryGPU
from midnight_graphics import Graphics
from package_micropython import package


def compiler():
    env = os.environ.copy()
    if os.name != 'nt':
        return shlex.split(env.get('CC', 'cc')), env
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    vs = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                  'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                  '-property', 'installationPath'], text=True).strip()
    vcvars = Path(vs)/'VC/Auxiliary/Build/vcvars64.bat'
    setup = subprocess.check_output('"{}" >nul && set'.format(vcvars), shell=True, text=True)
    env = {k.upper(): v for k, v in env.items()}
    env.update((k.upper(), v) for k, v in (line.split('=', 1) for line in setup.splitlines()
                                         if '=' in line and not line.startswith('=')))
    return [shutil.which('cl', path=env['PATH'])], env


def library(out, name, sources, exports, external=False):
    cc, env = compiler()
    result = out/(name+('.dll' if os.name == 'nt' else '.so'))
    includes = [MT/'src', MT/'generated']
    if os.name == 'nt':
        cmd = cc+['/nologo', '/O2', '/std:c11', '/experimental:c11atomics', '/LD',
                  '/DKFB_PACK_DESCRIPTOR=1', '/Fo'+str(out)+'/', '/Fe'+str(result)]
        cmd += ['/I'+str(p) for p in includes]
        if external:
            cmd += ['/DMT_EXTERNAL_SCRIPT=1']
        cmd += [str(p) for p in sources]+['/link']+['/EXPORT:'+n for n in exports]
    else:
        cmd = cc+['-O2', '-std=c11', '-shared', '-fPIC', '-DKFB_PACK_DESCRIPTOR=1']
        cmd += ['-I'+str(p) for p in includes]
        if external:
            cmd += ['-DMT_EXTERNAL_SCRIPT=1']
        cmd += [str(p) for p in sources]+['-lm', '-o', str(result)]
    subprocess.run(cmd, env=env, check=True, cwd=out)
    return ct.CDLL(str(result))


def scene_check(out):
    package(out/'app')
    prefix = (MT/'src/pc_main.c').read_text().split('static int8_t *song_l')[0]
    bridge = out/'reference.c'
    bridge.write_text(prefix+'''
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
static kfb_device ref_gpu;
EXPORT int ref_init(void) {
    memset(memory,0,sizeof memory); memset(palette,0,sizeof palette);
    memset(display_palette,0,sizeof display_palette);
    pointer_reg=page=polls=done=pending=device_error=sticky=clock_ms=0;
    tag=0;
    kfb_io io={NULL,read_reg,write_reg,now_ms};
    int rc=kfb_init(&ref_gpu,io,100);
    if(!rc) rc=kfb_probe(&ref_gpu);
    return rc ? rc : show_init(&ref_gpu,NULL);
}
EXPORT int ref_frame(uint32_t ms) { return show_frame(ms); }
EXPORT unsigned ref_page(void) { return page; }
EXPORT const uint8_t *ref_memory(void) { return memory; }
EXPORT const uint16_t *ref_palette(void) { return display_palette; }
''')
    ref = library(out, 'reference', [bridge, MT/'src/mt_show.c', MT/'src/mt_inflate.c',
                  MT/'generated/assets.c', MT.parent/'fm_megademo/src/font.c', MT.parent/'kagura_fb/kagura_fb.c'],
                  ['ref_init', 'ref_frame', 'ref_page', 'ref_memory', 'ref_palette'])
    ref.ref_memory.restype = ct.POINTER(ct.c_ubyte)
    ref.ref_palette.restype = ct.POINTER(ct.c_uint16)
    frames, digest = 0, hashlib.sha256()
    for replay in range(2):
        assert ref.ref_init() == 0
        gpu = Graphics(MemoryGPU(),str(out/'app/mt_data'))
        show = Show(gpu, story)
        show.preload()
        for f in range(story.END_MS*30//1000):
            ms = f*1000//30
            assert ref.ref_frame(ms) == 0
            show.frame(ms)
            expected = ct.string_at(ref.ref_memory(), 230400)
            actual = bytes(gpu.pages[0])+bytes(gpu.pages[1])
            if actual != expected:
                first = next(i for i, (a,b) in enumerate(zip(actual, expected)) if a != b)
                raise AssertionError('pixel mismatch replay=%d ms=%d page=%d x=%d y=%d' %
                                     (replay, ms, first//115200, first%320*2, first%115200//320))
            assert gpu.page == ref.ref_page(), ('page', ms)
            assert gpu.colors == list(ref.ref_palette()[:16]), ('palette', ms)
            digest.update(actual)
            frames += 1
    return dict(frames_compared=frames, replays=2, all_pixels_and_palettes_match=True,
                sha256=digest.hexdigest())


def fm_check(out):
    from kagura_fm import GAIN
    from midnight_instruments import presets,dsp_parameters
    from midnight_music import build_score
    exports = ['fm_init', 'fm_configure', 'fm_configure_pages', 'fm_effects', 'fm_command', 'fm_note_on', 'fm_note_off',
               'fm_all_off', 'fm_render', 'fm_position', 'fm_peak', 'fm_clipped', 'fm_configuration_error']
    # Compare against the committed engine, not a second build of edited code.
    baseline = out/'fm_before_port.c'
    baseline.write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                                 'HEAD:software/midnight_terminal/src/mt_fm.c']))
    ref = library(out, 'fm_reference', [baseline], ['fm_init', 'fm_render', 'fm_position', 'fm_peak', 'fm_clipped'])
    fm = library(out, 'fm_generic', [ROOT/'software/kagura_runtime/native/fm.c'], exports)
    for lib in (ref, fm):
        lib.fm_render.argtypes = [ct.POINTER(ct.c_int8), ct.POINTER(ct.c_int8), ct.c_uint]
    fm.fm_configure.argtypes=[ct.c_void_p,ct.c_size_t,ct.c_void_p,ct.c_size_t]
    fm.fm_effects.argtypes=[ct.c_void_p,ct.c_size_t]
    fm.fm_effects.restype=ct.c_bool
    fm.fm_configure_pages.argtypes=[ct.c_void_p,ct.c_size_t,ct.c_void_p,ct.c_size_t,ct.c_size_t]
    fm.fm_configure_pages.restype=ct.c_bool
    fm.fm_configure.restype = fm.fm_command.restype = fm.fm_note_on.restype = fm.fm_note_off.restype = fm.fm_all_off.restype = ct.c_bool
    patch_data=b''.join(p.pack() for p in presets())
    active_buffers=[]
    effects_data=dsp_parameters()
    effects_buffer=ct.create_string_buffer(effects_data)
    def configure(events,paged=False):
        active_buffers[:]=[ct.create_string_buffer(patch_data)]
        if paged:
            blocks=[ct.create_string_buffer(bytes(events[i:i+1024])) for i in range(0,len(events),1024)]
            pointers=(ct.c_void_p*len(blocks))(*(ct.addressof(b) for b in blocks))
            active_buffers.extend(blocks+[pointers])
            assert fm.fm_configure_pages(active_buffers[0],len(patch_data),pointers,len(blocks),len(events))
        else:
            active_buffers.append(ct.create_string_buffer(bytes(events)))
            assert fm.fm_configure(active_buffers[0],len(patch_data),active_buffers[1],len(events))
        assert fm.fm_effects(effects_buffer,len(effects_data))
    ref.fm_init(); fm.fm_init()
    schedule=build_score(story).data
    configure(schedule)
    buffers = [(ct.c_int8*4096)() for _ in range(4)]
    total, digest = story.END_MS*48, hashlib.sha256()
    first_difference=None
    for start in range(0, total, 4096):
        count = min(4096, total-start)
        ref.fm_render(buffers[0], buffers[1], count)
        fm.fm_render(buffers[2], buffers[3], count)
        for a,b in ((0,2),(1,3)):
            expected, actual = bytes(buffers[a])[:count], bytes(buffers[b])[:count]
            if actual!=expected and first_difference is None:
                first_difference=start+next(i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y)
            digest.update(actual)

    flat_hash=digest.hexdigest()
    fm.fm_init(); configure(schedule,paged=True)
    paged_digest=hashlib.sha256()
    for start in range(0,total,4096):
        count=min(4096,total-start)
        fm.fm_render(buffers[2],buffers[3],count)
        for index in (2,3): paged_digest.update(bytes(buffers[index])[:count])
    assert paged_digest.hexdigest()==flat_hash,'paged command reader must preserve every sample'

    def reset():
        fm.fm_init(); configure(b'')

    assert first_difference is None or first_difference >= 22*16*8000, 'non-random score prefix must retain its samples'

    def render(n):
        a, b = (ct.c_int8*n)(), (ct.c_int8*n)()
        fm.fm_render(a, b, n)
        return bytes(a), bytes(b)

    reset()
    quiet = render(4096)[0]
    assert all(v in (0, 1, 255) for v in quiet) and fm.fm_peak() == 0, 'only signed8 dither is expected before note_on'
    assert fm.fm_note_on(0, 0, 69, 200, 0)
    tone = render(48000)[0]
    assert fm.fm_peak() > 100 and any(2 < v < 254 for v in tone), 'Python note_on must produce samples'
    assert fm.fm_note_off(0)
    released = render(144000)[0]
    signed = lambda b: [v if v < 128 else v-256 for v in b]
    assert sum(abs(v) for v in signed(released[-24000:])) < sum(abs(v) for v in signed(tone[:24000]))/20
    reset(); assert fm.fm_note_on(0, 0, 69, 200, 10)
    gated = render(4096)
    reset(); assert fm.fm_note_on(0, 0, 69, 200, 0)
    prefix = render(480); assert fm.fm_note_off(0)
    suffix = render(4096-480)
    assert gated == tuple(a+b for a,b in zip(prefix, suffix)), 'gate_ms must release at sample time'
    preset_hashes = []
    for instrument in range(8):
        reset(); assert fm.fm_note_on(0, instrument, 60, 200, 0)
        audio = render(8192)[0]
        assert any(audio)
        preset_hashes.append(hashlib.sha256(audio).hexdigest())
    assert len(set(preset_hashes)) == 8
    reset()
    for voice in range(7):
        assert fm.fm_note_on(voice, 0, 48+voice*3, 160, 0)
    assert any(render(8192)[0])
    assert fm.fm_all_off()
    reset()
    for _ in range(32):
        assert fm.fm_note_on(0, 0, 60, 160, 0)
    assert not fm.fm_note_on(0, 0, 60, 160, 0), 'queue overflow must be explicit'
    render(16)
    assert fm.fm_note_on(0, 0, 60, 160, 0)
    assert not fm.fm_note_on(7, 0, 60, 160, 0)
    assert not fm.fm_note_on(0, 8, 60, 160, 0)
    invalid=struct.pack('<IBBBBII',0,GAIN,0,0,0,100,100)+struct.pack('<IBBBBII',16,255,0,0,0,0,0)
    invalid_buffer=ct.create_string_buffer(invalid)
    assert not fm.fm_configure(active_buffers[0],len(patch_data),invalid_buffer,len(invalid))
    assert fm.fm_configuration_error()==1, 'configuration errors must identify the invalid event'
    return dict(score_stereo_frames_rendered=total, python_schedule_bytes=len(schedule),
                paged_schedule_matches=True,
                first_difference_from_legacy_frame=first_difference,
                score_sha256=digest.hexdigest(), live_note_on_off=True, sample_timed_gate=True,
                instruments_verified=8, voices_verified=7, queue_overflow_checked=True,
                invalid_schedule_event_identified=True)


if __name__ == '__main__':
    out = ROOT/'build/midnight-micropython-host-checks'
    out.mkdir(parents=True, exist_ok=True)
    result = dict(scenes=scene_check(out), fm=fm_check(out), hardware_tested=False)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
