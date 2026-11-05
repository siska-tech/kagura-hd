"""No serial/JTAG dependencies; exercise actual generated MicroPython source."""
import unittest
import zlib
from showcase_segmented_readback import *


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.expected = bytes(((i*17) ^ (i>>8)) & 255 for i in range(PAGE_BYTES))

    def record(self, page=0, offset=0):
        return dict(event='readback_segment', id='T', address=page*PAGE_BYTES+offset,
                    length=512, actual=self.expected[offset:offset+512].hex(), elapsed_us=123)

    def test_both_pages_exact_coverage(self):
        for page in (0, 1):
            v = Validator('T', page, self.expected)
            self.assertEqual(len(segments(page)), 225)
            for address, length in segments(page):
                self.assertEqual(length, 512)
                v.accept(self.record(page, address-page*PAGE_BYTES))
            self.assertEqual(v.finish(), zlib.crc32(self.expected))

    def test_generated_code_reads_eight_transfers(self):
        outer = self
        class Device:
            calls = []
            def read_into(self, address, buffer):
                self.calls.append(address)
                buffer[:] = outer.expected[address:address+64]
        class Clock:
            ticks_us = staticmethod(lambda: 100)
            ticks_diff = staticmethod(lambda a, b: a-b)
        import binascii
        records=[]
        dev=Device()
        exec(source('T', 512, 512), dict(_dev=dev, time=Clock, binascii=binascii, _sc=records.append))
        self.assertEqual(dev.calls, list(range(512,1024,64)))
        self.assertEqual(records[0]['actual'], self.expected[512:1024].hex())

    def test_corruption_preserved_and_latched(self):
        v=Validator('T',0,self.expected);r=self.record();r['actual']='ff'+r['actual'][2:]
        with self.assertRaises(ValueError):v.accept(r)
        self.assertEqual(v.records[0]['error_byte_positions'],[0])
        with self.assertRaises(RuntimeError):v.accept(self.record())
        with self.assertRaises(ValueError):v.finish()

    def test_incomplete_duplicate_order_and_malformed(self):
        for mutation in ('missing','wrong_id','wrong_length','bad_hex','negative_time','duplicate'):
            with self.subTest(mutation=mutation):
                v=Validator('T',0,self.expected);r=self.record()
                if mutation=='missing':r['address']=512
                if mutation=='wrong_id':r['id']='OTHER'
                if mutation=='wrong_length':r['length']=64
                if mutation=='bad_hex':r['actual']='00'
                if mutation=='negative_time':r['elapsed_us']=-1
                if mutation=='duplicate':v.accept(r)
                with self.assertRaises(ValueError):v.accept(r)
        with self.assertRaises(ValueError):Validator('T',0,self.expected).finish()

    def test_invalid_job_boundaries(self):
        for address,length in ((-64,64),(0,0),(0,576),(1,64),(230400,64)):
            with self.assertRaises(ValueError):source('T',address,length)


if __name__=='__main__':unittest.main()
