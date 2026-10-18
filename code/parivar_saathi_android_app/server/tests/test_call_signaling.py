import io
import json
import os
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from call_signaling import VoiceCalls, Principal, VoiceConflict, VoiceDenied, CallApi


class Directory:
    def __init__(self): self.revoked=False
    def primary_caregiver(self,home_id): return 'caregiver_one' if home_id=='home_one' else None
    def caregiver_is_current(self,home_id,caregiver_id): return not self.revoked and home_id=='home_one' and caregiver_id=='caregiver_one'
    def hub_is_current(self,home_id,hub_id,epoch): return home_id=='home_one' and hub_id=='hub_one' and epoch==3


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=1000
        self.directory=Directory()
        self.voice=VoiceCalls(os.path.join(self.tmp.name,'calls.db'),self.directory,lambda:self.now)
        self.hub=Principal('hub_one','home_one','hub',3)
        self.care=Principal('caregiver_one','home_one','caregiver',3)

    def tearDown(self):
        self.voice.db.close()
        self.tmp.cleanup()

    def test_policy_gate_and_dedup_persistent(self):
        with self.assertRaises(VoiceDenied): self.voice.originate(self.hub,'incident_one',eligible=False)
        call=self.voice.originate(self.hub,'incident_one',eligible=True)
        self.assertEqual(call['state'],'REQUESTED')
        self.assertEqual(call['call_id'],self.voice.originate(self.hub,'incident_one',eligible=True)['call_id'])
        self.assertEqual(len(self.voice.claim_push_jobs()),1)
        self.assertEqual(self.voice.claim_push_jobs(),[])
        after_reboot=VoiceCalls(os.path.join(self.tmp.name,'calls.db'),self.directory,lambda:self.now)
        self.assertEqual(after_reboot.originate(self.hub,'incident_one',eligible=True)['call_id'],call['call_id'])
        after_reboot.db.close()

    def test_sdp_two_way_signaling_and_ice(self):
        call=self.voice.originate(self.hub,'incident_hello',eligible=True)
        cid=call['call_id']
        self.voice.action(self.care,cid,'accept')
        with self.assertRaises(VoiceConflict): self.voice.action(self.care,cid,'offer',{'sdp':'v=0\na=abc' * 4})
        self.voice.action(self.hub,cid,'offer',{'sdp':'v=0\na=sendrecv\na=mid:0\n'})
        self.assertIn('v=0',self.voice.status(self.care,cid)['offer'])
        self.assertIsNone(self.voice.status(self.hub,cid)['offer'])
        self.voice.action(self.care,cid,'answer',{'sdp':'v=0\na=recvonly\na=mid:0\n'})
        self.assertEqual(self.voice.status(self.hub,cid)['state'],'CONNECTING')
        self.voice.action(self.care,cid,'media_ready')
        self.assertEqual(self.voice.status(self.care,cid)['state'],'CONNECTING')
        self.voice.action(self.hub,cid,'media_ready')
        self.assertEqual(self.voice.status(self.hub,cid)['state'],'CONNECTED')
        self.voice.action(self.hub,cid,'ice',{'candidate':{'candidate':'candidate:1 1 udp 1 127.0.0.1 9000 typ host','sdpMid':'0'}})
        self.assertEqual(len(self.voice.candidates(self.care,cid)),1)
        self.assertEqual(len(self.voice.candidates(self.hub,cid)),0)
        self.voice.action(self.hub,cid,'end',{'reason':'hangup'})
        with self.assertRaises(VoiceConflict): self.voice.action(self.care,cid,'answer',{'sdp':'v=0\na=x'*8})

    def test_revocation_other_home_epoch_and_timeout(self):
        cid=self.voice.originate(self.hub,'incident_three',eligible=True)['call_id']
        for invalid in (Principal('caregiver_two','home_one','caregiver',3), Principal('caregiver_one','home_two','caregiver',3), Principal('caregiver_one','home_one','caregiver',2)):
            with self.assertRaises(VoiceDenied): self.voice.status(invalid,cid)
        self.now += 200
        self.assertEqual(self.voice.status(self.care,cid)['state'],'EXPIRED')
        with self.assertRaises(VoiceConflict):self.voice.action(self.care,cid,'accept')
        self.directory.revoked=True
        with self.assertRaises(VoiceDenied):self.voice.status(self.care,cid)

    def test_register_device_and_api_no_actor_spoof(self):
        self.voice.register_device(self.care,'device_one','x'*50)
        self.assertEqual(self.voice.db.execute('select count(*) from push_tokens').fetchone()[0],1)
        api=CallApi(self.voice)
        def send(actor=None,approved=None,body=None):
            response=[]
            raw=json.dumps(body or {'incident_id':'incident_four','policy_approved':True}).encode()
            env={'REQUEST_METHOD':'POST','PATH_INFO':'/v1/voice/calls','wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw))}
            if actor: env['gs.verified_voice_actor']=actor
            if approved: env['gs.verified_incident_call_approval']=approved
            api(env,lambda status,headers:response.append(status))
            return response[0]
        self.assertTrue(send().startswith('403'))
        self.assertTrue(send(actor=self.hub).startswith('403'))
        approval={'home_id':'home_one','incident_id':'incident_four','ownership_epoch':3,'auto_call_eligible':True}
        self.assertTrue(send(actor=self.hub,approved=approval).startswith('200'))
        self.assertTrue(send(actor=self.care,approved=approval).startswith('403'))


if __name__=='__main__': unittest.main()
