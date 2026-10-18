"""GS-157 pluggable FCM delivery worker; install only with approved credentials.

A provider 'success' is not proof that Android displayed the invite or a human
answered the call. Worker is intended for a trusted backend process only.
"""
from __future__ import annotations

from typing import Protocol
from call_signaling import VoiceCalls, ACTIVE


class PushSender(Protocol):
    def send_voice_invite(self, token: str, call_id: str) -> str: ...


class FirebaseAdminPushSender:
    """Uses default application credentials from trusted backend provisioning.

    pip install firebase-admin and configure a dedicated least-privilege
    Firebase project. Never bundle service keys in Android or public Git.
    """

    def send_voice_invite(self, token: str, call_id: str) -> str:
        from firebase_admin import messaging
        msg = messaging.Message(
            token=token,
            data={"type":"voice_invite", "call_id":call_id},
            android=messaging.AndroidConfig(priority="high", ttl=60),
        )
        return messaging.send(msg)


class PushWorker:
    def __init__(self, calls: VoiceCalls, sender: PushSender):
        self.calls, self.sender = calls, sender

    def deliver_once(self, limit: int=10) -> list[dict]:
        results=[]
        for job in self.calls.claim_push_jobs(limit=limit):
            with self.calls.lock:
                row=self.calls.db.execute("SELECT * FROM calls WHERE call_id=?",(job['call_id'],)).fetchone()
                if not row or row['state'] not in ACTIVE or self.calls.clock() >= row['expires_at'] or not self.calls.directory.caregiver_is_current(row['home_id'],row['caregiver_id']):
                    self.calls.db.execute("UPDATE delivery_outbox SET state='SKIPPED' WHERE id=?",(job['id'],))
                    results.append({'job_id':job['id'],'state':'SKIPPED'})
                    continue
                tokens=self.calls.db.execute("SELECT token FROM push_tokens WHERE home_id=? AND caregiver_id=?",(row['home_id'],row['caregiver_id'])).fetchall()
            if not tokens:
                with self.calls.lock:
                    self.calls.db.execute("UPDATE delivery_outbox SET state='NO_REGISTERED_DEVICE' WHERE id=?",(job['id'],))
                results.append({'job_id':job['id'],'state':'NO_REGISTERED_DEVICE'})
                continue
            succeeded=False
            for t in tokens:
                try:
                    receipt=self.sender.send_voice_invite(t['token'],job['call_id'])
                    if isinstance(receipt,str) and receipt:
                        succeeded=True
                except Exception:
                    # Never expose recipient device token or provider error internals.
                    pass
            with self.calls.lock:
                self.calls.db.execute("UPDATE delivery_outbox SET state=? WHERE id=?",('FCM_ACCEPTED' if succeeded else 'PROVIDER_FAILED',job['id']))
            results.append({'job_id':job['id'],'state':'FCM_ACCEPTED' if succeeded else 'PROVIDER_FAILED'})
        return results
