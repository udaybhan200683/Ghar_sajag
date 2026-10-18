"""GS-157 isolated calling contract; no production authentication or push provider installed.

Never mount CallApi directly on an untrusted HTTP listener: a verified principal
must be injected by production trusted authentication middleware.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import secrets
import sqlite3
import threading
import time
from typing import Callable, Protocol

ID = re.compile(r"^[a-zA-Z0-9_-]{1,96}$")
ACTIVE = ("REQUESTED", "RINGING", "ACCEPTED", "CONNECTING", "CONNECTED")
TERMINAL = ("DECLINED", "ENDED", "FAILED", "EXPIRED")


class VoiceDenied(PermissionError):
    pass


class VoiceConflict(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    """Injected by verified authentication middleware only; NOT a bearer credential."""
    identity: str
    home_id: str
    role: str  # exact allowed: hub / caregiver
    ownership_epoch: int


class Directory(Protocol):
    def primary_caregiver(self, home_id: str) -> str | None: ...
    def caregiver_is_current(self, home_id: str, caregiver_id: str) -> bool: ...
    def hub_is_current(self, home_id: str, hub_id: str, epoch: int) -> bool: ...


class VoiceCalls:
    """Transactional, incident-deduplicated WebRTC signaling state.

    Uses server-clock TTL and transactional delivery outbox. A worker can consume
    queued notifications, but PUSH_ENQUEUED is never described as RINGING/ANSWERED.
    """

    def __init__(self, db_path: str, directory: Directory, clock: Callable[[], int] | None = None):
        self.db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.lock = threading.RLock()
        self.directory = directory
        self.clock = clock or (lambda: int(time.time()))
        with self.lock:
            self.db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS calls (
                  call_id TEXT PRIMARY KEY, home_id TEXT NOT NULL, incident_id TEXT NOT NULL,
                  hub_id TEXT NOT NULL, caregiver_id TEXT NOT NULL, epoch INTEGER NOT NULL,
                  state TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                  revision INTEGER NOT NULL DEFAULT 0,
                  hub_media_ready INTEGER NOT NULL DEFAULT 0,
                  caregiver_media_ready INTEGER NOT NULL DEFAULT 0,
                  offer TEXT, answer TEXT, ended_reason TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_incident ON calls(home_id,incident_id);
                CREATE TABLE IF NOT EXISTS ice (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL,
                  sender TEXT NOT NULL, payload TEXT NOT NULL,
                  FOREIGN KEY(call_id) REFERENCES calls(call_id)
                );
                CREATE TABLE IF NOT EXISTS delivery_outbox (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL,
                  caregiver_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'QUEUED',
                  attempts INTEGER NOT NULL DEFAULT 0,
                  FOREIGN KEY(call_id) REFERENCES calls(call_id)
                );
                CREATE TABLE IF NOT EXISTS push_tokens (
                  caregiver_id TEXT NOT NULL, home_id TEXT NOT NULL,
                  device_id TEXT NOT NULL, token TEXT NOT NULL,
                  PRIMARY KEY(caregiver_id,home_id,device_id)
                );
            """)

    def _check(self, value: str):
        if not isinstance(value, str) or not ID.fullmatch(value):
            raise VoiceConflict("invalid_identifier")

    def _row(self, call_id: str) -> sqlite3.Row:
        self._check(call_id)
        row = self.db.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
        if row is None:
            raise KeyError("unknown_call")
        return row

    def _principal(self, row: sqlite3.Row, who: Principal):
        if not isinstance(who, Principal) or who.home_id != row["home_id"] or who.ownership_epoch != row["epoch"]:
            raise VoiceDenied("unauthorized_home_or_epoch")
        if who.role == "hub":
            if who.identity != row["hub_id"] or not self.directory.hub_is_current(who.home_id, who.identity, who.ownership_epoch):
                raise VoiceDenied("hub_not_current")
        elif who.role == "caregiver":
            if who.identity != row["caregiver_id"] or not self.directory.caregiver_is_current(who.home_id, who.identity):
                raise VoiceDenied("caregiver_not_current")
        else:
            raise VoiceDenied("invalid_role")

    def _expire(self, row: sqlite3.Row):
        if row["state"] in ACTIVE and self.clock() >= row["expires_at"]:
            self.db.execute("UPDATE calls SET state='EXPIRED', revision=revision+1, ended_reason='deadline' WHERE call_id=?", (row["call_id"],))
            return self._row(row["call_id"])
        return row

    def _public(self, row: sqlite3.Row) -> dict:
        return {k:row[k] for k in ("call_id", "incident_id", "state", "revision", "created_at", "expires_at")}

    def originate(self, who: Principal, incident_id: str, *, eligible: bool, lifetime_s: int = 120) -> dict:
        """Call only from an approved incident-policy engine after AUTO_CALL gate."""
        self._check(incident_id)
        if not isinstance(who, Principal) or who.role != "hub" or not eligible or not self.directory.hub_is_current(who.home_id, who.identity, who.ownership_epoch):
            raise VoiceDenied("hub_or_policy_not_authorized")
        if not isinstance(lifetime_s, int) or not 15 <= lifetime_s <= 600:
            raise VoiceConflict("invalid_lifetime")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute("SELECT * FROM calls WHERE home_id=? AND incident_id=?",(who.home_id,incident_id)).fetchone()
                if row:
                    # Same incident is one logical call. No automated redial without a
                    # new explicitly authorized follow-up attempt domain.
                    if row["hub_id"] != who.identity or row["epoch"] != who.ownership_epoch:
                        raise VoiceDenied("incident_owner_mismatch")
                    self.db.execute("COMMIT")
                    return self._public(row)
                caregiver = self.directory.primary_caregiver(who.home_id)
                if not caregiver or not self.directory.caregiver_is_current(who.home_id, caregiver):
                    raise VoiceDenied("missing_authorized_caregiver")
                self._check(caregiver)
                call_id = "c_" + secrets.token_hex(16)
                now = self.clock()
                self.db.execute("INSERT INTO calls(call_id,home_id,incident_id,hub_id,caregiver_id,epoch,state,created_at,expires_at) VALUES(?,?,?,?,?,?,'REQUESTED',?,?)",(call_id,who.home_id,incident_id,who.identity,caregiver,who.ownership_epoch,now,now+lifetime_s))
                self.db.execute("INSERT INTO delivery_outbox(call_id,caregiver_id) VALUES(?,?)",(call_id,caregiver))
                self.db.execute("COMMIT")
                return self._public(self._row(call_id))
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def status(self, who: Principal, call_id: str) -> dict:
        with self.lock:
            row = self._row(call_id)
            self._principal(row,who)
            row = self._expire(row)
            return {**self._public(row),"offer":row["offer"] if who.role=="caregiver" else None,"answer":row["answer"] if who.role=="hub" else None}

    def action(self, who: Principal, call_id: str, name: str, body: dict | None = None) -> dict:
        if name not in ("accept","decline","offer","answer","ice","media_ready","end"):
            raise VoiceConflict("unknown_action")
        body = body or {}
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self._row(call_id)
                self._principal(row,who)
                row = self._expire(row)
                if row["state"] in TERMINAL:
                    raise VoiceConflict("call_closed")
                state = row["state"]
                if name == "accept":
                    if who.role != "caregiver" or state not in ("REQUESTED","RINGING"):
                        raise VoiceConflict("invalid_accept")
                    self.db.execute("UPDATE calls SET state='ACCEPTED',revision=revision+1 WHERE call_id=?",(call_id,))
                elif name == "decline":
                    if who.role != "caregiver" or state not in ("REQUESTED","RINGING"):
                        raise VoiceConflict("invalid_decline")
                    self.db.execute("UPDATE calls SET state='DECLINED',revision=revision+1 WHERE call_id=?",(call_id,))
                elif name == "offer":
                    if who.role != "hub" or state not in ("ACCEPTED","CONNECTING") or row["offer"] is not None:
                        raise VoiceConflict("invalid_offer")
                    sdp = body.get("sdp")
                    if not isinstance(sdp,str) or not 20 <= len(sdp) <= 30000 or not sdp.startswith("v=0"):
                        raise VoiceConflict("invalid_offer_sdp")
                    self.db.execute("UPDATE calls SET offer=?,state='CONNECTING',revision=revision+1 WHERE call_id=?",(sdp,call_id))
                elif name == "answer":
                    if who.role != "caregiver" or state != "CONNECTING" or row["offer"] is None or row["answer"] is not None:
                        raise VoiceConflict("invalid_answer")
                    sdp = body.get("sdp")
                    if not isinstance(sdp,str) or not 20 <= len(sdp) <= 30000 or not sdp.startswith("v=0"):
                        raise VoiceConflict("invalid_answer_sdp")
                    self.db.execute("UPDATE calls SET answer=?,state='CONNECTING',revision=revision+1 WHERE call_id=?",(sdp,call_id))
                elif name == "media_ready":
                    if state != "CONNECTING" or row["offer"] is None or row["answer"] is None:
                        raise VoiceConflict("media_not_negotiated")
                    field = "hub_media_ready" if who.role == "hub" else "caregiver_media_ready"
                    self.db.execute(f"UPDATE calls SET {field}=1,revision=revision+1 WHERE call_id=?",(call_id,))
                    current=self._row(call_id)
                    if current["hub_media_ready"] and current["caregiver_media_ready"]:
                        self.db.execute("UPDATE calls SET state='CONNECTED',revision=revision+1 WHERE call_id=?",(call_id,))
                elif name == "ice":
                    if state not in ("CONNECTING","CONNECTED"):
                        raise VoiceConflict("ice_before_offer")
                    candidate = body.get("candidate")
                    if not isinstance(candidate,dict) or len(json.dumps(candidate)) > 3000 or not isinstance(candidate.get("candidate"),str) or len(candidate["candidate"])>2048:
                        raise VoiceConflict("invalid_ice")
                    self.db.execute("INSERT INTO ice(call_id,sender,payload) VALUES(?,?,?)",(call_id,who.role,json.dumps(candidate,separators=(',',':'))))
                else: # end
                    reason = body.get("reason","ended")
                    if reason not in ("ended","network_failure","hangup","timeout"):
                        raise VoiceConflict("invalid_end_reason")
                    self.db.execute("UPDATE calls SET state='ENDED',ended_reason=?,revision=revision+1 WHERE call_id=?",(reason,call_id))
                self.db.execute("COMMIT")
                return self.status(who,call_id)
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def candidates(self, who: Principal, call_id: str, after_id: int = 0) -> list[dict]:
        with self.lock:
            row=self._row(call_id)
            self._principal(row,who)
            if not isinstance(after_id,int) or after_id < 0:
                raise VoiceConflict("invalid_cursor")
            rows=self.db.execute("SELECT id,payload FROM ice WHERE call_id=? AND sender!=? AND id>? ORDER BY id LIMIT 100",(call_id,who.role,after_id)).fetchall()
            return [{"id":r["id"],"candidate":json.loads(r["payload"])} for r in rows]

    def register_device(self, who: Principal, device_id: str, token: str) -> None:
        self._check(device_id)
        if not isinstance(who,Principal) or who.role!="caregiver" or not self.directory.caregiver_is_current(who.home_id,who.identity):
            raise VoiceDenied("caregiver_not_authorized")
        if not isinstance(token,str) or not 30<=len(token)<=4096 or any(c.isspace() for c in token):
            raise VoiceConflict("invalid_fcm_token")
        with self.lock:
            self.db.execute("INSERT INTO push_tokens(caregiver_id,home_id,device_id,token) VALUES(?,?,?,?) ON CONFLICT(caregiver_id,home_id,device_id) DO UPDATE SET token=excluded.token",(who.identity,who.home_id,device_id,token))

    def claim_push_jobs(self, limit: int = 10) -> list[dict]:
        """Trusted push worker only, NOT exposed to caregiver/Hub HTTP routes."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                jobs=self.db.execute("SELECT id,call_id,caregiver_id FROM delivery_outbox WHERE state='QUEUED' ORDER BY id LIMIT ?",(limit,)).fetchall()
                for row in jobs:
                    self.db.execute("UPDATE delivery_outbox SET state='CLAIMED',attempts=attempts+1 WHERE id=?",(row["id"],))
                self.db.execute("COMMIT")
                return [dict(j) for j in jobs]
            except BaseException:
                self.db.execute("ROLLBACK")
                raise


class CallApi:
    """WSGI fragment with trusted middleware principal in environ['gs.verified_voice_actor'].

    Not to be deployed before a real session verifier and trusted Hub identity
    authority (GS-143/GS-68/GS-109) have been connected. HTTPS and CSRF defense
    belong at the production front door. No X-Actor-Id, demo actor, or open CORS.
    """
    def __init__(self, service: VoiceCalls, ice_config_provider: Callable[[Principal], dict] | None = None):
        self.service = service
        self.ice_config_provider = ice_config_provider

    def __call__(self, environ, start_response):
        try:
            who=environ.get("gs.verified_voice_actor")
            if not isinstance(who,Principal):
                raise VoiceDenied("verified_authentication_required")
            method=environ.get("REQUEST_METHOD", "GET")
            path=environ.get("PATH_INFO", "")
            parts=path.strip("/").split("/")
            if parts[:2] != ["v1","voice"]:
                raise KeyError("not_found")
            body={}
            if method=="POST":
                length=int(environ.get("CONTENT_LENGTH",0))
                if not 0<=length<=40000:
                    raise VoiceConflict("invalid_body_size")
                body=json.loads(environ["wsgi.input"].read(length) or b"{}")
                if not isinstance(body,dict):
                    raise VoiceConflict("invalid_body")
            if parts==["v1","voice","ice-config"] and method=="GET":
                if self.ice_config_provider is None:
                    raise RuntimeError("ice_provider_unavailable")
                response=self.ice_config_provider(who)
                if not isinstance(response,dict) or not isinstance(response.get("iceServers"),list) or not response["iceServers"]:
                    raise RuntimeError("ice_provider_unavailable")
            elif parts==["v1","voice","calls"] and method=="POST":
                # Caller-supplied eligible/approved flags must never authorize a call.
                # Require separate current server-owned incident-policy approval.
                approval=environ.get("gs.verified_incident_call_approval")
                approved=(isinstance(approval,dict)
                          and approval.get("home_id")==who.home_id
                          and approval.get("incident_id")==body.get("incident_id")
                          and approval.get("ownership_epoch")==who.ownership_epoch
                          and approval.get("auto_call_eligible") is True)
                response=self.service.originate(who,body.get("incident_id",""),eligible=approved)
            elif parts==["v1","voice","devices"] and method=="POST":
                self.service.register_device(who,body.get("device_id",""),body.get("token",""))
                response={"registered":True}
            elif len(parts)==4 and parts[:3]==["v1","voice","calls"] and method=="GET":
                response=self.service.status(who,parts[3])
            elif len(parts)==5 and parts[:3]==["v1","voice","calls"] and parts[4]=="candidates" and method=="GET":
                query=environ.get("QUERY_STRING","")
                if not re.fullmatch(r"after=\d{1,12}",query):
                    raise VoiceConflict("invalid_cursor")
                response={"candidates":self.service.candidates(who,parts[3],int(query.split("=")[1]))}
            elif len(parts)==5 and parts[:3]==["v1","voice","calls"] and method=="POST":
                response=self.service.action(who,parts[3],parts[4],body)
            else:
                raise KeyError("not_found")
            status="200 OK"
        except VoiceDenied as e:
            status,response="403 Forbidden",{"error":str(e)}
        except RuntimeError:
            status,response="503 Service Unavailable",{"error":"ice_provider_unavailable"}
        except VoiceConflict as e:
            status,response="409 Conflict",{"error":str(e)}
        except (ValueError,TypeError,json.JSONDecodeError):
            status,response="400 Bad Request",{"error":"invalid_request"}
        except KeyError:
            status,response="404 Not Found",{"error":"not_found"}
        data=json.dumps(response,separators=(",",":")).encode("utf-8")
        start_response(status,[("Content-Type","application/json"),("Cache-Control","no-store"),("Content-Length",str(len(data)))])
        return [data]
