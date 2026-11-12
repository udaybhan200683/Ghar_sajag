"""GS117-DEV-ADMIN: real production auth/config code, isolated TLS PostgreSQL.
No live account/board or policy is changed; physical qualification NOT_RUN.
"""
import json
import os
from io import BytesIO
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools/local'), str(ROOT/'parivar_saathi_android_app/server'), str(ROOT/'tests/support')]
from connected_lite import Store, bootstrap_admin, bootstrap_caregiver, build_app
import gs179_change_login as maintenance
from gs179_postgres_test_db import IsolatedPostgresSchema
from ghar_sajag.postgres_database import connect_postgres, initialize_postgres
from ghar_sajag.sqlite_events import SQLiteEventMap
from ghar_sajag.model import CloudEvent
from ghar_sajag.configuration_repository import PostgresConfigurationRepository, ConfigurationConflict
from ghar_sajag.cloud_client_identity import VerifiedHubContext, TimeReadiness


class DevelopmentHomeAdminPostgres(unittest.TestCase):
    """GS117-DEV-ADMIN-001..014: authenticated fixed-home assignment and recovery."""
    def setUp(self):
        dsn = os.environ.get('GS179_TEST_POSTGRES_DSN')
        if not dsn:
            raise RuntimeError('GS179_TEST_POSTGRES_DSN_required_no_silent_skip')
        self.schema = IsolatedPostgresSchema(dsn)
        self.addCleanup(self.schema.close)
        self.core = connect_postgres(self.schema.dsn)
        self.addCleanup(self.core.close)
        initialize_postgres(self.core)
        self.store = Store(self.schema.url); self.store.migrate()
        self.home = maintenance.DEV_HOME
        self.owner = bootstrap_admin(self.store,'seed-owner@example.org',secrets.token_urlsafe(24),self.home)
        self.password = secrets.token_urlsafe(24)
        self.account = bootstrap_caregiver(self.store,'same-current@example.org',self.password,self.home)
        self.core.execute('INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,1,1)',(self.home,'Isolated developer fixture','Etc/UTC'))
        for actor,role in [(self.owner,'OWNER'),(self.account,'FAMILY')]:
            self.core.execute('INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,1)',(actor,'Isolated test actor'))
            self.core.execute('INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES(?,?,?)',(self.home,actor,role))
        self.core.execute("INSERT INTO hub_ownership_registry(hub_device_id,identity_key_fingerprint,state,home_id,installation_epoch,created_at,updated_at) VALUES(?,?,'ACTIVE',?,1,1,1)",(maintenance.DEV_HUB,'a'*64,self.home));self.core.commit()
        events = SQLiteEventMap(self.core)
        events[(self.home,'preserved-historical-event')] = CloudEvent(self.home,'preserved-historical-event','MOTION','Bedroom',1,2,3,payload={'fixture':'HOST_ONLY_HISTORY'})
        self.core.commit()
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.path=self.root/'.local/state/ghar-sajag/gs179-laptop/caregiver-login.json';self.path.parent.mkdir(parents=True);self.path.parent.chmod(0o700)
        self.credentials={'profile':'GS179_TEST_ONLY','home_id':self.home,'account_id':self.account,'email':'same-current@example.org','password':self.password}
        self.write_credentials()
        self.env=patch.dict(os.environ,{'DATABASE_URL':self.schema.url,'PUBLIC_ORIGIN':'https://care.gharsajag.in','GS179_TEST_ONLY_MONITORING':'1','GS179_LOCAL_LAN_TEST_ONLY':'0','GS179_TEST_ONLY_ALLOWED_ORIGINS':''})
        self.env.start();self.addCleanup(self.env.stop)
        self.api=build_app();self.addCleanup(self.api.product_view.durable_api.close)
        status,_,headers=self.request('POST','/lite/v1/auth/login',{'email':self.credentials['email'],'password':self.password})
        self.assertEqual(status,'200 OK');self.cookie=headers['Set-Cookie'].split(';',1)[0]
        self.before=self.snapshot()

    def write_credentials(self):
        self.path.write_text(json.dumps(self.credentials));self.path.chmod(0o600)

    def request(self,method,path,body=None,cookie=None):
        raw=json.dumps(body or {}).encode();headers=[]
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':BytesIO(raw),'HTTP_ORIGIN':'https://care.gharsajag.in','HTTP_COOKIE':getattr(self,'cookie','') if cookie is None else cookie,'REMOTE_ADDR':'192.0.2.1'}
        result=json.loads(b''.join(self.api(env,lambda status,h:headers.extend([status,h]))))
        return headers[0],result,dict(headers[1])

    def snapshot(self):
        with self.store.connect() as db:
            accounts=[tuple(r.values()) for r in db.execute('SELECT account_id,email,password_hash,active FROM lite_accounts ORDER BY account_id')]
            sessions=[tuple(r.values()) for r in db.execute('SELECT session_id,account_id,token_hash,expires_at,revoked_at FROM lite_sessions ORDER BY session_id')]
            events=[tuple(r.values()) for r in db.execute('SELECT event_id,home_id,payload_json FROM events ORDER BY event_id')]
        return dict(accounts=accounts,sessions=sessions,events=events,credentials=self.path.read_bytes())

    def grant(self,revoke=False):
        # Inject only registered-lab evidence for isolated test data. Execute the
        # real private-file, password, DB scope, transaction, audit and API guards.
        with patch('gs179_verified_endpoint.engineering_functional_admission',return_value={'profile':'GS117_ENGINEERING_FUNCTIONAL'}),patch.object(Path,'home',return_value=self.root):
            return maintenance.assign_existing_development_admin(self.store,self.path,revoke=revoke)

    def roles(self):
        with self.store.connect() as db:
            return tuple(db.execute('SELECT m.role AS lite_role,c.role AS durable_role FROM lite_memberships m JOIN household_caregivers c ON c.home_id=m.home_id AND c.caregiver_id=m.account_id WHERE m.home_id=%s AND m.account_id=%s',(self.home,self.account)).fetchone().values())

    def test_001_same_session_reports_settings_save_and_exact_hub_apply(self):
        url=f'/lite/v1/homes/{self.home}/routine-config'
        self.assertEqual(self.request('GET',url)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{self.home}/reports')[0],'200 OK')
        result=self.grant();self.assertEqual(result['status'],'GRANTED');self.assertEqual(self.roles(),('ADMIN','OWNER'))
        self.assertEqual(self.snapshot(),self.before)
        status,data,_=self.request('GET',url);self.assertEqual(status,'200 OK');self.assertEqual(data['desired_version'],0)
        # Named synthetic test policy ONLY in this isolated schema, never live defaults.
        policy={'morning':{'enabled':True,'start_minute':420,'end_minute':600,'grace_minutes':30},'activity_rules':{'quiet_hours_enabled':True,'quiet_start_minute':60,'quiet_end_minute':300,'door_open_timeout_seconds':300,'daytime_inactivity_enabled':True,'daytime_start_minute':480,'daytime_end_minute':1260,'daytime_inactivity_seconds':10800,'morning_steps':[{'location':'bedroom','enabled':True,'required':True}]}}
        status,data,_=self.request('POST',url,{'expected_version':0,'config':policy});self.assertEqual(status,'202 Accepted');self.assertEqual(data['desired_version'],1);self.assertIsNone(data['applied_version'])
        hub=VerifiedHubContext(maintenance.DEV_HUB,self.home,1,'b'*64,'a'*64,True,TimeReadiness.TRUSTED)
        repository=PostgresConfigurationRepository(self.core,authorize_hub_configuration=lambda c,h,at:c==hub and h==self.home)
        with self.assertRaises(ConfigurationConflict):repository.record_applied(context=hub,home_id=self.home,version=2,at=100)
        repository.record_applied(context=hub,home_id=self.home,version=1,at=101)
        status,data,_=self.request('GET',url);self.assertEqual(status,'200 OK');self.assertEqual(data['applied_version'],1)
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{self.home}/reports')[0],'200 OK')
        self.assertEqual(self.snapshot(),self.before)

    def test_002_idempotent_and_auditable_without_duplicate_grant(self):
        self.grant();self.assertEqual(self.grant()['status'],'ALREADY_AUTHORIZED')
        with self.store.connect() as db:
            rows=db.execute("SELECT details_json FROM audit_log WHERE action='dev.home_admin.granted'").fetchall()
        self.assertEqual(len(rows),1);d=rows[0]['details_json'];d=json.loads(d) if isinstance(d,str) else d
        self.assertEqual(d['previous_roles'],['CAREGIVER','FAMILY']);self.assertEqual(d['owner_ref'],maintenance.DEV_OWNER_REF)
        self.assertNotIn(self.password,json.dumps(d))

    def test_003_revocation_current_cookie_denied_settings_reports_preserved(self):
        self.grant();self.assertEqual(self.grant(True)['status'],'REVOKED');self.assertEqual(self.roles(),('CAREGIVER','FAMILY'))
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{self.home}/routine-config')[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{self.home}/reports')[0],'200 OK');self.assertEqual(self.snapshot(),self.before)
        with self.assertRaisesRegex(maintenance.LoginChangeError,'active_audited'):self.grant(True)

    def test_004_wrong_password_or_claimed_account_id_rejected(self):
        for change in [{'password':'wrong-password-not-authority'},{'account_id':self.owner}]:
            original=dict(self.credentials);self.credentials.update(change);self.write_credentials()
            with self.assertRaisesRegex(maintenance.LoginChangeError,'current_caregiver_login_invalid'):self.grant()
            self.credentials=original;self.write_credentials()
        self.assertEqual(self.roles(),('CAREGIVER','FAMILY'))

    def test_005_wrong_home_and_production_flag_rejected(self):
        self.credentials['home_id']='gs177-test-other';self.write_credentials()
        with self.assertRaisesRegex(maintenance.LoginChangeError,'registered_development_home_required'):self.grant()
        self.credentials['home_id']=self.home;self.write_credentials()
        with self.store.connect() as db:db.execute('UPDATE lite_homes SET test_only=FALSE WHERE home_id=%s',(self.home,))
        with self.assertRaisesRegex(maintenance.LoginChangeError,'current_test_home'):self.grant()

    def test_006_epoch_or_revoked_hub_rejected(self):
        for sql in ["UPDATE hub_ownership_registry SET installation_epoch=2", "UPDATE hub_ownership_registry SET state='REVOKED'"]:
            with self.store.connect() as db:db.execute(sql)
            with self.assertRaisesRegex(maintenance.LoginChangeError,'current_registered_home_ownership_required'):self.grant()
            with self.store.connect() as db:db.execute("UPDATE hub_ownership_registry SET state='ACTIVE',installation_epoch=1")
        self.assertEqual(self.roles(),('CAREGIVER','FAMILY'))

    def test_007_inactive_membership_or_withdrawn_consent_rejected(self):
        for sql,restore in [("UPDATE household_caregivers SET active=0 WHERE caregiver_id=%s","UPDATE household_caregivers SET active=1 WHERE caregiver_id=%s"),("UPDATE households SET consent_state='WITHDRAWN' WHERE home_id=%s","UPDATE households SET consent_state='ACTIVE' WHERE home_id=%s")]:
            arg=self.account if 'caregiver_id' in sql else self.home
            with self.store.connect() as db:db.execute(sql,(arg,))
            with self.assertRaisesRegex(maintenance.LoginChangeError,'current_registered_home_ownership_required'):self.grant()
            with self.store.connect() as db:db.execute(restore,(arg,))

    def test_008_audit_failure_rolls_back_both_memberships(self):
        original=self.store.sql
        def failing(db,query,args=()):
            if 'INSERT INTO audit_log' in query:raise RuntimeError('injected audit failure')
            return original(db,query,args)
        with patch.object(self.store,'sql',side_effect=failing),self.assertRaisesRegex(RuntimeError,'audit failure'):self.grant()
        self.assertEqual(self.roles(),('CAREGIVER','FAMILY'));self.assertEqual(self.snapshot(),self.before)

    def test_009_untrusted_credential_file_or_pending_recovery_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(maintenance.LoginChangeError,'permissions_invalid'):self.grant()
        self.path.chmod(0o600);pending=self.path.with_name(self.path.name+'.pending');pending.write_text('{}')
        with self.assertRaisesRegex(maintenance.LoginChangeError,'pending_login_change'):self.grant()

    def test_010_changed_assignment_not_silently_revoked(self):
        self.grant()
        with self.store.connect() as db:db.execute("UPDATE household_caregivers SET role='PRIMARY' WHERE caregiver_id=%s",(self.account,))
        with self.assertRaisesRegex(maintenance.LoginChangeError,'changed_or_audit_invalid'):self.grant(True)

    def test_011_real_release_guard_cannot_grant(self):
        for mode in ['RELEASE_CANDIDATE','PRODUCTION']:
            with patch.dict(os.environ,{'GHAR_SAJAG_QUALIFICATION_MODE':mode}),self.assertRaisesRegex(ValueError,'release_environment'):
                maintenance.assign_existing_development_admin(self.store,self.path)
        self.assertEqual(self.roles(),('CAREGIVER','FAMILY'))

    def test_012_operator_mismatch_or_unregistered_path_rejected(self):
        with patch('gs179_verified_endpoint.ENGINEERING_OWNER_UID',os.getuid()+1),self.assertRaisesRegex(ValueError,'owner_or_laptop'):
            maintenance.assign_existing_development_admin(self.store,self.path)
        with patch('gs179_verified_endpoint.engineering_functional_admission',return_value={}),self.assertRaisesRegex(maintenance.LoginChangeError,'registered_private_account_path_required'):
            maintenance.assign_existing_development_admin(self.store,self.path)

    def test_013_cross_home_and_forged_session_denied_after_grant(self):
        self.grant()
        self.assertEqual(self.request('GET','/lite/v1/homes/gs177-test-other/routine-config')[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{self.home}/routine-config',cookie='not-a-valid-cookie')[0],'403 Forbidden')

    def test_014_longer_or_remote_database_not_admitted(self):
        with patch('gs179_verified_endpoint.engineering_functional_admission',return_value={}),patch.object(Path,'home',return_value=self.root):
            for url in ['postgresql://user@remote.example/db?sslmode=verify-full','postgresql://user@localhost/db?sslmode=require']:
                with self.assertRaisesRegex(maintenance.LoginChangeError,'local_verified_tls_database'):
                    maintenance.assign_existing_development_admin(Store(url),self.path)


if __name__=='__main__':unittest.main(verbosity=2)
