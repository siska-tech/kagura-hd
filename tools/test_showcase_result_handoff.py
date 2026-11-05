import unittest
from showcase_result_handoff import read_result


class HandoffTests(unittest.TestCase):
    def test_transient_access_does_not_reissue_job(self):
        class Artifact:
            count=0
            def read_text(self,**kw):
                self.count+=1
                if self.count<3:raise PermissionError('sharing denied')
                return '{"ok": true}'
        artifact=Artifact();waits=[]
        self.assertEqual(read_result(artifact,1,clock=lambda:0,pause=waits.append),{'ok':True})
        self.assertEqual(artifact.count,3);self.assertEqual(waits,[.05,.05])
    def test_deadline_and_malformed_still_stop(self):
        class Denied:
            def read_text(self,**kw):raise PermissionError('persistent')
        with self.assertRaises(PermissionError):read_result(Denied(),1,clock=lambda:1)
        class Malformed:
            def read_text(self,**kw):return 'invalid'
        with self.assertRaises(ValueError):read_result(Malformed(),1)


if __name__=='__main__':unittest.main()
