import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from io import BytesIO
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connected_lite import HOME_ID, LiteApi, Store, bootstrap_admin, bootstrap_caregiver, rotate_password, run_scenario


class ConnectedLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['GS177_LOCAL_TEST'] = '1'
        os.environ['PUBLIC_ORIGIN'] = 'https://care.gharsajag.in'
        cls.store = Store('sqlite:///' + cls.temp.name + '/lite.db')
        os.environ['DATABASE_URL'] = 'sqlite:///' + cls.temp.name + '/lite.db'
        cls.api = LiteApi(cls.store, runner=lambda scenario: {
            'status': 'PASS', 'scenario': {'id': scenario}, 'state': {'timeline': [{'kind': 'MOTION', 'event_key': 'synthetic-only'}]},
            'checks': [{'pass': True, 'detail': 'observed'}], 'hardware_evidence': 'NOT_RUN',
            'provenance': 'HOST_SIMULATION_TEST_ONLY',
        }, clock=lambda: 1000)
        bootstrap_admin(cls.store, 'admin@example.org', 'correct-horse-battery-test-177', HOME_ID)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def request(self, method, path, body=None, cookie='', origin='https://care.gharsajag.in'):
        raw = json.dumps(body or {}).encode()
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'CONTENT_LENGTH': str(len(raw)),
               'wsgi.input': BytesIO(raw), 'HTTP_ORIGIN': origin, 'HTTP_COOKIE': cookie,
               'REMOTE_ADDR': '192.0.2.2'}
        headers=[]
        response=json.loads(b''.join(self.api(env, lambda status, h: headers.extend([status,h]))))
        return headers[0], response, dict(headers[1])

    def login(self):
        status, body, headers = self.request('POST','/lite/v1/auth/login',
            {'email':'admin@example.org','password':'correct-horse-battery-test-177'})
        self.assertEqual(status, '200 OK')
        return headers['Set-Cookie'].split(';',1)[0]

    def test_valid_login_session_restore_and_logout(self):
        cookie=self.login()
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[1]['role'],'ADMIN')
        overview=self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[1]
        self.assertIn('TEST_ONLY', str(overview))
        self.assertEqual(overview['physical_status'],'UNAVAILABLE')
        self.assertEqual(overview['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        self.assertEqual(overview['physical_data_contract'],'GS-148_CLOUDSYNC')
        self.assertEqual(overview['source_freshness'],'UNKNOWN')
        self.assertEqual(overview['backend_data_retrieved_at'],1000)
        self.assertNotIn('last_successful_sync',overview)
        devices=self.request('GET',f'/lite/v1/homes/{HOME_ID}/devices',cookie=cookie)[1]
        self.assertEqual(devices['physical_status'],'UNAVAILABLE')
        self.assertEqual(devices['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        routines=self.request('GET',f'/lite/v1/homes/{HOME_ID}/routines',cookie=cookie)[1]
        self.assertEqual(routines['learning_status'],'UNSUPPORTED_MULTI_DAY')
        self.assertEqual(self.request('POST','/lite/v1/auth/logout',cookie=cookie)[0],'200 OK')
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')

    def test_invalid_credentials_and_csrf(self):
        self.assertEqual(self.request('POST','/lite/v1/auth/login',{'email':'admin@example.org','password':'wrong'})[0],'401 Unauthorized')
        self.assertEqual(self.request('POST','/lite/v1/auth/login',{'email':'admin@example.org','password':'wrong'},origin='https://evil.example.org')[0],'403 Forbidden')
        cloud_event={'event_key':{'home_id':'real-home','device_id':'node-1','boot_id':'boot-1','sequence':1}}
        self.assertEqual(self.request('POST','/v1/homes/real-home/events',cloud_event)[0],'404 Not Found')

    def test_authenticated_api_rate_limit_is_bounded_and_recovers_next_window(self):
        home='gs177-test-rate-limit'
        bootstrap_admin(self.store,'rate-limit@example.org','rate-limit-password-177',home)
        status,_,headers=self.request('POST','/lite/v1/auth/login',
            {'email':'rate-limit@example.org','password':'rate-limit-password-177'})
        self.assertEqual(status,'200 OK')
        cookie=headers['Set-Cookie'].split(';',1)[0]
        for _ in range(239):
            status,_,_=self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)
            self.assertEqual(status,'200 OK')
        status,body,headers=self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)
        self.assertEqual(status,'429 Too Many Requests')
        self.assertEqual(body['error'],'rate_limited')
        self.assertGreaterEqual(int(headers['Retry-After']),1)
        self.api.clock=lambda:1060
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)[0],'200 OK')
        with self.store.connect() as db:
            self.store.sql(db,'DELETE FROM lite_api_limits WHERE account_id=(SELECT account_id FROM lite_accounts WHERE email=?)',
                           ('rate-limit@example.org',))
        self.api.clock=lambda:1000

    def test_simulation_hourly_rate_limit(self):
        cookie=self.login()
        account=self.request('GET','/lite/v1/me',cookie=cookie)[1]['account_id']
        inserted=[]
        try:
            with self.store.connect() as db:
                for _ in range(120):
                    run_id=str(uuid4());inserted.append(run_id)
                    self.store.sql(db,'INSERT INTO lite_runs(run_id,home_id,account_id,scenario_id,status,simulation_generation,created_at,result_json) VALUES(?,?,?,?,?,?,?,?)',
                                   (run_id,HOME_ID,account,'motion-room1-visible','PASS',1,1000,'{}'))
            status,body,headers=self.request('POST',f'/lite/v1/homes/{HOME_ID}/sim/runs',{'scenario_id':'motion-room1-visible'},cookie)
            self.assertEqual(status,'429 Too Many Requests')
            self.assertEqual(body['error'],'simulation_hourly_limit')
            self.assertEqual(headers['Retry-After'],'3600')
        finally:
            with self.store.connect() as db:
                for run_id in inserted:
                    self.store.sql(db,'DELETE FROM lite_runs WHERE run_id=?',(run_id,))

    def test_home_role_epoch_and_frontend_tampering_denied(self):
        cookie=self.login()
        engineering=self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)
        self.assertEqual(engineering[0],'200 OK')
        self.assertEqual(engineering[1]['gs124_health']['status'],'UNSUPPORTED')
        self.assertEqual(engineering[1]['physical_status'],'UNAVAILABLE')
        self.assertEqual(engineering[1]['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        self.assertEqual(engineering[1]['physical_data_contract'],'GS-148_CLOUDSYNC')
        self.assertEqual(self.request('GET','/lite/v1/homes/other-home/overview',cookie=cookie)[0],'403 Forbidden')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET role='CAREGIVER' WHERE home_id=?",(HOME_ID,))
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/catalog',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'200 OK')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET role='ADMIN',ownership_epoch=2 WHERE home_id=?",(HOME_ID,))
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'403 Forbidden')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET ownership_epoch=1 WHERE home_id=?",(HOME_ID,))

    def test_run_persists_after_api_restart_and_input_is_bounded(self):
        cookie=self.login()
        url=f'/lite/v1/homes/{HOME_ID}/sim/runs'
        self.assertEqual(self.request('POST',url,{'scenario_id':'unknown'},cookie)[0],'400 Bad Request')
        status, created, _=self.request('POST',url,{'scenario_id':'motion-room1-visible'},cookie)
        self.assertEqual(status,'201 Created')
        restarted=LiteApi(self.store,runner=self.api.runner,clock=lambda:1000)
        self.api=restarted
        status, loaded, _=self.request('GET',url+'/'+created['run_id'],cookie=cookie)
        self.assertEqual(status,'200 OK')
        self.assertEqual(loaded['result']['provenance'],'HOST_SIMULATION_TEST_ONLY')
        self.assertEqual(loaded['result']['hardware_evidence'],'NOT_RUN')
        self.assertEqual(self.request('POST',url,{'scenario_id':'motion-room1-visible','seed':7},cookie)[0],'400 Bad Request')
        self.assertEqual(self.request('POST',url,{'scenario_id':'x'*17000},cookie)[0],'400 Bad Request')

    def test_saved_run_exposes_test_only_event_and_routine_trace_projections(self):
        cookie=self.login()
        root=f'/lite/v1/homes/{HOME_ID}'
        status,created,_=self.request('POST',root+'/sim/runs',{'scenario_id':'motion-room1-visible'},cookie)
        self.assertEqual(status,'201 Created')
        self.assertEqual(created['trace_id'],f"sim:{created['run_id']}")
        trace=created['result']['trace']
        self.assertFalse(trace['original_event_key_available'])
        self.assertEqual(trace['event_count'],1)
        overview=self.request('GET',root+'/overview',cookie=cookie)[1]
        event=next(item for item in overview['recent_events'] if item['run_id']==created['run_id'])
        self.assertIsNone(event['event_key'])
        self.assertFalse(event['original_event_key_available'])
        self.assertEqual(event['source'],'HOST_SIMULATION_TEST_ONLY')
        self.assertEqual(event['trace_id'],f"sim:{created['run_id']}:1")

        # This catalogue scenario is category=routine even though its ID does not contain
        # "routine", "morning", "inactivity" or "night"; the catalogue is authoritative.
        status,catalogue_routine,_=self.request('POST',root+'/sim/runs',
            {'scenario_id':'door-left-open-two-hour-config-default'},cookie)
        self.assertEqual(status,'201 Created')
        routine_view=self.request('GET',root+'/routines',cookie=cookie)[1]
        self.assertIn(catalogue_routine['run_id'],[item['run_id'] for item in routine_view['runs']])

        saved_runner=self.api.runner
        try:
            self.api.runner=lambda scenario: {
                'status':'PASS','scenario':{'id':scenario,'title':'Missing morning activity','category':'morning'},
                'state':{'timeline':[],'simulation':{'reason':'no_qualifying_evidence'},
                         'incidents':[{'incident_id':'incident-1','kind':'MISSING_MORNING_ACTIVITY',
                                       'home_id':'simulation-home','is_test':False,'state':'OPEN'}]},
                'step_results':[{'index':1,'passed':True,'detail':'scenario rule evaluated'}],
                'checks':[{'pass':True,'detail':'expected missing-activity decision'}],
                'provenance':'HOST_SIMULATION_TEST_ONLY','hardware_evidence':'NOT_RUN'}
            status,morning,_=self.request('POST',root+'/sim/runs',{'scenario_id':'morning-missing-covered'},cookie)
            self.assertEqual(status,'201 Created')
            routines=self.request('GET',root+'/routines',cookie=cookie)[1]
            decision=next(item for item in routines['decisions'] if item['run_id']==morning['run_id'])
            self.assertEqual(decision['decision_reason'],'no_qualifying_evidence')
            self.assertEqual(decision['learning_status'],'UNSUPPORTED_MULTI_DAY')
            self.assertEqual(decision['incident_count'],1)
            self.assertEqual(decision['provenance'],'HOST_SIMULATION_TEST_ONLY')
            incidents=self.request('GET',root+'/incidents',cookie=cookie)[1]['incidents']
            projected=next(item for item in incidents if item['run_id']==morning['run_id'])
            self.assertNotIn('home_id',projected)
            self.assertNotIn('is_test',projected)
            self.assertEqual(projected['provenance'],'HOST_SIMULATION_TEST_ONLY')
        finally:
            self.api.runner=saved_runner

    def test_initial_schema_migration_is_recorded_once_across_restart(self):
        with self.store.connect() as db:
            versions=[row['version'] for row in self.store.sql(db,'SELECT version FROM lite_schema_migrations ORDER BY version').fetchall()]
        self.assertEqual(versions,[1])
        LiteApi(self.store,runner=self.api.runner,clock=lambda:1000)
        with self.store.connect() as db:
            versions=[row['version'] for row in self.store.sql(db,'SELECT version FROM lite_schema_migrations ORDER BY version').fetchall()]
        self.assertEqual(versions,[1])

    def test_wsgi_entrypoint_health_and_database_readiness(self):
        import wsgi
        previous = self.api
        try:
            self.api = wsgi.application
            self.assertEqual(self.request('GET', '/healthz')[0], '200 OK')
            ready = self.request('GET', '/readyz')
            self.assertEqual(ready[0], '200 OK')
            self.assertEqual(ready[1], {'status': 'ready', 'database': 'reachable'})
        finally:
            self.api = previous

    def test_reset_preserves_history_and_increments_fixture_generation(self):
        cookie=self.login()
        root=f'/lite/v1/homes/{HOME_ID}/sim'
        first=self.request('POST',root+'/runs',{'scenario_id':'motion-room1-visible'},cookie)[1]
        reset=self.request('POST',root+'/reset',{},cookie)
        self.assertEqual(reset[0],'200 OK')
        self.assertGreater(reset[1]['simulation_generation'],first['simulation_generation'])
        self.assertEqual(self.request('GET',root+'/runs/'+first['run_id'],cookie=cookie)[0],'200 OK')

    def test_real_existing_lab_executes_through_authenticated_api(self):
        cookie=self.login()
        saved=self.api
        try:
            self.api=LiteApi(self.store,runner=run_scenario,clock=lambda:1000)
            status,created,_=self.request('POST',f'/lite/v1/homes/{HOME_ID}/sim/runs',
                {'scenario_id':'motion-room1-visible'},cookie)
            self.assertEqual(status,'201 Created')
            self.assertEqual(created['status'],'PASS')
            self.assertGreater(len(created['result']['state']['timeline']),0)
            self.assertEqual(created['result']['hardware_evidence'],'NOT_RUN')
            loaded=self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/runs/{created["run_id"]}',cookie=cookie)[1]
            self.assertEqual(loaded['result']['checks'],created['result']['checks'])
        finally:
            self.api=saved

    def test_session_expiry_and_other_admin_home_isolation(self):
        cookie=self.login()
        second='gs177-test-other-admin'
        bootstrap_admin(self.store,'another-admin@example.org','another-correct-password-177',second)
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{second}/engineering',cookie=cookie)[0],'403 Forbidden')
        saved=self.api
        try:
            self.api=LiteApi(self.store,runner=saved.runner,clock=lambda:50000)
            self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')
        finally:
            self.api=saved

    def test_caregiver_login_denied_engineering_and_rotation_revokes(self):
        bootstrap_caregiver(self.store,'caregiver@example.org','caregiver-secret-password-177',HOME_ID)
        status,profile,headers=self.request('POST','/lite/v1/auth/login',
            {'email':'caregiver@example.org','password':'caregiver-secret-password-177'})
        self.assertEqual(status,'200 OK')
        self.assertEqual(profile['role'],'CAREGIVER')
        cookie=headers['Set-Cookie'].split(';',1)[0]
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'200 OK')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/runs',cookie=cookie)[0],'403 Forbidden')
        rotate_password(self.store,'caregiver@example.org','new-caregiver-password-177')
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('POST','/lite/v1/auth/login',
            {'email':'caregiver@example.org','password':'new-caregiver-password-177'})[0],'200 OK')


if __name__ == '__main__':
    unittest.main()
