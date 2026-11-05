import unittest
from pathlib import Path
from decode import decode
root=Path(__file__).resolve().parents[2]/'build/host-window-observe/sim'
class Tests(unittest.TestCase):
 def test_six_boundaries_and_counts(self):
  for lanes in (1,4):
   result=decode((root/f'uart-l{lanes}-n0.bin').read_bytes())
   self.assertTrue(result['all_six_match']);self.assertEqual(result['flags'],0)
   self.assertFalse(result['header_fault'])
   for key in ('rx_count','write_count','csr_count','tx_count','read_count'):self.assertEqual(result[key],4)
 def test_timeout_snapshot(self):
  result=decode((root/'uart-l4-n1.bin').read_bytes())
  self.assertEqual(result['flags'],128);self.assertTrue(result['header_fault'])
  self.assertEqual(result['write_count'],0)
 def test_corruption_and_truncation(self):
  raw=(root/'uart-l4-n0.bin').read_bytes()
  for value in (b'',raw[:-1],raw+b'x',raw[:50]+bytes((raw[50]^1,))+raw[51:]):
   with self.assertRaises(ValueError):decode(value)
if __name__=='__main__':unittest.main()
