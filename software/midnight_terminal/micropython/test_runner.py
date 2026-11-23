"""Host tests for Python-owned playback, live FM API and resource cleanup."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'generated'), str(ROOT/'tools'), str(ROOT.parent/'kagura_runtime')]
import story
import midnight_terminal as runner
from midnight_fm import Synth, audio_events, KEY
from midnight_show import Show, Text
from memory_gpu import MemoryGPU


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.clock = 133000000
        self.clock_changes = []

        def frequency(value=None):
            if value is not None:
                self.clock = value
                self.clock_changes.append(value)
            return self.clock

        self.context = patch.dict(sys.modules, {'machine': types.SimpleNamespace(freq=frequency)})
        self.context.start()
        self.addCleanup(self.context.stop)

    def test_complete_python_timeline_and_replay(self):
        gpu = MemoryGPU()
        for _ in range(2):
            result = runner.run(backend=gpu)
            self.assertEqual(len(result['scene_frames']), 7)
            self.assertTrue(all(result['scene_frames']))
            self.assertEqual(sum(result['scene_frames']), result['frames'])
            self.assertTrue(gpu.closed)
        self.assertEqual(self.clock, 133000000)
        self.assertEqual(self.clock_changes, [120000000, 133000000]*2)

    def test_python_script_edits_change_text_and_sound_schedule(self):
        changed = types.SimpleNamespace(**{k: getattr(story, k) for k in dir(story) if not k.startswith('_')})
        changed.DIALOGUE = [(13600, 'mio', '雨雨雨雨')]+story.DIALOGUE[1:]
        self.assertNotEqual(audio_events(changed), audio_events(story))
        gpu = MemoryGPU()
        show = Show(gpu, changed)
        show.preload()
        show.frame(13645)
        self.assertEqual(show.dialogue_drawn, 2)
        self.assertEqual(show.dialogues[0][1].length, 4)

    def test_live_fm_presets_and_polyphony(self):
        gpu = MemoryGPU()
        with Synth(backend=gpu) as synth:
            self.assertFalse(gpu.score)
            for voice, note in enumerate((60, 64, 67)):
                synth.note_on(note, voice=voice, instrument='ep', velocity=180, gate_ms=400)
            synth.sleep_ms(600)
            synth.note_off(1)
            synth.all_off()
        self.assertEqual(gpu.notes[0], ('on', 0, 0, 60, 180, 400))
        self.assertEqual(gpu.notes[-2:], [('off', 1), ('all_off',)])
        self.assertTrue(gpu.closed)
        self.assertEqual(self.clock, 133000000)

    def test_cleanup_at_every_playback_stage(self):
        for stage in ('start', 'image', 'text', 'wait_until', 'check'):
            for error in (KeyboardInterrupt(), OSError('bus fault')):
                gpu = MemoryGPU()
                def fail(*args):
                    raise error
                setattr(gpu, stage, fail)
                with self.assertRaises(type(error)):
                    runner.run(backend=gpu)
                self.assertTrue(gpu.closed, stage)
                self.assertEqual(self.clock, 133000000, stage)

    def test_open_failure_does_not_close_another_session(self):
        gpu = MemoryGPU()
        def busy(*args):
            raise OSError('core1 occupied')
        gpu.open = busy
        with self.assertRaises(OSError):
            runner.run(backend=gpu)
        self.assertFalse(gpu.closed)
        self.assertEqual(self.clock, 133000000)

    def test_unknown_glyph_rejected_before_hardware_is_opened(self):
        with self.assertRaises(ValueError):
            Text('🐈')

    def test_python_cues_follow_terminal_edits(self):
        changed = types.SimpleNamespace(**{k: getattr(story, k) for k in dir(story) if not k.startswith('_')})
        changed.TERMINAL = [(46000, 'ABC')]
        cues = [e for e in audio_events(changed) if 46000 <= e[0] < 47000]
        self.assertEqual(cues, [(46000, KEY, 0), (46032, KEY, 1), (46064, KEY, 2)])

    def test_skipped_frames_and_bounds(self):
        gpu = MemoryGPU()
        show = Show(gpu, story)
        show.preload()
        for ms in (0, 32000, 45000, 58499, 73999, 81000, 94500, 94800, 103999):
            show.frame(ms)
        self.assertEqual(show.scene, 6)
        with self.assertRaises(ValueError):
            show.frame(100)


if __name__ == '__main__':
    unittest.main()
