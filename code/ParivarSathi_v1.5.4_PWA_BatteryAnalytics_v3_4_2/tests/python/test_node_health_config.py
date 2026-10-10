from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from ghar_sajag.node_health_policy import load,validate,NodeHealthPolicy,DeploymentPolicy
from ghar_sajag.foundation import FoundationService

class NodeHealthConfigTest(unittest.TestCase):
    def setUp(self):
        self.value=json.loads((ROOT/'config/node_health.json').read_text())
    def test_default_and_derived_examples(self):
        self.assertEqual(load().configured,NodeHealthPolicy(300))
        for seconds,timeout in [(60,190),(120,370),(300,910),(600,1810)]:
            with self.subTest(seconds=seconds):
                self.value['node_health']['heartbeat_interval_seconds']=seconds
                self.assertEqual(validate(self.value).configured.offline_seconds,timeout)
    def test_invalid_fields(self):
        for bad in [0,-1,True,1.5,'300',2**64,14,3601,None]:
            with self.subTest(value=bad):
                self.value['node_health']['heartbeat_interval_seconds']=bad
                with self.assertRaises(ValueError): validate(self.value)
    def test_missing_unknown_version_and_piggyback(self):
        for change in ['missing','unknown','version','disabled','independent_timeout']:
            with self.subTest(change=change):
                v=deepcopy(self.value)
                if change=='missing':del v['node_health']['heartbeat_interval_seconds']
                elif change=='unknown':v['other']=1
                elif change=='version':v['schema_version']=2
                elif change=='disabled':v['node_health']['piggyback_on_events']=False
                else:v['node_health']['offline_timeout_seconds']=910
                with self.assertRaises(ValueError):validate(v)
    def test_corrupt_missing_duplicate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'policy.json'
            with self.assertRaises(OSError):load(path)
            for value in ['{', '{"schema_version":1,"schema_version":1}', 'null']:
                path.write_text(value)
                with self.assertRaises(ValueError):load(path)
    def test_range_and_profiles(self):
        for interval in [15,3600]:
            self.value['node_health']['heartbeat_interval_seconds']=interval
            self.assertEqual(validate(self.value).configured.heartbeat_seconds,interval)
        self.value['deployment_profiles']={'c3-000000000001':'legacy_60','c3-000000000002':'legacy_120','c3-000000000003':'configured'}
        policy=validate(self.value)
        self.assertEqual(policy.for_device('c3-000000000001').offline_seconds,190)
        self.assertEqual(policy.for_device('c3-000000000002').offline_seconds,310)
        self.assertIsNone(policy.for_device('unlisted'))
    def test_invalid_profile(self):
        for profiles in [{'untrusted':'configured'},{'c3-000000000001':'schema2'},{f'c3-{i:012x}':'configured' for i in range(11)}]:
            self.value['deployment_profiles']=profiles
            with self.assertRaises(ValueError):validate(self.value)
    def test_json_changes_compiled_startup_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json';header=Path(tmp)/'gs/node_health_config.hpp'
            src=Path(tmp)/'policy.cpp';binary=Path(tmp)/'policy'
            src.write_text('#include "gs/node_health_config.hpp"\n#include <iostream>\nint main(){std::cout<<gs::deployment::policy.heartbeat_seconds<<","<<gs::deployment::policy.offline_seconds<<","<<gs::deployment::sha256;}')
            outputs=[]
            for interval in [300,600]:
                self.value['node_health']['heartbeat_interval_seconds']=interval;path.write_text(json.dumps(self.value))
                subprocess.run([sys.executable,str(ROOT/'scripts/generate_node_health_config.py'),'--config',str(path),'--output',str(header)],check=True,capture_output=True)
                subprocess.run(['g++','-B/usr/bin','-std=c++17','-I'+tmp,'-I'+str(ROOT/'shared/include'),str(src),'-o',str(binary)],check=True,capture_output=True)
                output=subprocess.check_output([str(binary)],text=True);outputs.append(output)
                self.assertTrue(output.startswith(f'{interval},{3*interval+10},'))
                self.assertEqual(load(path).configured.offline_seconds,int(output.split(',')[1]))
            self.assertNotEqual(outputs[0].split(',')[2],outputs[1].split(',')[2])
            path.write_text('{}')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/generate_node_health_config.py'),'--config',str(path),'--output',str(header)],capture_output=True)
            self.assertNotEqual(result.returncode,0)
    def test_backend_mixed_silent_nodes(self):
        clock=[1000]
        profiles={'c3-000000000001':'legacy_60','c3-000000000002':'legacy_120','c3-000000000003':'configured'}
        service=FoundationService(clock=lambda:clock[0],node_health_policy=DeploymentPolicy(NodeHealthPolicy(300),profiles))
        try:
            service.seed({},[])
            for identity in list(profiles)+['c3-000000000004']:
                service.register_device(service.owner_id,{'device_id':identity,'display_name':'Test Node','kind':'NODE','capability':'MOTION','room':'Bedroom / Room 1'})
                service.record_health(identity,True,'ACTIVE',heartbeat=True)
            for t,expected in [(1190,[1,1,1]),(1191,[0,1,1]),(1311,[0,0,1]),(1910,[0,0,1]),(1911,[0,0,0])]:
                clock[0]=t;service.expire_stale(t)
                records={d['device_id']:d for d in service.devices(service.owner_id)}
                self.assertEqual([records[d]['online'] for d in profiles],expected)
                self.assertEqual(records['c3-000000000004']['node_liveness'],'UNKNOWN')
            clock[0]=2000;service.record_health('c3-000000000003',True,'ACTIVE',heartbeat=True)
            self.assertEqual(service.device(service.owner_id,'c3-000000000003')['last_seen_at'],2000)
        finally:service.close()
    def test_packaging_rejects_mismatched_image_or_configuration(self):
        spec=importlib.util.spec_from_file_location('gs40_package',ROOT/'scripts/package_node_health_firmware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        canonical=json.dumps(self.value,sort_keys=True,separators=(',',':'))
        import hashlib
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c3=root/'c3';s3=root/'s3';config=root/'config.json';config.write_text(json.dumps(self.value))
            c3_bytes=b'C3-test-'+digest.encode()
            for build,name,content in [(c3,'gs_hw_m1_node',c3_bytes),(s3,'gs_r1_s3_hub',b'Hub-test-'+c3_bytes)]:
                (build/'gs40_generated/gs').mkdir(parents=True)
                (build/'gs40_generated/gs/node_health_config.hpp').write_text(digest)
                (build/(name+'.bin')).write_bytes(content)
                (build/'flasher_args.json').write_text(json.dumps({'flash_files':{'0x20000':name+'.bin'}}))
            module.package(config,c3,s3,root/'bundle')
            manifest=json.loads((root/'bundle/manifest.json').read_text())
            self.assertEqual(manifest['heartbeat_interval_seconds'],300)
            self.assertEqual(manifest['node_offline_timeout_seconds'],910)
            self.assertEqual(manifest['hardware_actions'],'NONE')
            (s3/'gs_r1_s3_hub.bin').write_bytes(b'Hub-test-'+digest.encode())
            with self.assertRaises(ValueError):module.package(config,c3,s3,root/'bad')
            (s3/'gs_r1_s3_hub.bin').write_bytes(b'Hub-test-'+c3_bytes)
            (s3/'gs40_generated/gs/node_health_config.hpp').write_text('wrong policy')
            with self.assertRaises(ValueError):module.package(config,c3,s3,root/'bad')

    def test_received_contact_not_render_time_renews_freshness(self):
        clock=[1000];identity='c3-146393c5d158'
        service=FoundationService(clock=lambda:clock[0])
        try:
            service.seed({},[])
            service.register_device(service.owner_id,{'device_id':identity,'display_name':'Node','kind':'NODE','capability':'MOTION','room':'Kitchen'})
            service.record_health(identity,True,'ACTIVE',heartbeat=True,received_contact_at=1000)
            writes=service.db.total_changes
            clock[0]=1100
            service.record_health(identity,True,'ACTIVE',heartbeat=True,received_contact_at=1000)
            self.assertEqual(service.db.total_changes,writes)
            self.assertEqual(service.device(service.owner_id,identity)['last_seen_at'],1000)
            clock[0]=1300
            service.record_health(identity,True,'ACTIVE',heartbeat=True,received_contact_at=1300)
            self.assertEqual(service.device(service.owner_id,identity)['last_seen_at'],1300)
            with self.assertRaises(ValueError):
                service.record_health(identity,True,'ACTIVE',heartbeat=True,received_contact_at=1301)
        finally:service.close()

    def test_build_and_startup_share_input(self):
        for main in ['firmware/node/target/esp32c3/idf/main/CMakeLists.txt','firmware/hub/target/esp32/idf/main/CMakeLists.txt']:
            self.assertIn('node_health_config.cmake',(ROOT/main).read_text())
        node=(ROOT/'firmware/node/target/esp32c3/node_runtime_adapter.cpp').read_text()
        self.assertIn('deployment::policy.heartbeat_seconds',node)
        self.assertIn('health_cadence.observe_authenticated_contact(now)',node[node.index('outstanding_health_sequence.reset();'):])
        self.assertIn('message->power = energy.telemetry()',node)
        self.assertIn('message->power.reset()',node)
        self.assertIn('SessionRecoveryPolicy::active_deadline',node)
        self.assertIn('set_node_offline_timeout',(ROOT/'firmware/hub/target/esp32/hub_runtime_adapter.cpp').read_text())


class NodeHealthPwaTest(unittest.TestCase):
    def test_quiet_sleeping_resident_is_not_offline_day_or_night(self):
        from tools.sim.local_lab import Lab
        for minute in [0,720]:
            with self.subTest(minute=minute):
                lab=Lab()
                try:
                    lab.action({'action':'time','minute':minute})
                    lab.action({'action':'advance','seconds':1800})
                    view=lab.pwa_view()
                    nodes=[d for d in view['devices'] if d['kind']=='NODE']
                    self.assertTrue(all(d['active'] for d in nodes))
                    self.assertTrue(all(d['node_offline_timeout_seconds']==910 for d in nodes))
                    self.assertEqual(view['coverage']['state'],'COVERED')
                finally:lab.close()
    def test_silent_rf_expiry_boundary_and_automatic_health_return(self):
        from tools.sim.local_lab import Lab
        lab=Lab()
        try:
            lab.command('silence 1');lab.sync()
            self.assertTrue(next(d for d in lab.pwa_view()['devices'] if d['id']=='kitchen')['active'])
            lab.action({'action':'advance','seconds':910})
            self.assertEqual(lab.pwa_view()['coverage']['state'],'COVERED')
            lab.action({'action':'advance','seconds':1})
            lost=lab.pwa_view()
            self.assertEqual(lost['coverage']['state'],'UNKNOWN')
            self.assertIn('kitchen',lost['device_health']['offline_devices'])
            lab.action({'action':'node','node':'kitchen','enabled':True})
            self.assertEqual(lab.pwa_view()['coverage']['state'],'COVERED')
            self.assertNotIn('kitchen',lab.pwa_view()['device_health']['offline_devices'])
        finally:lab.close()
    def test_internet_loss_does_not_expire_locally_healthy_nodes(self):
        from tools.sim.local_lab import Lab
        lab=Lab()
        try:
            lab.action({'action':'wan','enabled':False})
            lab.action({'action':'advance','seconds':1200})
            view=lab.pwa_view()
            self.assertTrue(all(d['active'] for d in view['devices'] if d['kind']=='NODE'))
            self.assertEqual(view['coverage']['state'],'COVERED')
            self.assertFalse(view['network']['wan_online'])
        finally:lab.close()
    def test_schema_matches_validator_and_unknown_ui_is_explicit(self):
        schema=json.loads((ROOT/'config/node_health.schema.json').read_text())
        interval=schema['properties']['node_health']['properties']['heartbeat_interval_seconds']
        self.assertEqual((interval['minimum'],interval['maximum']),(15,3600))
        self.assertNotIn('offline_timeout_seconds',schema['properties']['node_health']['properties'])
        source=(ROOT/'tools/sim/pwa/app.js').read_text()
        self.assertIn("d.node_liveness==='UNKNOWN'?'Availability unknown'",source)

if __name__=='__main__':unittest.main()
