import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from call_signaling import VoiceCalls,Principal
from push_adapter import PushWorker
from test_call_signaling import Directory

class Sender:
    def __init__(self):self.sent=[]
    def send_voice_invite(self,token,call_id):
        self.sent.append((token,call_id))
        return 'provider-accepted-id'

class PushTests(unittest.TestCase):
    def test_fcm_dispatch_outbox_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Directory();now=[123];s=VoiceCalls(os.path.join(tmp,'x.sqlite'),d,lambda:now[0])
            care=Principal('caregiver_one','home_one','caregiver',3)
            hub=Principal('hub_one','home_one','hub',3)
            s.register_device(care,'android_1','x'*60)
            cid=s.originate(hub,'i10',eligible=True)['call_id']
            sender=Sender();worker=PushWorker(s,sender)
            self.assertEqual(worker.deliver_once()[0]['state'],'FCM_ACCEPTED')
            self.assertEqual(sender.sent,[('x'*60,cid)])
            self.assertEqual(worker.deliver_once(),[])
            s.db.close()
    def test_revoked_contact_never_pushed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Directory();s=VoiceCalls(os.path.join(tmp,'x.sqlite'),d,lambda:123)
            s.register_device(Principal('caregiver_one','home_one','caregiver',3),'a1','y'*60)
            s.originate(Principal('hub_one','home_one','hub',3),'i11',eligible=True)
            d.revoked=True
            sender=Sender(); self.assertEqual(PushWorker(s,sender).deliver_once()[0]['state'],'SKIPPED')
            self.assertEqual(sender.sent,[])
            s.db.close()

if __name__=='__main__':unittest.main()
