import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'software/kagura_fb'),str(ROOT/'software/kagura_fb/tests')]
from kagura_fb import Device
from model import Model
import host_case

class IsolationModel(Model):
    def __init__(self):
        super().__init__()
        self.count=0
        self.wrong_signature=False
        self.bad_injection=False
    def read(self,address,increment,length):
        if address==32:
            return (b'BAD1' if self.wrong_signature else b'ISO1')+bytes((0,1,4))
        if address==36:
            return bytes((self.count | (4 if self.count==2 else 0),))
        return super().read(address,increment,length)
    def finish(self):
        command,data=self.pending
        address=int.from_bytes(command[4:8],'little')
        assert address==300032 and command[1]==1
        if command[0]==5:
            self.memory[address:address+4]=bytes(((address+i)*13+91)&255 for i in range(4))
            if self.bad_injection:self.memory[address]^=1
        else:
            assert data[:4]==bytes.fromhex('ed0f2143')
            assert int.from_bytes(command[8:16],'little')==0xfffffffffffffff0
        self.count+=1
        super().finish()

class HostCaseTests(unittest.TestCase):
    def test_real_device_driver_one_case(self):
        model=IsolationModel();gpu=Device(model,100,model.now);records=[];frames=[]
        host_case.run_one(gpu,records.append,frames.append)
        self.assertEqual([c[0] for c in model.commands],[4,5])
        self.assertEqual(frames,[1,2]);self.assertEqual(records[-1]['stage'],'complete')
    def test_wrong_identity_no_write(self):
        model=IsolationModel();gpu=Device(model,100,model.now);model.wrong_signature=True
        with self.assertRaises(ValueError):host_case.run_write(gpu,lambda r:None)
        self.assertEqual(model.commands,[])
    def test_bad_first_trace_prevents_read(self):
        model=IsolationModel();gpu=Device(model,100,model.now)
        def reject(index):raise ValueError('bad UART CRC')
        with self.assertRaises(ValueError):host_case.run_one(gpu,lambda r:None,reject)
        self.assertEqual([c[0] for c in model.commands],[4])
    def test_bad_download_stops_and_logs(self):
        model=IsolationModel();gpu=Device(model,100,model.now);model.bad_injection=True;records=[]
        with self.assertRaises(ValueError):host_case.run_one(gpu,records.append,lambda i:None)
        self.assertEqual(records[-1]['stage'],'independent_download')
        self.assertEqual(records[-1]['xor'],'01000000')
        self.assertEqual(len(model.commands),2)

if __name__=='__main__':unittest.main()
