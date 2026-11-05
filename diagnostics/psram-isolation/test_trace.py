import unittest
import struct
import zlib
from pathlib import Path
from decode_trace import decode

ROOT=Path(__file__).resolve().parents[2]

class TraceTests(unittest.TestCase):
    def test_actual_uart_and_oracle(self):
        for lanes in (1,4):
            raw=(ROOT/f'build/psram-isolation/board-sim/uart-l{lanes}-b0.bin').read_bytes()
            frames=decode(raw)
            self.assertEqual(len(frames),2)
            for f in frames:
                self.assertEqual((f['test_id'],f['address'],f['words'],f['fault']),(1,300032,1,False))
            self.assertEqual(frames[0]['mask'],'fffffffffffffff0')
            self.assertEqual(frames[1]['mask'],'0000000000000000')
            self.assertEqual(frames[0]['data'],'ed0f2143')
            self.assertEqual(frames[1]['data'],bytes(((300032+i)*13+91)&255 for i in range(4)).hex())
            self.assertEqual(frames[0]['payload64'][8:],'00'*60)
    def test_bad_request_freeze(self):
        raw=(ROOT/'build/psram-isolation/board-sim/uart-l4-b1.bin').read_bytes()
        frame,=decode(raw)
        self.assertTrue(frame['fault'])
        self.assertEqual(frame['address'],300036)
    def test_reject_corruption_truncation_extra(self):
        raw=(ROOT/'build/psram-isolation/board-sim/uart-l4-b0.bin').read_bytes()
        for data in (b'',raw[:-1],raw+b'x',raw+raw,raw[:20]+bytes([raw[20]^1])+raw[21:]):
            with self.assertRaises(ValueError):decode(data)
    def test_semantic_invalid_with_correct_crc(self):
        raw=bytearray((ROOT/'build/psram-isolation/board-sim/uart-l4-b0.bin').read_bytes()[:136])
        raw[5]=3
        raw[-4:]=struct.pack('<I',zlib.crc32(raw[:-4]))
        with self.assertRaises(ValueError):decode(raw)

if __name__=='__main__':unittest.main()
