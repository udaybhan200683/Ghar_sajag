"""GS-116 framework integrity tests: real controlled subprocesses, no boards."""
import copy, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from validation import component_gate as gate
ROOT=gate.ROOT

class ComponentGateTest(unittest.TestCase):
    def stage(self,**kwargs):
        return {"id":"sample","success":r"^PASS tests=(\d+)$","allowed_skips":[],**kwargs}
    def result(self,output="PASS tests=1\n",rc=0):
        return {"exit_code":rc,"output":output,"seconds":0}
    def test_external_crypto_and_idf_guard_invalidate_receipts(self):
        from scripts.build_portable_psa_reset import dependency_fingerprint
        with tempfile.TemporaryDirectory() as t:
            sdk=Path(t);crypto=sdk/'components/mbedtls/mbedtls/tf-psa-crypto'
            crypto.mkdir(parents=True);(crypto/'CMakeLists.txt').write_text('cmake')
            guard=sdk/'components/mbedtls/port/aes/esp_aes_gcm.c'
            guard.parent.mkdir(parents=True);guard.write_text('guard')
            env={'IDF_PATH':t};before=dependency_fingerprint(env)
            guard.write_text('changed guard');self.assertNotEqual(before,dependency_fingerprint(env))
            before=dependency_fingerprint(env);(crypto/'source.c').write_text('crypto')
            self.assertNotEqual(before,dependency_fingerprint(env))
            guard.unlink();self.assertTrue(dependency_fingerprint(env).startswith('MISSING:'))
    def test_partial_board_case_selection_cannot_satisfy_complete_gate(self):
        stage=next(s for s in gate.load_registry()['stages'] if s['id']=='board-stack-e2e')
        out='BOARD-TC-130-001 PASS\nBOARD STACK E2E PASS cases=1 checks=20 failed=0 physical=NOT_RUN\n'
        self.assertEqual(gate.adjudicate(stage,self.result(out)),'FAIL')
    def test_profile_initialization_works_without_pythonpath(self):
        script="import importlib.util; s=importlib.util.spec_from_file_location('gate',"+repr(str(ROOT/'validation/component_gate.py'))+"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m.build_profile({})['portable_crypto_sources']"
        result=subprocess.run([sys.executable,'-I','-c',script],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_option_a_fault_matrix_and_old_reader_limit_are_mandatory(self):
        stages={s['id']:s for s in gate.load_registry()['stages']}
        storage=stages['storage-correctness']
        lines=[p.removeprefix('^').removesuffix('$') for p in storage['required_success']]
        complete='\n'.join(lines+['PASS: GS148 bounded admission and recovery correctness'])+'\n'
        self.assertEqual(gate.adjudicate(storage,self.result(complete)),'PASS')
        for line in lines:
            if 'option_a_' in line or 'pending_privacy_context' in line:
                self.assertEqual(gate.adjudicate(storage,self.result(complete.replace(line+'\n',''))),'FAIL')
        reader=stages['first-event-reader-compatibility']
        complete=('GS148-ARCH-049 PASS actual_readers=2 byte_states=11 reboot_per_reader=2\n'
                  'OLD_READER_COMMERCIAL_ROLLBACK_AVAILABILITY=FAIL_KNOWN_FIRST_EVENT_LIMITATION\n'
                  'GS148_READER_REPORT=build/gs148_reader_compatibility/reader-fixture/report.json\n')
        self.assertEqual(gate.adjudicate(reader,self.result(complete)),'PASS')
        self.assertEqual(gate.adjudicate(reader,self.result(complete.split('OLD_READER_')[0])),'FAIL')
        self.assertEqual(gate.adjudicate(reader,self.result(complete,rc=2)),'FAIL')

    def test_failure_propagates_even_with_pass_text(self):
        self.assertEqual(gate.adjudicate(self.stage(),self.result(rc=3)),"FAIL")
    def test_zero_tests_and_missing_records_fail(self):
        for text in ("PASS tests=0\n","Ran 0 tests\nPASS tests=1\n",""):
            self.assertEqual(gate.adjudicate(self.stage(),self.result(text)),"FAIL")
    def test_positive_execution_count_passes(self):
        self.assertEqual(gate.adjudicate(self.stage(),self.result()),"PASS")
    def test_sanitizer_diagnostic_fails_even_with_zero_exit(self):
        s=self.stage(failure_patterns=[r'runtime error:',r'ERROR: AddressSanitizer'])
        for text in ('runtime error: overflow','ERROR: AddressSanitizer: use-after-free'):
            self.assertEqual(gate.adjudicate(s,self.result('PASS tests=1\n'+text+'\n')),'FAIL')
    def test_browser_and_tap_lowercase_skips_cannot_pass(self):
        for text in ('  1 skipped','# skipped 1','# todo 1','  2 did not run','  1 interrupted'):
            self.assertEqual(gate.adjudicate(self.stage(),self.result('PASS tests=1\n'+text+'\n')),'FAIL')
    def test_cancellation_reaps_owned_child_group(self):
        from unittest.mock import Mock
        proc=Mock(pid=12345);proc.communicate.side_effect=[KeyboardInterrupt(),('',None)]
        with patch.object(gate.subprocess,'Popen',return_value=proc),patch.object(gate.os,'killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):gate.run_process(['controlled'],ROOT,{},1)
            kill.assert_called_once_with(12345,gate.signal.SIGKILL)
            self.assertEqual(proc.communicate.call_count,2)
    def test_compound_stage_requires_every_execution_record(self):
        s=self.stage(required_success=[r"Ran [1-9]\d* tests?"])
        self.assertEqual(gate.adjudicate(s,self.result()),"FAIL")
        self.assertEqual(gate.adjudicate(s,self.result("PASS tests=1\nRan 11 tests\n")),"PASS")
    def test_partition_csv_invalidates_source_receipts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'partitions.csv';p.write_text('old')
            with patch.object(gate.subprocess,'check_output',return_value='partitions.csv\n'):
                before=gate.source_fingerprint(root);p.write_text('new')
                self.assertNotEqual(before,gate.source_fingerprint(root))
    def test_required_dependency_absence(self):
        r=gate.run_process(["/nonexistent/gs116-required-tool"],ROOT,os.environ,1)
        self.assertEqual(r["exit_code"],127)
        self.assertIn("DEPENDENCY_ERROR",r["output"])
    def test_timeout_fails_and_retains_partial_output(self):
        r=gate.run_process([sys.executable,"-c","import time; print('started',flush=True); time.sleep(10)"],ROOT,os.environ,2)
        self.assertEqual(r["exit_code"],124)
        self.assertIn("started",r["output"]);self.assertIn("TIMEOUT",r["output"])
    def test_timeout_terminates_child_process_group(self):
        with tempfile.TemporaryDirectory() as t:
            marker=Path(t)/"escaped"
            child="import time;from pathlib import Path;time.sleep(4);Path("+repr(str(marker))+").touch()"
            parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);print('child launched',flush=True);time.sleep(10)"
            r=gate.run_process([sys.executable,"-c",parent],ROOT,os.environ,2)
            self.assertEqual(r["exit_code"],124)
            self.assertIn('child launched',r['output'])
            time.sleep(4.1);self.assertFalse(marker.exists())
    def test_mandatory_skipped_or_manual_cannot_pass(self):
        for token in ("SKIPPED","MANUAL_REQUIRED","ALREADY_PASSED"):
            self.assertEqual(gate.adjudicate(self.stage(),self.result("PASS tests=1\n"+token+"\n")),"FAIL")
    def test_unexpected_python_skip_fails(self):
        out="case ... skipped 'missing thing'\nRan 1 test\nOK (skipped=1)\nPASS tests=1\n"
        self.assertEqual(gate.adjudicate(self.stage(),self.result(out)),"FAIL")
    def test_specific_approved_historical_skip_is_visible(self):
        out="case ... skipped '"+gate.CLASSIC_SKIP+"'\nRan 2 tests\nOK (skipped=1)\nPASS tests=1\n"
        self.assertEqual(gate.adjudicate(self.stage(allowed_skips=[gate.CLASSIC_SKIP]),self.result(out)),"PASS")
    def test_missing_skip_detail_fails(self):
        self.assertEqual(gate.adjudicate(self.stage(),self.result("PASS tests=1\nOK (skipped=1)\n")),"FAIL")
    def test_release_dominates_fast_and_all_components(self):
        data=gate.load_registry()
        fast={s["id"] for s in gate.select(data,"fast")}
        release={s["id"] for s in gate.select(data,"release")}
        self.assertLessEqual(fast,release)
        for name in gate.COMPONENTS:
            self.assertLessEqual({s["id"] for s in gate.select(data,name)},fast)
        self.assertLessEqual({"sanitizers","trace","target-builds","browser","bounded-performance"},release)
    def test_node_has_previous_safety_and_new_health_without_browser(self):
        ids={s["id"] for s in gate.select(gate.load_registry(),"node")}
        self.assertLessEqual({"cpp","battery-c8","gs150","gs40","node-persistence","node-retirement","rejoin","fota"},ids)
        self.assertNotIn("browser",ids);self.assertNotIn("python",ids)
    def test_new_registered_component_test_automatically_joins_aggregates(self):
        d=copy.deepcopy(gate.load_registry())
        d["stages"].append({"id":"future-node","components":["node"],"command":["true"],"success":"PASS","timeout":1})
        for suite in ("node","fast","release"):
            self.assertIn("future-node",{s["id"] for s in gate.select(d,suite)})
    def test_zero_selection_fails(self):
        with self.assertRaises(ValueError): gate.select({"stages":[]},"node")
    def test_physical_not_run_never_means_qualified(self):
        r=gate.software_report_status([{"status":"PASS"}])
        self.assertEqual(r["software_status"],"PASS")
        self.assertEqual(r["physical_status"],"NOT_RUN")
        self.assertFalse(r["physically_qualified"]);self.assertFalse(r["release_approved"])
    def test_source_mutation_rejects_stale_fingerprint(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/"source.cpp").write_text("before")
            with patch.object(gate.subprocess,"check_output",return_value="source.cpp\n"):
                before=gate.source_fingerprint(root)
                (root/"source.cpp").write_text("after")
                self.assertNotEqual(before,gate.source_fingerprint(root))
    def test_reuse_requires_current_source_logs_and_binary_hashes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);log=root/'stage.log';binary=root/'binary'
            log.write_text('PASS tests=1\n');binary.write_bytes(b'executed-binary')
            stage=self.stage(command=['test'])
            row={'command':['test'],'status':'PASS','exit_code':0,'log':'stage.log',
                 'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                 'artifacts':{'binary':hashlib.sha256(binary.read_bytes()).hexdigest()}}
            report={'source_fingerprint':'source','source_unchanged':True,'build_profile':{}}
            self.assertEqual(gate.verify_receipt(stage,row,report,'source',{},root)['exit_code'],0)
            with self.assertRaisesRegex(ValueError,'source/profile'):
                gate.verify_receipt(stage,row,report,'different',{},root)
            binary.write_bytes(b'stale-or-tampered-binary')
            with self.assertRaisesRegex(ValueError,'binary'):
                gate.verify_receipt(stage,row,report,'source',{},root)
            binary.write_bytes(b'executed-binary');log.write_text('fabricated PASS')
            with self.assertRaisesRegex(ValueError,'log'):
                gate.verify_receipt(stage,row,report,'source',{},root)
    def test_empty_report_fails_software_qualification(self):
        self.assertEqual(gate.software_report_status([])['software_status'],'FAIL')
    def test_incomplete_nightly_never_reports_pass(self):
        from validation import nightly
        with tempfile.TemporaryDirectory() as t, patch.object(nightly,'EVIDENCE',Path(t)):
            rows=[{'suite':'one','status':'PASS','duration':0,'log':''}]
            report=nightly.write_report(rows,'branch','head',False,False,time.monotonic())
            self.assertEqual(report['status'],'RUNNING')
            self.assertFalse(report['physically_qualified'])
            self.assertEqual(nightly.write_report([], 'branch','head',False,False,time.monotonic(),complete=True)['status'],'FAIL')
    def test_unknown_component_and_duplicate_registration_fail(self):
        d=copy.deepcopy(gate.load_registry())
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'tests/cpp').mkdir(parents=True)
            for s in d['stages']:s['inputs']=[]
            p=root/'registry.json'
            d['stages'].append(copy.deepcopy(d['stages'][0]));p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'duplicate'):gate.load_registry(p,root)
            d['stages'].pop();d['stages'][0]['components']=['unowned'];p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'ownership'):gate.load_registry(p,root)
    def test_make_targets_delegate_to_registered_owner(self):
        mk=(ROOT/"Makefile").read_text()
        for name in ("node","hub","contract","backend","pwa"):
            self.assertIn("validation-"+name,mk)
        self.assertIn("--suite fast",mk);self.assertIn("--suite release",mk)
    def test_compiler_flags_have_distinct_cached_object_profiles(self):
        from scripts.host_build_profile import fingerprint
        self.assertNotEqual(fingerprint(["g++","-O2"]),fingerprint(["g++","-O0","-fsanitize=address"]))
    def test_source_content_invalidates_cache_even_with_preserved_mtime(self):
        from scripts.host_build_profile import source_signature
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'code.cpp';p.write_text('before');stamp=p.stat().st_mtime_ns
            before=source_signature(root,['code.cpp']);p.write_text('after')
            os.utime(p,ns=(stamp,stamp))
            self.assertNotEqual(before,source_signature(root,['code.cpp']))
    def test_cached_host_objects_keep_generated_and_header_dependencies(self):
        mk=(ROOT/'Makefile').read_text()
        self.assertIn('$(HOST_TEST_OBJECTS): Makefile build/gs40_generated/gs/node_health_config.hpp',mk)
        self.assertIn('-include $(HOST_TEST_OBJECTS:.o=.d)',mk)
        self.assertIn('-MMD -MP',mk)
    def test_special_fake_idf_include_recipe_is_not_shared_cached(self):
        mk=(ROOT/'Makefile').read_text()
        recipe=mk[mk.index('p2d-https-channel-host-test:'):].split('\n')[1]
        self.assertIn('-Itests/cpp/p2d_idf_fake',recipe)
        self.assertIn('firmware/hub/target/esp32s3/https_backend_channel.cpp',recipe)
        self.assertNotIn('host_objects',recipe)
    def test_simulator_links_production_replay_fence_implementation(self):
        mk=(ROOT/'Makefile').read_text()
        self.assertIn('GS116_SIMULATOR_HOST_SOURCES := tests/support/host/simulator/main.cpp firmware/hub/storage/durable_event_outbox.cpp',mk)
        self.assertIn('simulator: build $(CPP_OBJECTS)',mk)
    def test_linker_guard_and_include_overrides_invalidate_receipts(self):
        with patch.object(gate.subprocess,'check_output',return_value='compiler'):
            default=gate.build_profile({})
            self.assertNotEqual(default,gate.build_profile({'HOST_TOOLCHAIN_GUARD':'-B/other'}))
            self.assertNotEqual(default,gate.build_profile({'INCLUDES':'-Iother'}))
    def test_registry_rejects_missing_input_and_unregistered_harness(self):
        d=copy.deepcopy(gate.load_registry())
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/"tests/cpp").mkdir(parents=True)
            for s in d["stages"]: s["inputs"]=[]
            reg=root/"suites.json";reg.write_text(json.dumps(d))
            (root/"tests/cpp/unregistered.cpp").write_text("int main(){return 0;}")
            with self.assertRaisesRegex(ValueError,"unregistered"): gate.load_registry(reg,root)
            (root/"tests/cpp/unregistered.cpp").unlink()
            d["stages"][0]["inputs"]=["missing.cpp"];reg.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"missing dependency"): gate.load_registry(reg,root)
    def test_p0_e2e_registration_reaches_affected_components_and_release(self):
        data=gate.load_registry();stage=next(s for s in data["stages"] if s["id"]=="p0-full-product-e2e")
        self.assertIn("P0_SCENARIOS=",stage["command"],"official gate must clear developer-only scenario filters")
        for suite in ("node","hub","contract","backend","pwa","fast","release","p0-e2e"):
            self.assertIn(stage,gate.select(data,suite))
    def test_partial_p0_product_cannot_be_adjudicated_as_complete(self):
        stage=next(s for s in gate.load_registry()["stages"] if s["id"]=="p0-full-product-e2e")
        output="P0 E2E EXECUTION PASS scenarios=10 checks=10 browser_tests=1 product_status=PARTIAL physical=NOT_RUN"
        self.assertEqual(gate.adjudicate(stage,self.result(output)),"FAIL")
    def test_physical_hil_is_registered_opt_in_and_not_in_software_suites(self):
        data=gate.load_registry()
        physical=data["opt_in_physical_suites"]
        self.assertEqual(set(physical),{"validation-board-hil","validation-motion-hil"})
        makefile=(ROOT/"Makefile").read_text()
        for name, item in physical.items():
            self.assertFalse(item["automatic"])
            self.assertFalse(item["included_in_software_gates"])
            self.assertTrue(item["requires_operator_confirmation"])
            self.assertEqual(item["command"],["make",name])
            self.assertTrue((ROOT/item["runner"]).is_file())
            self.assertIn(name+":",makefile)
        for suite in ("node","hub","contract","backend","pwa","fast","release"):
            ids={stage["id"] for stage in gate.select(data,suite)}
            self.assertNotIn("validation-board-hil",ids)
            self.assertNotIn("validation-motion-hil",ids)

if __name__=="__main__":unittest.main()
