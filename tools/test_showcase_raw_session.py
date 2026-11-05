import unittest
from showcase_raw_session import RawSession


class Port:
    def __init__(self, response):
        self.response=bytearray(response);self.writes=[];self.closed=False
    def write(self, data):
        self.writes.append(data);return len(data)
    def read(self, length):
        data=self.response[:length];del self.response[:length];return bytes(data)
    def close(self):self.closed=True


class SessionTests(unittest.TestCase):
    def session(self,response):
        p=Port(response);ticks=iter(i/100 for i in range(10000))
        return p,RawSession(p,clock=lambda:next(ticks),pause=lambda _:None)
    def test_success_and_no_replay(self):
        p,s=self.session(b'OKhello\x04\x04>')
        self.assertEqual(s.transfer('T',b'print(1)'),b'hello')
        self.assertFalse(p.closed)
        with self.assertRaises(RuntimeError):s.transfer('T',b'print(1)')
    def test_timeout_preserves_partial_closes_and_rejects_recovery(self):
        p,s=self.session(b'OKpartial')
        with self.assertRaises(TimeoutError):s.transfer('T',b'print(1)',.2)
        self.assertEqual(s.raw,b'OKpartial');self.assertTrue(p.closed)
        writes=list(p.writes)
        with self.assertRaises(RuntimeError):s.transfer('RECOVERY',b'pass')
        self.assertEqual(writes,p.writes)
    def test_device_exception_closes(self):
        p,s=self.session(b'OK\x04Traceback\x04>')
        with self.assertRaisesRegex(RuntimeError,'Traceback'):s.transfer('T',b'pass')
        self.assertTrue(p.closed)
    def test_bad_ack_stops(self):
        p,s=self.session(b'badOK')
        with self.assertRaises(ValueError):s.transfer('T',b'pass')
        self.assertTrue(p.closed)
    def test_external_abort_closes(self):
        p,s=self.session(b'OK');s.should_abort=lambda:True
        with self.assertRaises(TimeoutError):s.transfer('T',b'pass')
        self.assertTrue(p.closed)


if __name__=='__main__':unittest.main()
