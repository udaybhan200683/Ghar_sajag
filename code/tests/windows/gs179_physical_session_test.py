"""GS-179 production session functions with mocked network/task effects.
Explicit Windows/PowerShell offline qualification; no OS mutation or hardware.
"""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools/local"))
class PhysicalIngressSessionTest(unittest.TestCase):
    """Execute production PowerShell functions with network/task effects mocked."""
    def powershell(self, body):
        import shutil
        import subprocess
        proxy = Path(__file__).resolve().parents[2] / "tools/local/gs179-windows-lan-proxy.ps1"
        executable = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not executable:
            self.fail("PowerShell required for production proxy function qualification")
        source = str(proxy)
        if executable.endswith("powershell.exe"):
            source = subprocess.check_output(["wslpath", "-w", source], text=True).strip()
        prelude = r"""
$ErrorActionPreference='Stop'
function Get-ScheduledTask {param($TaskName,$ErrorAction) return @{Name=$TaskName} }
$tokens=$null;$errors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile('__SOURCE__',[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
foreach($name in @('Is-Rfc1918','Get-Ipv4Network','Test-EquivalentIpv4Scope','Get-PhysicalSessionDecision','Close-PhysicalSession','Register-PhysicalSessionTasks','Invoke-PhysicalSessionTick','Get-PhysicalSessionWindow','Get-PhysicalAuthority')) {
 $node=$tree.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 . ([scriptblock]::Create($node.Extent.Text))
}
""".replace('__SOURCE__', source.replace("'", "''"))
        with tempfile.TemporaryDirectory(prefix="gs179-ps-test-") as temp:
            script=Path(temp)/"mock-test.ps1"
            script.write_text(prelude + body)
            script_path=str(script)
            if executable.endswith("powershell.exe"):
                script_path=subprocess.check_output(["wslpath","-w",script_path],text=True).strip()
            result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script_path],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        return json.loads(result.stdout.strip())

    def test_session_policy_failure_recovery_matrix(self):
        import json
        state = dict(started="2026-11-04T10:00:00Z", deadline="2026-11-04T11:00:00Z",
                     scope="scope", activation="activation", controller="123", service="456:hash",
                     timeProcess="789:start", target="172.17.152.10")
        observation = dict(authorized=True, services=True, cleanupReady=True, administrator=True,
                           scope="scope", activation="activation", controller="123", service="456:hash",
                           timeProcess="789:start", target="172.17.152.10", address="192.168.1.6",
                           wifi="Airtel_Agrim", prefix=24, profile="Private", firewall=True, routeOwned=True,
                           conflict=False, listening=True)
        cases=[]
        def add(name, changes=None, expected="CLOSE", now="2026-11-04T10:10:00Z", st=None):
            cases.append(dict(name=name,state=st or state,observation={**observation, **(changes or {})},
                              now=now,expected=expected))
        add("healthy_no_mutation",expected="KEEP")
        add("dormant_exact_recovery",dict(listening=False),"REPAIR")
        add("trusted_reconnect",dict(profile="DomainAuthenticated",listening=False),"REPAIR")
        add("verified_wsl_nat_change",dict(target="172.18.1.2"),"REPAIR")
        add("expired_services",dict(services=False))
        add("revoked_authority",dict(authorized=False))
        add("controller_crash",dict(controller="gone"))
        add("wrong_activation",dict(activation="replacement"))
        add("changed_service_identity",dict(service="other"))
        add("changed_time_service_identity",dict(timeProcess="other"))
        add("public_wifi",dict(profile="Public"))
        add("wrong_fixed_ip",dict(address="192.168.1.7"))
        add("wrong_ssid",dict(wifi="Yogi"))
        add("wrong_subnet",dict(prefix=16))
        add("conflicting_port",dict(conflict=True))
        add("unexpected_firewall",dict(firewall=False))
        add("unrelated_mapping",dict(routeOwned=False))
        add("missing_admin",dict(administrator=False))
        add("cleanup_unavailable",dict(cleanupReady=False))
        add("invalid_wsl_target",dict(target="8.8.8.8"))
        add("deadline",now="2026-11-04T11:00:00Z")
        add("clock_rollback",now="2026-11-04T09:59:59Z")
        add("deadline_extension",st={**state,"deadline":"2026-11-04T11:00:01Z"})
        add("invalid_negative_window",st={**state,"deadline":"2026-11-04T09:00:00Z"})
        data=json.dumps(cases).replace("'", "''")
        actual=self.powershell("$cases=ConvertFrom-Json '"+data+"'; @($cases|ForEach-Object {Get-PhysicalSessionDecision $_.state $_.observation ([DateTimeOffset]::Parse($_.now))})|ConvertTo-Json -Compress")
        for case,decision in zip(cases,actual):
            with self.subTest(case=case['name']): self.assertEqual(decision,case['expected'])
        self.assertEqual(len(actual),len(cases))
        print("CASE GS179-SESSION-POLICY-001 PASS scenarios="+str(len(cases)))

    def test_independent_cleanup_preserves_unrelated_state_and_retries_failure(self):
        result=self.powershell(r"""
$script:deleted=@();$script:tasks=@();$script:saved=0;$script:fail=$false
function Get-PortProxyRows { return @(
 [pscustomobject]@{ListenAddress='192.168.1.6';ListenPort=8445;TargetAddress='172.17.152.10';TargetPort=8445},
 [pscustomobject]@{ListenAddress='192.168.1.6';ListenPort=443;TargetAddress='172.17.152.10';TargetPort=8444},
 [pscustomobject]@{ListenAddress='192.168.1.7';ListenPort=8445;TargetAddress='172.17.152.10';TargetPort=8445},
 [pscustomobject]@{ListenAddress='192.168.1.6';ListenPort=8445;TargetAddress='172.18.1.9';TargetPort=8445}) }
function netsh.exe { $script:deleted+=($args -join ' ');$global:LASTEXITCODE=0;if($script:fail){$global:LASTEXITCODE=1} }
function Stop-WithError($reason){throw $reason}
function Save-PhysicalSession($s){$script:saved++}
function Unregister-ScheduledTask {param($TaskName,[switch]$Confirm,$ErrorAction) $script:tasks+=$TaskName}
$state=[pscustomobject]@{targets=@('172.17.152.10');tickTask='own-tick';expiryTask='own-expiry';closed=$false;exposureOwned=$true}
Close-PhysicalSession $state
$success=@{deleted=@($script:deleted);tasks=@($script:tasks);saved=$script:saved;closed=$state.closed}
# Cleanup failure must retain the independent task and unclosed state.
$script:deleted=@();$script:tasks=@();$script:saved=0;$script:fail=$true;$state.closed=$false
try{Close-PhysicalSession $state;throw 'expected failure'}catch{if($_.Exception.Message -ne 'physical_session_cleanup_failed'){throw}}
$failure=@{tasks=@($script:tasks);saved=$script:saved;closed=$state.closed}
# Failed start before ownership must not delete a pre-existing route.
$script:fail=$false;$script:deleted=@();$state.exposureOwned=$false
Close-PhysicalSession $state
@{success=$success;failure=$failure;unownedDeletes=@($script:deleted)}|ConvertTo-Json -Depth 6 -Compress
""")
        self.assertEqual(len(result['success']['deleted']),1)
        self.assertIn('listenaddress=192.168.1.6 listenport=8445',result['success']['deleted'][0])
        self.assertEqual(result['success']['tasks'],['own-tick','own-expiry'])
        self.assertTrue(result['success']['closed'])
        self.assertEqual(result['failure'],dict(tasks=[],saved=0,closed=False))
        self.assertEqual(result['unownedDeletes'],[])
        print("CASE GS179-SESSION-CLEANUP-001 PASS")


    def test_expiry_is_independent_and_registered_before_exposure(self):
        result=self.powershell(r"""
$script:registered=@();$SessionFile='C:\protected\session.json'
function New-ScheduledTaskSettingsSet {param([switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit,$RestartCount,$RestartInterval) return @{recover=$RestartCount;start=$StartWhenAvailable.IsPresent} }
function New-ScheduledTaskAction {param($Execute,$Argument) return @{exe=$Execute;args=$Argument} }
function New-ScheduledTaskTrigger {param([switch]$Once,$At,[switch]$AtStartup,$RepetitionInterval,$RepetitionDuration) return @{once=$Once.IsPresent;boot=$AtStartup.IsPresent;at=$At} }
function Register-ScheduledTask {param($TaskName,$Action,$Trigger,$User,$RunLevel,$Settings,$ErrorAction)
 $script:registered+=@{name=$TaskName;action=$Action;triggers=@($Trigger);user=$User;level=$RunLevel;settings=$Settings}
}
function Get-PhysicalTaskHash($name){return 'verified-task-definition'}
function Get-PhysicalObservation($s){return @{timeProcess='pinned-time-process'}}
function Save-PhysicalSession($s){}
$state=[pscustomobject]@{started='2026-11-04T10:00:00Z';deadline='2026-11-04T11:00:00Z';script='C:\protected\pinned.ps1';
 tickTask='own-tick';expiryTask='own-expiry';expiryHash='';timeProcess='';exposureOwned=$false}
Register-PhysicalSessionTasks $state
@{tasks=@($script:registered);owned=$state.exposureOwned;expiryHash=$state.expiryHash}|ConvertTo-Json -Depth 8 -Compress
""")
        expiry,tick=result['tasks']
        self.assertEqual(expiry['user'],'SYSTEM')
        self.assertEqual(expiry['name'],'own-expiry')
        self.assertTrue(any(t['boot'] for t in expiry['triggers']))
        self.assertTrue(any(t['once'] for t in expiry['triggers']))
        self.assertIn('-Action SessionClose',expiry['action']['args'])
        self.assertEqual(tick['name'],'own-tick')
        self.assertIn('-Action SessionTick',tick['action']['args'])
        self.assertFalse(result['owned'])
        self.assertEqual(result['expiryHash'],'verified-task-definition')
        self.assertEqual(expiry['settings']['recover'],3)
        print('CASE GS179-SESSION-EXPIRY-001 PASS')

    def test_existing_start_exact_repair_rollback_and_strict_session_guards(self):
        result=self.powershell(r"""
$startNode=$tree.Find({param($n) $n -is [Management.Automation.Language.IfStatementAst] -and
 $n.Extent.Text.StartsWith('if ($Action -eq "Start")') -and $n.Extent.Text.Contains('$createdFirewall')},$true)
$text=$startNode.Clauses[0].Item2.Extent.Text
$start=[scriptblock]::Create($text.Substring(1,$text.Length-2).Replace('exit 0','return'))
function Stop-WithError($reason){throw $reason}
function Get-NetFirewallAddressFilter { return @{LocalAddress='192.168.1.6';RemoteAddress=$script:remote} }
function Get-CimInstance {param($ClassName,$Filter) return @{ProcessId=22} }
function Get-NetTCPConnection {param($State,$LocalAddress,$LocalPort,$ErrorAction)
 if($script:healthy){return [pscustomobject]@{LocalAddress='192.168.1.6';OwningProcess=$script:owner}} }
function Get-PortProxyRows { return $script:rows }
function Wait-PortProxyListener { return $script:wait }
function New-NetFirewallRule {throw 'unexpected firewall creation'}
function Set-NetFirewallRule {throw 'unexpected firewall change'}
function netsh.exe { $script:calls+=($args -join ' ');$global:LASTEXITCODE=0 }
$all=@()
foreach($case in @('healthy','dormant','nat-change','rollback','firewall','other-row','wrong-ip','conflict','caregiver443','mask-scope')) {
 $Action='Start';$EndpointKind='PhysicalHubIngress';$SessionRestricted=$true
 $actualAddress='192.168.1.6';$profile=@{Name='Airtel_Agrim'};$ipInfo=@{PrefixLength=24}
 $ListenPort=8445;$TargetPort=8445;$scope='192.168.1.0/24';$firewallProfile='Private'
 $WslAddress='172.17.152.10';$PreviousWslAddress='172.17.152.10';$wslPrivate=$true;$wasWatch=$false
 $existingRule=@{Profile='Private';EdgeTraversalPolicy='Block'}
 $script:rows=@([pscustomobject]@{ListenAddress='192.168.1.6';ListenPort=8445;TargetAddress='172.17.152.10';TargetPort=8445})
 $mapRows=@($script:rows);$script:remote='192.168.1.0/24';$script:owner=4
 $script:healthy=($case -eq 'healthy' -or $case -eq 'conflict');$script:wait=($case -ne 'rollback');$script:calls=@()
 if($case -eq 'nat-change'){$WslAddress='172.18.1.2'}
 if($case -eq 'firewall'){$script:remote='Any'}
 if($case -eq 'mask-scope'){$script:remote='192.168.1.0/255.255.255.0'}
 if($case -eq 'wrong-ip'){$actualAddress='192.168.1.7'}
 if($case -eq 'conflict'){$script:owner=999}
 if($case -eq 'other-row'){$script:rows+= [pscustomobject]@{ListenAddress='192.168.1.7';ListenPort=8445;TargetAddress='172.17.152.10';TargetPort=8445}}
 if($case -eq 'caregiver443'){$SessionRestricted=$false;$EndpointKind='Caregiver';$ListenPort=443;$TargetPort=8444;$script:healthy=$true;$script:rows=@([pscustomobject]@{ListenAddress='192.168.1.6';ListenPort=443;TargetAddress='172.17.152.10';TargetPort=8444});$mapRows=@($script:rows)}
 $errorCode='';try{& $start|Out-Null}catch{$errorCode=$_.Exception.Message}
 $all+=@{name=$case;calls=@($script:calls);error=$errorCode}
}
ConvertTo-Json -InputObject $all -Depth 5 -Compress
""")
        by={x['name']:x for x in result}
        self.assertEqual(by['healthy']['calls'],[])
        self.assertEqual(by['healthy']['error'],'')
        for case in ('dormant','nat-change','mask-scope'):
            self.assertEqual(len(by[case]['calls']),2)
            self.assertEqual(by[case]['error'],'')
        self.assertIn('connectaddress=172.18.1.2',by['nat-change']['calls'][-1])
        self.assertEqual(by['rollback']['error'],'portproxy_listener_not_active')
        self.assertIn('connectaddress=172.17.152.10',by['rollback']['calls'][-1])
        for case in ('firewall','other-row','wrong-ip','conflict'):
            self.assertNotEqual(by[case]['error'],'')
            self.assertEqual(by[case]['calls'],[])
        self.assertEqual(by['caregiver443']['calls'],[])
        self.assertEqual(by['caregiver443']['error'],'')
        for case in result:
            for call in case['calls']:
                self.assertIn('listenport=8445',call)
                self.assertIn('listenaddress=192.168.1.6',call)
        print('CASE GS179-SESSION-REPAIR-001 PASS scenarios=10')

    def test_existing_authorization_and_service_identity_projection(self):
        import json,os,subprocess,hashlib
        from datetime import datetime,timezone,timedelta
        from unittest.mock import patch
        from gs179_verified_endpoint import physical_ingress_authority
        import gs117_hil_authorization as auth
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            directory=home/'.local/state/ghar-sajag/gs117-tc001/services-test'
            directory.mkdir(parents=True,mode=0o700)
            script=directory/'gs117-active-ingress.py'
            script.write_text('import time;time.sleep(60)')
            child=subprocess.Popen([sys.executable,str(script)])
            try:
                row={'script':script.name,'pid':child.pid,'sha256':hashlib.sha256(script.read_bytes()).hexdigest()}
                manifest=directory/'launch-manifest.json'
                manifest.write_text(json.dumps({'processes':[row]}));manifest.chmod(0o600)
                status=directory/'ingress-runtime-status.json'
                runtime={'pid':child.pid,'at':datetime.now(timezone.utc).isoformat(),'status':{
                    'listener_ready':'YES','postgres_ready':'YES','trusted_time_ready':'YES','profile':'GS179_TEST_ONLY'}}
                status.write_text(json.dumps(runtime));status.chmod(0o600)
                policy=dict(owner_approval_ref='GS-117#99999',procedures=['protected_gs40_bootstrap'],
                    max_sessions=1,max_retries=0,observation_seconds=90,max_bootstraps_per_session=1,
                    motion_injection_authorized=False,development_mode={'activation_id':'active'})
                with patch.object(Path,'home',return_value=home),patch.object(auth,'load_development',return_value=policy),\
                     patch.object(auth,'development_status',return_value={'status':'ACTIVE','authorization_scope_id':'scope'}),\
                     patch('gs179_verified_endpoint.wsl_ipv4',return_value='172.17.152.10'):
                    result=physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                    self.assertEqual(result['scope_id'],'scope')
                    self.assertEqual(result['service_pid'],child.pid)
                    self.assertTrue(result['controller_start'])
                    for key,value in [('max_sessions',2),('motion_injection_authorized',True),
                                      ('max_retries',1),('observation_seconds',120)]:
                        before=policy[key];policy[key]=value
                        with self.subTest(key=key),self.assertRaises(ValueError):
                            physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                        policy[key]=before
                    with self.assertRaises(ValueError):
                        physical_ingress_authority('GS-117#other',os.getpid(),str(directory))
                    # Existing pessimistic live reservation is accepted only
                    # while its real shared flock is held and it has no fault.
                    import fcntl
                    auth_state=home/'auth-state';auth_state.mkdir(mode=0o700)
                    ledger=auth_state/'ledger.json'
                    row=dict(started_at=datetime.now(timezone.utc).isoformat(),procedure='protected_gs40_bootstrap')
                    ledger.write_text(json.dumps(row));ledger.chmod(0o600)
                    lock=auth_state/'session.lock';lock.touch(mode=0o600)
                    with patch.object(auth,'DEV_STATE',auth_state),patch.object(auth,'_development_ledger_path',return_value=(ledger,'scope')),\
                         patch.object(auth,'development_status',return_value={'status':'SAFETY_LATCHED','authorization_scope_id':'scope'}):
                        with lock.open('r') as holder:
                            fcntl.flock(holder,fcntl.LOCK_EX|fcntl.LOCK_NB)
                            self.assertEqual(physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))['scope_id'],'scope')
                            ledger.write_text(json.dumps({**row,'failure':'security'}))
                            with self.assertRaises(ValueError):
                                physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                        ledger.write_text(json.dumps(row))
                        with self.assertRaises(ValueError):
                            physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))

                    for change in [{'at':(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()},
                                   {'pid':child.pid+1}, {'status':{**runtime['status'],'profile':'OTHER'}}]:
                        status.write_text(json.dumps({**runtime,**change}))
                        with self.subTest(change=change),self.assertRaises(ValueError):
                            physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                    status.write_text(json.dumps(runtime))
                    manifest.chmod(0o644)
                    with self.assertRaises(ValueError):
                        physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                    manifest.chmod(0o600)
                    script.write_text('changed')
                    with self.assertRaises(ValueError):
                        physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
                    with patch.object(auth,'load_development',side_effect=ValueError('revoked')):
                        with self.assertRaises(ValueError):
                            physical_ingress_authority('GS-117#99999',os.getpid(),str(directory))
            finally:
                child.terminate();child.wait(timeout=5)
        print('CASE GS179-SESSION-AUTHORITY-001 PASS')

    def test_task_registration_failure_closes_without_exposure(self):
        result=self.powershell(r"""
$SessionFile='C:\protected\session.json';$script:results=@()
function New-ScheduledTaskSettingsSet {param([switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit,$RestartCount,$RestartInterval) return @{} }
function New-ScheduledTaskAction {param($Execute,$Argument) return @{} }
function New-ScheduledTaskTrigger {param([switch]$Once,$At,[switch]$AtStartup,$RepetitionInterval,$RepetitionDuration) return @{} }
function Get-PhysicalTaskHash($name){return 'hash'}
function Get-PhysicalObservation($s){return @{timeProcess='time'}}
function Save-PhysicalSession($s){}
function Get-PortProxyRows {return @()}
function Unregister-ScheduledTask {param($TaskName,[switch]$Confirm,$ErrorAction) $script:removed+=$TaskName}
function Register-ScheduledTask {param($TaskName,$Action,$Trigger,$User,$RunLevel,$Settings,$ErrorAction)
 if($TaskName -eq $script:failTask){throw 'mock-registration-denied'} }
foreach($failure in @('expiry','tick')) {
 $state=[pscustomobject]@{started='2026-11-04T10:00:00Z';deadline='2026-11-04T11:00:00Z';script='C:\protected\pinned.ps1';
 tickTask='tick';expiryTask='expiry';expiryHash='';timeProcess='';exposureOwned=$false;closed=$false}
 $script:failTask=$failure;$script:removed=@()
 try{Register-PhysicalSessionTasks $state;throw 'expected registration failure'}catch{if($_.Exception.Message -ne 'mock-registration-denied'){throw}}
 $script:results+=@{owned=$state.exposureOwned;closed=$state.closed;removed=@($script:removed)}
}
ConvertTo-Json -InputObject $script:results -Depth 6 -Compress
""")
        for row in result:
            self.assertFalse(row['owned'])
            self.assertTrue(row['closed'])
            self.assertEqual(row['removed'],['tick','expiry'])
        print('CASE GS179-SESSION-TASK-FAILURE-001 PASS')

    def test_worker_trigger_to_recovery_and_crash_expiry_cleanup(self):
        result=self.powershell(r"""
$script:repairs=0;$script:closes=0
function Save-PhysicalSession($s){}
function Close-PhysicalSession($s){$script:closes++;$s.closed=$true}
function Repair-PhysicalSessionRoute($s,$prior){$script:repairs++;if($script:mode -eq 'failure'){throw 'mock-repair-failure'}}
function Get-PhysicalObservation($s) {return [pscustomobject]@{
 authorized=($script:mode -ne 'revoked');services=($script:mode -ne 'expired-service');
 cleanupReady=$true;administrator=$true;scope='scope';activation='activation';controller=$(if($script:mode -eq 'crash'){'dead'}else{'controller'});
 service='service';timeProcess='time';address='192.168.1.6';wifi='Airtel_Agrim';prefix=24;profile='Private';firewall=$true;routeOwned=$true;
 conflict=$false;target='172.17.152.10';listening=($script:mode -eq 'healthy')} }
$results=@()
foreach($script:mode in @('healthy','dormant','crash','revoked','expired-service','deadline','failure','dormant')) {
 $state=[pscustomobject]@{started=[DateTimeOffset]::UtcNow.AddMinutes(-1).ToString('o');deadline=[DateTimeOffset]::UtcNow.AddMinutes(1).ToString('o');
 scope='scope';activation='activation';controller='controller';service='service';timeProcess='time';target='172.17.152.10';targets=@('172.17.152.10');closed=$false}
 if($script:mode -eq 'deadline'){$state.deadline=[DateTimeOffset]::UtcNow.AddSeconds(-1).ToString('o')}
 $script:repairs=0;$script:closes=0;$errorCode='';$decision=''
 try{$decision=(Invoke-PhysicalSessionTick $state).Decision}catch{$errorCode=$_.Exception.Message}
 $results+=@{mode=$script:mode;repairs=$script:repairs;closes=$script:closes;decision=$decision;error=$errorCode}
}
ConvertTo-Json -InputObject $results -Depth 4 -Compress
""")
        for row in result:
            if row['mode']=='healthy':
                self.assertEqual((row['repairs'],row['closes'],row['decision']),(0,0,'KEEP'))
            elif row['mode']=='dormant':
                self.assertEqual((row['repairs'],row['closes'],row['decision']),(1,0,'REPAIR'))
            elif row['mode']=='failure':
                self.assertEqual((row['repairs'],row['closes'],row['error']),(1,1,'mock-repair-failure'))
            else:
                self.assertEqual((row['repairs'],row['closes'],row['decision']),(0,1,'CLOSE'))
        print('CASE GS179-SESSION-WORKER-001 PASS scenarios=8')

    def test_repeated_start_stop_cannot_renew_scope_deadline(self):
        result=self.powershell(r"""
function Stop-WithError($r){throw $r}
$at=[DateTimeOffset]::Parse('2026-11-04T10:00:00Z')
$first=Get-PhysicalSessionWindow @() 'scope' 'activation' $at 3600
$old=[pscustomobject]@{scope='scope';activation='activation';started=$first.started;deadline=$first.deadline;closed=$true}
$next=Get-PhysicalSessionWindow @($old) 'scope' 'activation' $at.AddMinutes(30) 3600
$other=Get-PhysicalSessionWindow @($old) 'new-scope' 'new-activation' $at.AddMinutes(30) 3600
$expired=$false;try{Get-PhysicalSessionWindow @($old) 'scope' 'activation' $at.AddHours(1) 3600|Out-Null}catch{$expired=$true}
$tooLong=$false;try{Get-PhysicalSessionWindow @() 'scope' 'activation' $at 3601|Out-Null}catch{$tooLong=$true}
@{first=$first;next=$next;other=$other;expired=$expired;tooLong=$tooLong}|ConvertTo-Json -Depth 5 -Compress
""")
        self.assertEqual(result['first'],result['next'])
        self.assertNotEqual(result['first']['deadline'],result['other']['deadline'])
        self.assertTrue(result['expired'])
        self.assertTrue(result['tooLong'])
        print('CASE GS179-SESSION-WINDOW-001 PASS')

    def test_authority_helper_integrity_rejected_before_wsl_execution(self):
        result=self.powershell(r"""
function Stop-WithError($reason){throw $reason}
function Get-FileHash {param($Path,$Algorithm) return @{Hash=('b'*64)} }
$results=@()
foreach($hash in @('',('a'*64))) {
 try {Get-PhysicalAuthority 'GS-117#99999' 123 '/home/udaybhan/.local/state/ghar-sajag/gs117-tc001/services-test' $hash | Out-Null;throw 'expected rejection'}
 catch {$results+=$_.Exception.Message}
}
ConvertTo-Json -InputObject $results -Compress
""")
        self.assertEqual(result,['physical_session_inputs_invalid','physical_session_authority_helper_changed'])
        print('CASE GS179-SESSION-HELPER-PIN-001 PASS')

    def test_windows_firewall_mask_notation_is_equivalent_without_scope_widening(self):
        result=self.powershell(r"""
@(
 (Test-EquivalentIpv4Scope @('192.168.1.0/255.255.255.0') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('192.168.1.0/24') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('192.168.1.0/255.255.0.0') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('192.168.2.0/24') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('Any') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('192.168.1.0/24','10.0.0.0/8') '192.168.1.0/24'),
 (Test-EquivalentIpv4Scope @('192.168.1.0/255.0.255.0') '192.168.1.0/24')
)|ConvertTo-Json -Compress
""")
        self.assertEqual(result,[True,True,False,False,False,False,False])
        print('CASE GS179-SESSION-FIREWALL-NORMALIZATION-001 PASS')

if __name__ == "__main__":
    unittest.main()
