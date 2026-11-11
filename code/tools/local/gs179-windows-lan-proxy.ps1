param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Audit", "Start", "Stop", "Watch", "RegisterWatch", "UnregisterWatch", "SessionStart", "SessionTick", "SessionClose")]
    [string]$Action,
    [string]$WslAddress = "",
    [string]$PreviousWslAddress = "",
    [string]$LinuxScriptPath = "",
    [ValidateSet("Caregiver", "PhysicalHubIngress")]
    [string]$EndpointKind = "Caregiver",
    [string]$SessionFile = "",
    [string]$ApprovalRef = "",
    [int]$ControllerPid = 0,
    [string]$ServiceDirectory = "",
    [string]$AuthorityHelperSha256 = "",
    [ValidateSet('', 'A', 'B', 'DEV')][string]$NetworkWindow = '',
    [string]$NetworkApprovalSha256 = '',
    [string]$NetworkLeaseId = '',
    [ValidateRange(1, 3600)][int]$SessionSeconds = 3600,
    [switch]$SessionRestricted
)

$ErrorActionPreference = "Stop"
$RuleName = "GS179-Local-LAN-HTTPS"
$RuleDescription = "GS-179 TEST_ONLY caregiver HTTPS, limited to the active owner Wi-Fi subnet."
$WatchTaskName = "Ghar Sajag GS-179 Trusted Wi-Fi Reconnect"
$ListenPort = 443
$TargetPort = 8444
$RuleDisplayName = "Ghar Sajag GS-179 Local Validation HTTPS"
if ($EndpointKind -eq "PhysicalHubIngress") {
    # Explicit GS-117 TEST_ONLY data ingress; never the loopback test console.
    # Reuse the same Private/Domain Wi-Fi, subnet and administrator guards.
    if ($Action -notlike "Session*" -and $Action -notin @("Audit", "Start", "Stop")) {
        throw "GS179-WINDOWS-PROXY BLOCKED: physical_hub_ingress_watch_not_enabled"
    }
    $RuleName = "GS117-Physical-Hub-mTLS"
    $RuleDescription = "GS-117 TEST_ONLY physical Hub mTLS, limited to the active owner Wi-Fi subnet."
    $RuleDisplayName = "Ghar Sajag GS-117 Physical Hub mTLS"
    $ListenPort = 8445
    $TargetPort = 8445
}

function Stop-WithError([string]$Message) {
    throw ("GS179-WINDOWS-PROXY BLOCKED: " + $Message)
}

function Assert-Administrator {
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Stop-WithError "administrator_token_required_for_scoped_portproxy_and_firewall_rule"
    }
}

function Test-LinuxScriptPath([string]$Path) {
    return $Path -match '^/[A-Za-z0-9_./-]+$'
}

function Is-Rfc1918([string]$Address) {
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed) -or
        $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $bytes = $parsed.GetAddressBytes()
    return ($bytes[0] -eq 10) -or
        ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
        ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
}

function Get-Ipv4Network([string]$Address, [int]$PrefixLength) {
    $bytes = ([System.Net.IPAddress]::Parse($Address)).GetAddressBytes()
    $network = New-Object byte[] 4
    for ($index = 0; $index -lt 4; $index++) {
        $remaining = $PrefixLength - ($index * 8)
        if ($remaining -ge 8) { $mask = 255 }
        elseif ($remaining -le 0) { $mask = 0 }
        else { $mask = (255 -shl (8 - $remaining)) -band 255 }
        $network[$index] = [byte]($bytes[$index] -band $mask)
    }
    return (([System.Net.IPAddress]::new($network)).ToString() + "/" + $PrefixLength)
}

function Test-EquivalentIpv4Scope($Actual, [string]$Expected) {
    $values=@($Actual)
    if ($values.Count -ne 1) { return $false }
    $normalized=@()
    foreach($value in @([string]$values[0],$Expected)) {
        $parts=$value.Split('/')
        if($parts.Count -ne 2){return $false}
        $address=$null
        if(-not [Net.IPAddress]::TryParse($parts[0],[ref]$address) -or $address.AddressFamily -ne 'InterNetwork'){return $false}
        $prefix=0
        if($parts[1].Contains('.')) {
            $mask=$null
            if(-not [Net.IPAddress]::TryParse($parts[1],[ref]$mask) -or $mask.AddressFamily -ne 'InterNetwork'){return $false}
            $bits=($mask.GetAddressBytes()|ForEach-Object {[Convert]::ToString($_,2).PadLeft(8,'0')}) -join ''
            if($bits -notmatch '^1*0*$'){return $false}
            $prefix=($bits -replace '0','').Length
        } elseif(-not [int]::TryParse($parts[1],[ref]$prefix) -or $prefix -lt 0 -or $prefix -gt 32){return $false}
        $normalized+=Get-Ipv4Network $parts[0] $prefix
    }
    return $normalized[0] -eq $normalized[1]
}

function Get-PortProxyRows {
    $output = & netsh.exe interface portproxy show v4tov4 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_query_failed" }
    $rows = @()
    foreach ($line in $output) {
        if ([string]$line -match '^\s*(?<listen>[0-9]{1,3}(?:\.[0-9]{1,3}){3})\s+(?<lport>[0-9]+)\s+(?<target>[0-9]{1,3}(?:\.[0-9]{1,3}){3})\s+(?<tport>[0-9]+)\s*$') {
            $rows += [pscustomobject]@{
                ListenAddress = $Matches.listen
                ListenPort = [int]$Matches.lport
                TargetAddress = $Matches.target
                TargetPort = [int]$Matches.tport
            }
        }
    }
    return $rows
}

function Get-ExactFirewallRule {
    $rule = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule) { return $null }
    $port = $rule | Get-NetFirewallPortFilter
    $interface = $rule | Get-NetFirewallInterfaceFilter
    if ($rule.Direction -ne "Inbound" -or $rule.Action -ne "Allow" -or
        $rule.Enabled -ne "True" -or
        $port.Protocol -ne "TCP" -or $port.LocalPort -ne "$ListenPort" -or
        (@($interface.InterfaceAlias) -join ",") -ne "Wi-Fi" -or
        $rule.Description -ne $RuleDescription) {
        Stop-WithError "existing_firewall_rule_does_not_match_gs179_lan_scope"
    }
    return $rule
}

function Wait-PortProxyListener([string]$Address, [int]$Port) {
    for ($attempt = 0; $attempt -lt 12; $attempt++) {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalAddress $Address `
            -LocalPort $Port -ErrorAction SilentlyContinue)
        if ($listeners.Count -gt 0) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Get-NetstatListenerCount([string]$Address, [int]$Port) {
    $output = & netstat.exe -ano -p tcp 2>&1
    if ($LASTEXITCODE -ne 0) { return $null }
    $count = 0
    foreach ($line in $output) {
        $parts = ([string]$line).Trim() -split '\s+'
        if ($parts.Count -ge 4 -and $parts[0] -eq "TCP" -and
            $parts[1] -eq "$Address`:$Port" -and $parts[3] -eq "LISTENING") {
            $count++
        }
    }
    return $count
}

function Get-ActiveWifiState([bool]$WaitForReady) {
    $attempts = if ($WaitForReady) { 30 } else { 1 }
    for ($attempt = 0; $attempt -lt $attempts; $attempt++) {
        $adapter = Get-NetAdapter -Name "Wi-Fi" -ErrorAction SilentlyContinue
        $profile = Get-NetConnectionProfile -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
            Where-Object { $_.IPv4Connectivity -ne "Disconnected" } | Select-Object -First 1
        $ipInfo = Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.AddressState -eq "Preferred" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1
        if ($null -ne $adapter -and $adapter.Status -eq "Up" -and
            $null -ne $profile -and $null -ne $ipInfo) {
            return [pscustomobject]@{ Adapter = $adapter; Profile = $profile; IpInfo = $ipInfo }
        }
        if ($attempt + 1 -lt $attempts) { Start-Sleep -Seconds 2 }
    }
    Stop-WithError "active_wifi_ipv4_unavailable_after_bounded_wait"
}

function Get-NetworkCategoryName($Category) {
    if ($Category -is [string] -and $Category -in @("Public", "Private", "DomainAuthenticated")) {
        return $Category
    }
    try {
        switch ([int]$Category) {
            0 { return "Public" }
            1 { return "Private" }
            2 { return "DomainAuthenticated" }
        }
    } catch { }
    return "Unknown"
}

function Test-TrustedWifiProfile($Category) {
    return (Get-NetworkCategoryName $Category) -in @("Private", "DomainAuthenticated")
}


# Opt-in session actions are never reached by the installed default 443 Watch.
# State and a pinned script snapshot are administrator/SYSTEM writable only.
function Get-PhysicalSessionWindow($Prior, [string]$Scope, [string]$Activation, [DateTimeOffset]$Now, [int]$Seconds,
    [string]$LeaseStarted='', [string]$LeaseDeadline='') {
    if ($Seconds -lt 1 -or $Seconds -gt 3600) { Stop-WithError 'physical_session_duration_invalid' }
    $start=$Now;$deadline=$Now.AddSeconds($Seconds)
    foreach($old in @($Prior)) {
        if($old.scope -eq $Scope -and $old.activation -eq $Activation) {
            $priorStart=[DateTimeOffset]::Parse($old.started)
            $priorEnd=[DateTimeOffset]::Parse($old.deadline)
            if($priorStart -lt $start){$start=$priorStart}
            if($priorEnd -lt $deadline){$deadline=$priorEnd}
        }
    }
    if ($LeaseStarted -or $LeaseDeadline) {
        $issued=[DateTimeOffset]::Parse($LeaseStarted);$end=[DateTimeOffset]::Parse($LeaseDeadline)
        if ($Now -lt $issued -or $Now -ge $end -or ($end-$issued).TotalSeconds -gt 3600) {
            Stop-WithError 'physical_session_scope_window_expired'
        }
        if($issued -lt $start){$start=$issued}
        if($end -lt $deadline){$deadline=$end}
    }
    if($Now -ge $deadline -or $Now -lt $start -or ($deadline-$start).TotalSeconds -gt 3600) {
        Stop-WithError 'physical_session_scope_window_expired'
    }
    return [pscustomobject]@{started=$start.ToString('o');deadline=$deadline.ToString('o')}
}

function Assert-PhysicalWindowOrder($Prior, [string]$ApprovalHash, [string]$Window) {
    if (-not $Window) { return } # Old receipts retain their original contract.
    if (@($Prior | Where-Object { -not $_.closed }).Count -gt 0) {
        Stop-WithError 'physical_session_already_exists'
    }
    if ($Window -eq 'A' -and @($Prior | Where-Object {
        $_.networkApprovalSha256 -eq $ApprovalHash -and $_.networkWindow -eq 'B'
    }).Count -gt 0) { Stop-WithError 'network_window_order_invalid' }
    if ($Window -eq 'B' -and @($Prior | Where-Object {
        $_.networkApprovalSha256 -eq $ApprovalHash -and $_.networkWindow -eq 'A' -and
        $_.closed -and $_.exposureOwned
    }).Count -eq 0) { Stop-WithError 'network_window_a_cleanup_required' }
}

function Get-PhysicalSessionDecision($State, $Observation, [DateTimeOffset]$Now) {
    if ($Now -ge [DateTimeOffset]::Parse($State.deadline) -or
        $Now -lt [DateTimeOffset]::Parse($State.started) -or
        ([DateTimeOffset]::Parse($State.deadline) - [DateTimeOffset]::Parse($State.started)).TotalSeconds -gt 3600 -or
        ([DateTimeOffset]::Parse($State.deadline) - [DateTimeOffset]::Parse($State.started)).TotalSeconds -le 0 -or
        -not $Observation.authorized -or -not $Observation.services -or
        -not $Observation.cleanupReady -or -not $Observation.administrator -or
        $Observation.scope -ne $State.scope -or $Observation.activation -ne $State.activation -or
        $Observation.controller -ne $State.controller -or
        $Observation.service -ne $State.service -or $Observation.timeProcess -ne $State.timeProcess -or
        $Observation.address -ne '192.168.1.6' -or $Observation.prefix -ne 24 -or $Observation.wifi -ne 'Airtel_Agrim' -or
        $Observation.profile -notin @('Private','DomainAuthenticated') -or
        -not $Observation.firewall -or -not $Observation.routeOwned -or
        $Observation.target -notmatch '^172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}$' -or
        -not (Is-Rfc1918 $Observation.target) -or $Observation.conflict) {
        return 'CLOSE'
    }
    if ($Observation.target -eq $State.target -and $Observation.listening) { return 'KEEP' }
    return 'REPAIR'
}

function Assert-PhysicalSessionFile([string]$Path) {
    $base = 'C:\ProgramData\GharSajag\PhysicalIngress'
    if ([IO.Path]::GetDirectoryName($Path) -ne $base -or
        [IO.Path]::GetFileName($Path) -notmatch '^[a-f0-9]{32}\.json$') {
        Stop-WithError 'physical_session_path_invalid'
    }
    foreach ($item in @($base,$Path)) {
        if ((Get-Item -LiteralPath $item).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Stop-WithError 'physical_session_reparse_point'
        }
        $acl=Get-Acl -LiteralPath $item
        if ($acl.Owner -notin @('BUILTIN\Administrators','NT AUTHORITY\SYSTEM') -or
            @($acl.Access | Where-Object {
                $_.AccessControlType -ne 'Allow' -or
                $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')
            }).Count -gt 0) { Stop-WithError 'physical_session_acl_invalid' }
    }
}

function Save-PhysicalSession($State) {
    $temp=$SessionFile+'.tmp'
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temp -Encoding UTF8
    $acl=Get-Acl -LiteralPath $temp
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    Set-Acl -LiteralPath $temp -AclObject $acl
    Move-Item -LiteralPath $temp -Destination $SessionFile -Force
    $eventPath=$SessionFile+'.events.jsonl'
    if ((Test-Path $eventPath) -and ((Get-Item $eventPath).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Stop-WithError 'physical_session_event_reparse_point'
    }
    [ordered]@{at=[DateTimeOffset]::UtcNow.ToString('o');scope=$State.scope;
        deadline=$State.deadline;closed=$State.closed;decision=$State.lastDecision;
        closureSid=$State.closureSid} |
        ConvertTo-Json -Compress | Add-Content -LiteralPath $eventPath -Encoding UTF8
    $eventAcl=Get-Acl $eventPath
    $eventAcl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    Set-Acl -LiteralPath $eventPath -AclObject $eventAcl

}

function Close-PhysicalSession($State) {
    # No firewall removal and no matching by port alone. Keep expiry/retry tasks
    # if cleanup fails so a failed netsh invocation cannot silently end recovery.
    if (-not $State.closed) {
    foreach ($row in @(Get-PortProxyRows | Where-Object { $State.exposureOwned })) {
        if ($row.ListenAddress -eq '192.168.1.6' -and $row.ListenPort -eq 8445 -and
            $row.TargetPort -eq 8445 -and $row.TargetAddress -in @($State.targets)) {
            & netsh.exe interface portproxy delete v4tov4 listenaddress=192.168.1.6 listenport=8445 | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError 'physical_session_cleanup_failed' }
        }
    }
    $State.closed=$true
    $State | Add-Member -NotePropertyName closureSid -NotePropertyValue ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value) -Force
    $State | Add-Member -NotePropertyName closedAt -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString('o')) -Force
    Save-PhysicalSession $State
    }
    foreach ($name in @($State.tickTask,$State.expiryTask)) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
        }
    }
}

function Set-PhysicalExpiryTask($state, [switch]$Update) {
    $exe=Join-Path $PSHOME 'powershell.exe'
    $expiryArgs="-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$($state.script)`" -Action SessionClose -EndpointKind PhysicalHubIngress -SessionFile `"$SessionFile`""
    $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $at=if($state.cleanupDeadline){$state.cleanupDeadline}else{$state.deadline}
    $force=@{};if($Update){$force=@{Force=$true}}
    Register-ScheduledTask -TaskName $state.expiryTask -Action (New-ScheduledTaskAction -Execute $exe -Argument $expiryArgs) `
        -Trigger @((New-ScheduledTaskTrigger -Once -At ([DateTimeOffset]::Parse($at)).LocalDateTime),(New-ScheduledTaskTrigger -AtStartup)) `
        -User 'SYSTEM' -RunLevel Highest -Settings $settings -ErrorAction Stop @force | Out-Null
    $state.expiryHash=Get-PhysicalTaskHash $state.expiryTask
}

function Register-PhysicalSessionTasks($state) {
    try {
        $exe=Join-Path $PSHOME 'powershell.exe'
        $tickArgs="-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$($state.script)`" -Action SessionTick -EndpointKind PhysicalHubIngress -SessionFile `"$SessionFile`""
        $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        # Independent SYSTEM expiry/startup cleanup survives WSL/controller exit.
        Set-PhysicalExpiryTask $state
        $state.timeProcess=(Get-PhysicalObservation $state).timeProcess
        Save-PhysicalSession $state
        Register-ScheduledTask -TaskName $state.tickTask -Action (New-ScheduledTaskAction -Execute $exe -Argument $tickArgs) `
            -Trigger (New-ScheduledTaskTrigger -Once -At ([DateTimeOffset]::Parse($state.started)).AddSeconds(1).LocalDateTime -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Seconds ([Math]::Max(60,([int]([DateTimeOffset]::Parse($state.deadline)-[DateTimeOffset]::Parse($state.started)).TotalSeconds))))) `
            -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -RunLevel Highest -Settings $settings -ErrorAction Stop | Out-Null
    } catch { Close-PhysicalSession $state;throw }
}

function Get-PhysicalTaskHash([string]$Name) {
    $xml=Export-ScheduledTask -TaskName $Name -ErrorAction Stop
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($xml)))).Replace('-','') } finally { $sha.Dispose() }
}

function Get-PhysicalAuthority([string]$Reference,[int]$PidValue,[string]$Directory,[string]$ExpectedHelper,
    [string]$Window='', [string]$ApprovalHash='', [string]$LeaseId='', [switch]$IssueNext) {
    if ($Reference -notmatch '^GS-(117|179)#[0-9]+$' -or $PidValue -lt 1 -or
        $Directory -notmatch '^/home/udaybhan/\.local/state/ghar-sajag/gs117-tc001/[A-Za-z0-9_-]+$' -or
        $ExpectedHelper -notmatch '^[a-fA-F0-9]{64}$') {
        Stop-WithError 'physical_session_inputs_invalid'
    }
    if ($Window -eq 'DEV') {
        if ($Reference -notin @('GS-179#11916','GS-179#11947') -or $ApprovalHash -notmatch '^[a-f0-9]{64}$' -or
            $LeaseId -notmatch '^[a-f0-9]{64}$') { Stop-WithError 'physical_session_network_inputs_invalid' }
    } elseif (($Window -and ($Window -notin @('A','B') -or $Reference -ne 'GS-117#11910' -or
            $ApprovalHash -notmatch '^[a-f0-9]{64}$')) -or
        (-not $Window -and ($ApprovalHash -or $Reference -notmatch '^GS-117#' -or $Reference -eq 'GS-117#11910')) -or $LeaseId -or $IssueNext) {
        Stop-WithError 'physical_session_network_inputs_invalid'
    }
    $helper='\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\code\tools\local\gs179_verified_endpoint.py'
    if ((Get-FileHash $helper -Algorithm SHA256).Hash -ne $ExpectedHelper) {
        Stop-WithError 'physical_session_authority_helper_changed'
    }
    $wsl=Join-Path ([Environment]::SystemDirectory) 'wsl.exe'
    $networkArgs=@()
    if ($Window) { $networkArgs=@('--network-window',$Window,'--network-approval-sha256',$ApprovalHash) }
    if ($Window -eq 'DEV') { $networkArgs+=@('--network-lease-id',$LeaseId) }
    if ($IssueNext) { $networkArgs+='--issue-development-sublease' }
    $raw=& $wsl --exec /usr/bin/python3 /home/udaybhan/projects/Ghar_sajag_r1/code/tools/local/gs179_verified_endpoint.py `
        --physical-ingress-authority $Reference --controller-pid $PidValue --service-directory $Directory @networkArgs
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'physical_session_authority_or_services_unavailable' }
    return ($raw | ConvertFrom-Json)
}

function Get-PhysicalObservation($State) {
    $authority=Get-PhysicalAuthority $State.approval $State.pid $State.directory $State.authorityHelperSha256 $State.networkWindow $State.networkApprovalSha256 $State.networkLeaseId
    $wifi=Get-ActiveWifiState $false
    $rule=Get-ExactFirewallRule
    $addressFilter=$rule | Get-NetFirewallAddressFilter
    $profile=Get-NetworkCategoryName $wifi.Profile.NetworkCategory
    $expectedProfile=if($profile -eq 'DomainAuthenticated'){'Domain'}else{$profile}
    $firewall=($null -ne $rule -and
        (@($addressFilter.LocalAddress) -join ',') -eq '192.168.1.6' -and
        (Test-EquivalentIpv4Scope $addressFilter.RemoteAddress '192.168.1.0/24') -and
        (@($rule.Profile) -join ',') -eq $expectedProfile -and $rule.EdgeTraversalPolicy -eq 'Block')
    $rows=@(Get-PortProxyRows | Where-Object ListenPort -eq 8445)
    $owned=($rows.Count -eq 0 -or ($rows.Count -eq 1 -and
        $rows[0].ListenAddress -eq '192.168.1.6' -and $rows[0].TargetPort -eq 8445 -and
        $rows[0].TargetAddress -in @($State.targets)))
    $listeners=@(Get-NetTCPConnection -State Listen -LocalPort 8445 -ErrorAction SilentlyContinue)
    # A portproxy listener is owned by IP Helper (svchost) or the System stack.
    $iphelper=Get-CimInstance Win32_Service -Filter "Name='iphlpsvc'"
    $conflict=@($listeners|Where-Object {
        $_.LocalAddress -ne '192.168.1.6' -or $_.OwningProcess -notin @(4,$iphelper.ProcessId)
    }).Count -gt 0
    $udp=@(Get-NetUDPEndpoint -LocalAddress '192.168.1.6' -LocalPort 4468 -ErrorAction SilentlyContinue)
    $timeProcess=if($udp.Count -eq 1){
        $proc=Get-Process -Id $udp[0].OwningProcess -ErrorAction Stop
        $identity=Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)"
        if ($identity.ExecutablePath -ne 'C:\Users\DELL\AppData\Local\Programs\Python\Python312\python.exe' -or
            $identity.CommandLine -notlike '*from gs40_test_bootstrap import SignedTimeService*' -or
            $identity.CommandLine -notlike '*from gs68_signed_time_fixture import TestOnlySignedTimeFixture*') {
            Stop-WithError 'physical_session_signed_time_identity_mismatch'
        }
        "$($proc.Id):$($proc.StartTime.ToUniversalTime().Ticks)"
    }else{''}
    $client=New-Object Net.Sockets.TcpClient
    try {
        $connect=$client.BeginConnect($authority.wsl_address,8445,$null,$null)
        $ready=$connect.AsyncWaitHandle.WaitOne(1500)
        if($ready){$client.EndConnect($connect)}
    } finally { $client.Dispose() }
    return [pscustomobject]@{ authorized=$true;services=($ready -and $timeProcess -ne '');
        cleanupReady=((Get-FileHash $State.script -Algorithm SHA256).Hash -eq $State.scriptHash -and
            (Get-ScheduledTask -TaskName $State.expiryTask -ErrorAction Stop).State -ne 'Disabled' -and
            (Get-PhysicalTaskHash $State.expiryTask) -eq $State.expiryHash);
        administrator=$true;scope=$authority.scope_id;activation=$authority.activation;activityDeadline=$authority.activity_deadline;
        controller=$authority.controller_start;service="$($authority.service_pid):$($authority.service_start):$($authority.service_sha256)";
        timeProcess=$timeProcess;address=$wifi.IpInfo.IPAddress;prefix=$wifi.IpInfo.PrefixLength;wifi=$wifi.Profile.Name;profile=$profile;
        firewall=$firewall;routeOwned=$owned;conflict=$conflict;target=$authority.wsl_address;
        listening=($listeners.Count -eq 1 -and $rows.Count -eq 1 -and $rows[0].TargetAddress -eq $authority.wsl_address) }
}


function Repair-PhysicalSessionRoute($State, [string]$Previous) {
    & $PSCommandPath -Action Start -EndpointKind PhysicalHubIngress -WslAddress $State.target -PreviousWslAddress $Previous -SessionRestricted
    if ($LASTEXITCODE -ne 0) { throw 'physical_session_repair_failed' }
}

function Continue-PhysicalDevelopmentLease($State) {
    # Operator-only, activity-validated close-before-open handoff. SYSTEM expiry
    # never renews. No task or privilege survives the individual lease closure.
    $next=Get-PhysicalAuthority $State.approval $State.pid $State.directory $State.authorityHelperSha256 `
        $State.networkWindow $State.networkApprovalSha256 $State.networkLeaseId -IssueNext
    Close-PhysicalSession $State
    & $State.script -Action SessionStart -EndpointKind PhysicalHubIngress -ApprovalRef $State.approval `
        -ControllerPid $State.pid -ServiceDirectory $State.directory -AuthorityHelperSha256 $State.authorityHelperSha256 `
        -NetworkWindow DEV -NetworkApprovalSha256 $State.networkApprovalSha256 -NetworkLeaseId $next.lease_id -SessionSeconds 3600
    if ($LASTEXITCODE -ne 0) { throw 'development_network_handoff_failed' }
}

function Invoke-PhysicalSessionTick($State) {
    if ($State.closed -or [DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($State.deadline)) {
        Close-PhysicalSession $State
        return [pscustomobject]@{Decision='CLOSE';ExitCode=0}
    }
    try {
        $observation=Get-PhysicalObservation $State
        $decision=Get-PhysicalSessionDecision $State $observation ([DateTimeOffset]::UtcNow)
        $State | Add-Member -NotePropertyName lastDecision -NotePropertyValue $decision -Force
        if ($decision -eq 'CLOSE') {
            Close-PhysicalSession $State
            return [pscustomobject]@{Decision='CLOSE';ExitCode=2}
        }
        if ($State.networkWindow -eq 'DEV') {
            $idleEnd=[DateTimeOffset]::Parse($observation.activityDeadline)
            $leaseEnd=[DateTimeOffset]::Parse($State.deadline)
            if($idleEnd -gt $leaseEnd){$idleEnd=$leaseEnd}
            if($idleEnd -gt [DateTimeOffset]::Parse($State.cleanupDeadline)) {
                $State.cleanupDeadline=$idleEnd.ToString('o')
                Set-PhysicalExpiryTask $State -Update
                Save-PhysicalSession $State
            }
        }
        if ($decision -eq 'REPAIR') {
            $previous=$State.target
            $State.targets=@(@($State.targets)+$observation.target|Select-Object -Unique)
            $State.target=$observation.target
            Save-PhysicalSession $State
            Repair-PhysicalSessionRoute $State $previous
        }
        if ($State.networkWindow -eq 'DEV' -and $State.allowHandoff -and
            (($State.PSObject.Properties['standingAuthority'] -and $State.standingAuthority -eq $true) -or
             [DateTimeOffset]::Parse($State.outerDeadline) -gt [DateTimeOffset]::Parse($State.deadline)) -and
            ([DateTimeOffset]::Parse($State.deadline)-[DateTimeOffset]::UtcNow).TotalSeconds -le 60) {
            Continue-PhysicalDevelopmentLease $State
            return [pscustomobject]@{Decision='HANDOFF';ExitCode=0}
        }
        Save-PhysicalSession $State
        return [pscustomobject]@{Decision=$decision;ExitCode=0;Deadline=$State.deadline}
    } catch { Close-PhysicalSession $State;throw }
}

if ($Action -like 'Session*') {
    if ($EndpointKind -ne 'PhysicalHubIngress') { Stop-WithError 'physical_session_endpoint_required' }
    Assert-Administrator
    if ($Action -eq 'SessionStart') {
        if ($SessionFile) { Stop-WithError 'physical_session_file_generated_only' }
        $authority=Get-PhysicalAuthority $ApprovalRef $ControllerPid $ServiceDirectory $AuthorityHelperSha256 $NetworkWindow $NetworkApprovalSha256 $NetworkLeaseId
        $base='C:\ProgramData\GharSajag\PhysicalIngress'
        foreach($folder in @('C:\ProgramData\GharSajag',$base)) {
        if (-not (Test-Path $folder)) {
            New-Item -ItemType Directory -Path $folder | Out-Null
            $acl=New-Object Security.AccessControl.DirectorySecurity
            $acl.SetAccessRuleProtection($true,$false)
            $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
            foreach($sid in @('S-1-5-18','S-1-5-32-544')) {
                $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
                    [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
            }
            Set-Acl -LiteralPath $folder -AclObject $acl
        }
        $folderItem=Get-Item -LiteralPath $folder
        $folderAcl=Get-Acl -LiteralPath $folder
        if ($folderItem.Attributes -band [IO.FileAttributes]::ReparsePoint -or
            $folderAcl.Owner -notin @('BUILTIN\Administrators','NT AUTHORITY\SYSTEM') -or
            @($folderAcl.Access|Where-Object {
                $_.AccessControlType -ne 'Allow' -or
                $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')
            }).Count -gt 0) { Stop-WithError 'physical_session_parent_acl_invalid' }
        }
        $baseItem=Get-Item -LiteralPath $base
        $baseAcl=Get-Acl -LiteralPath $base
        if ($baseItem.Attributes -band [IO.FileAttributes]::ReparsePoint -or
            $baseAcl.Owner -notin @('BUILTIN\Administrators','NT AUTHORITY\SYSTEM') -or
            @($baseAcl.Access|Where-Object {
                $_.AccessControlType -ne 'Allow' -or
                $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')
            }).Count -gt 0) { Stop-WithError 'physical_session_directory_acl_invalid' }
        # Validate the protected base before placing executable/state files in it.
        $id=[Guid]::NewGuid().ToString('N');$SessionFile=Join-Path $base ($id+'.json')
        $now=[DateTimeOffset]::UtcNow
        $prior=@(Get-ChildItem $base -Filter '*.json' | ForEach-Object {
            Assert-PhysicalSessionFile $_.FullName
            Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        })
        Assert-PhysicalWindowOrder $prior $NetworkApprovalSha256 $NetworkWindow
        $window=Get-PhysicalSessionWindow $prior $authority.scope_id $authority.activation $now $SessionSeconds `
            $authority.lease_started $authority.lease_deadline
        $cleanupDeadline=$window.deadline
        if($NetworkWindow -eq 'DEV' -and [DateTimeOffset]::Parse($authority.activity_deadline) -lt [DateTimeOffset]::Parse($cleanupDeadline)) {
            $cleanupDeadline=$authority.activity_deadline
        }
        $state=[pscustomobject]@{approval=$ApprovalRef;pid=$ControllerPid;directory=$ServiceDirectory;authorityHelperSha256=$AuthorityHelperSha256;
            networkWindow=$NetworkWindow;networkApprovalSha256=$NetworkApprovalSha256;
            networkLeaseId=$NetworkLeaseId;standingAuthority=($authority.PSObject.Properties['standing_authority'] -and $authority.standing_authority -eq $true);outerDeadline=$authority.outer_deadline;cleanupDeadline=$cleanupDeadline;allowHandoff=($NetworkWindow -eq 'DEV' -and $SessionSeconds -eq 3600);
            hardwareScope=$authority.hardware_scope;hardwareActivation=$authority.hardware_activation;
            scope=$authority.scope_id;activation=$authority.activation;controller=$authority.controller_start;
            service="$($authority.service_pid):$($authority.service_start):$($authority.service_sha256)";timeProcess='';
            started=$window.started;deadline=$window.deadline;
            target=$authority.wsl_address;targets=@($authority.wsl_address);closed=$false;exposureOwned=$false;expiryHash='';
            ownerSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;
            tickTask="GharSajag-PhysicalIngress-$id-Tick";expiryTask="GharSajag-PhysicalIngress-$id-Expiry";
            script=(Join-Path $base ($id+'.ps1'));scriptHash=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash}
        Save-PhysicalSession $state
        try {
        Assert-PhysicalSessionFile $SessionFile
        if (@(Get-ChildItem $base -Filter '*.json' | Where-Object {
            $_.FullName -ne $SessionFile -and -not ((Get-Content $_.FullName -Raw|ConvertFrom-Json).closed)
        }).Count -gt 0) { Stop-WithError 'physical_session_already_exists' }
        Copy-Item -LiteralPath $PSCommandPath -Destination $state.script
        $scriptAcl=Get-Acl $state.script
        $scriptAcl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
        Set-Acl -LiteralPath $state.script -AclObject $scriptAcl
        if ((Get-FileHash $state.script -Algorithm SHA256).Hash -ne $state.scriptHash) {
            Stop-WithError 'physical_session_snapshot_changed'
        }
        Register-PhysicalSessionTasks $state
        $state.exposureOwned=$true;Save-PhysicalSession $state
        # No exposure before both independent cleanup and reconciliation exist.
        & $state.script -Action SessionTick -EndpointKind PhysicalHubIngress -SessionFile $SessionFile
        exit $LASTEXITCODE
        } catch { Close-PhysicalSession $state;throw }
    }
    Assert-PhysicalSessionFile $SessionFile
    $state=Get-Content -LiteralPath $SessionFile -Raw|ConvertFrom-Json
    if ((Get-FileHash $PSCommandPath -Algorithm SHA256).Hash -ne $state.scriptHash -or
        $PSCommandPath -ne $state.script) { Stop-WithError 'physical_session_script_identity_mismatch' }
    if ($Action -eq 'SessionTick' -and [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne $state.ownerSid) {
        Stop-WithError 'physical_session_owner_mismatch'
    }
    # Serialize cleanup and reconciliation, including an expiry racing a repair.
    $lock=[IO.File]::Open($SessionFile+'.lock','OpenOrCreate','ReadWrite','None')
    try {
        $state=Get-Content -LiteralPath $SessionFile -Raw|ConvertFrom-Json
        if ($Action -eq 'SessionClose') { Close-PhysicalSession $state;exit 0 }
        $result=Invoke-PhysicalSessionTick $state
        $result | ConvertTo-Json -Compress
        exit $result.ExitCode
    } finally { $lock.Dispose() }
    exit 0
}

if ($Action -eq "UnregisterWatch") {
    Assert-Administrator
    Unregister-ScheduledTask -TaskName $WatchTaskName -Confirm:$false -ErrorAction SilentlyContinue
    [pscustomobject]@{ Action = $Action; Task = $WatchTaskName; Removed = $true } | ConvertTo-Json -Compress
    exit 0
}

if ($Action -eq "RegisterWatch") {
    Assert-Administrator
    if (-not (Test-LinuxScriptPath $LinuxScriptPath)) { Stop-WithError "canonical_wsl_script_path_required" }
    # A persistent watcher is allowed to mutate forwarding only while Windows
    # classifies the active Wi-Fi as owner-trusted. Check before registering so
    # a failed first run cannot leave a task behind on Public/Unknown Wi-Fi.
    $registrationWifi = Get-ActiveWifiState $false
    if (-not (Test-TrustedWifiProfile $registrationWifi.Profile.NetworkCategory) -or
        -not (Is-Rfc1918 $registrationWifi.IpInfo.IPAddress) -or
        $registrationWifi.IpInfo.PrefixLength -lt 16 -or
        $registrationWifi.IpInfo.PrefixLength -gt 29) {
        Stop-WithError "watch_registration_requires_trusted_private_or_domain_rfc1918_wifi"
    }
    $powershell = Join-Path $PSHOME "powershell.exe"
    $taskArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Action Watch -LinuxScriptPath `"$LinuxScriptPath`""
    $escapedPowerShell = [System.Security.SecurityElement]::Escape($powershell)
    $escapedArguments = [System.Security.SecurityElement]::Escape($taskArguments)
    $userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $eventPath = "Microsoft-Windows-NetworkProfile/Operational"
    $watchStartBoundary = [DateTime]::Now.AddMinutes(1).ToString("s")
    $taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
    <EventTrigger><Enabled>true</Enabled><Subscription><![CDATA[<QueryList><Query Id="0" Path="$eventPath"><Select Path="$eventPath">*[System[(EventID=10000)]]</Select></Query></QueryList>]]></Subscription></EventTrigger>
    <CalendarTrigger>
      <Enabled>true</Enabled><StartBoundary>$watchStartBoundary</StartBoundary>
      <Repetition><Interval>PT1M</Interval><Duration>P1D</Duration><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>$userSid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT3M</ExecutionTimeLimit><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>$escapedPowerShell</Command><Arguments>$escapedArguments</Arguments></Exec></Actions>
</Task>
"@
    Register-ScheduledTask -TaskName $WatchTaskName -Xml $taskXml -Force -ErrorAction Stop | Out-Null
    [pscustomobject]@{ Action = $Action; Task = $WatchTaskName; Triggers = "logon,Wi-Fi profile connected,daily WSL address reconciliation every minute"; LinuxScriptPath = $LinuxScriptPath } | ConvertTo-Json -Compress
    & $PSCommandPath -Action Watch -LinuxScriptPath $LinuxScriptPath
    exit $LASTEXITCODE
}

# Rollback must remain available even when the laptop has no active Wi-Fi
# profile. Remove only mappings to a recorded/current WSL NAT target and the
# uniquely named GS-179 rule after verifying its shape.
if ($Action -eq "Stop") {
    Assert-Administrator
    $knownTargets = @($WslAddress, $PreviousWslAddress) | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    }
    $ownedMaps = @(Get-PortProxyRows | Where-Object {
        $_.ListenPort -eq $ListenPort -and $_.TargetPort -eq $TargetPort -and
        $_.TargetAddress -in $knownTargets
    })
    foreach ($owned in $ownedMaps) {
        & netsh.exe interface portproxy delete v4tov4 listenaddress=$($owned.ListenAddress) listenport=$($owned.ListenPort) | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_delete_failed" }
    }
    $existingRule = Get-ExactFirewallRule
    if ($null -ne $existingRule) { Remove-NetFirewallRule -Name $RuleName }
    [pscustomobject]@{ Action = "Stop"; PortProxyRemoved = ($ownedMaps.Count -gt 0); `
        FirewallRuleRemoved = ($null -ne $existingRule); KnownWslTargets = $knownTargets.Count } |
        ConvertTo-Json -Compress
    exit 0
}

$wifiState = Get-ActiveWifiState ($Action -eq "Watch")
$adapter = $wifiState.Adapter
$profile = $wifiState.Profile
$ipInfo = $wifiState.IpInfo
$actualAddress = $ipInfo.IPAddress
$wifiPrivate = Is-Rfc1918 $actualAddress
$scope = Get-Ipv4Network $actualAddress $ipInfo.PrefixLength
$networkCategory = Get-NetworkCategoryName $profile.NetworkCategory
$firewallProfile = if ($networkCategory -eq "DomainAuthenticated") { "Domain" } else { $networkCategory }

if ($Action -eq "Audit") {
    $firewallReadable = $false
    $firewallExists = $null
    $firewallReadStatus = "QUERY_FAILED"
    try {
        $firewall = Get-NetFirewallRule -Name $RuleName -ErrorAction Stop
        $firewallReadable = $true
        $firewallExists = ($null -ne $firewall)
        $firewallReadStatus = if ($firewallExists) { "READABLE" } else { "ABSENT" }
    } catch {
        if ($_.Exception.Message -match 'Access is denied|Unauthorized|permission') {
            $firewallReadStatus = "BLOCKED_ADMIN_READ_PERMISSION"
        }
    }
    $listenerCount = $null
    $listenerReadStatus = "QUERY_FAILED"
    try {
        $listenerCount = @(Get-NetTCPConnection -State Listen -LocalAddress $actualAddress `
            -LocalPort $ListenPort -ErrorAction Stop).Count
        $listenerReadStatus = "READABLE"
    } catch {
        if ($_.Exception.Message -match 'Access is denied|Unauthorized|permission') {
            $listenerReadStatus = "BLOCKED_ADMIN_READ_PERMISSION"
        }
    }
    if ($listenerReadStatus -ne "READABLE") {
        $netstatListenerCount = Get-NetstatListenerCount $actualAddress $ListenPort
        if ($null -ne $netstatListenerCount) {
            $listenerCount = $netstatListenerCount
            $listenerReadStatus = "READABLE_NETSTAT"
        }
    }
    [pscustomobject]@{
        Action = $Action
        EndpointKind = $EndpointKind
        ListenPort = $ListenPort
        TargetPort = $TargetPort
        WifiName = $profile.Name
        NetworkCategory = $networkCategory
        WifiAddress = $actualAddress
        WifiPrefixLength = $ipInfo.PrefixLength
        ScopedRemoteSubnet = $scope
        WslAddress = $WslAddress
        PortProxyRows = (Get-PortProxyRows | ConvertTo-Json -Compress)
        FirewallRuleReadStatus = $firewallReadStatus
        FirewallRuleExists = $firewallExists
        ListenerReadStatus = $listenerReadStatus
        ListenerCount = $listenerCount
        Port443ListenerReadStatus = $listenerReadStatus
        Port443Listeners = $listenerCount
    } | ConvertTo-Json -Compress
    exit 0
}

# Only Start, Stop, and Watch can mutate Windows state. Audit performs read-only
# adapter, route, firewall and socket queries and is available without an
# administrative token. Never weaken the mutation gate below.
if ($Action -in @("Start", "Stop", "Watch")) { Assert-Administrator }

if ($Action -in @("Start", "Watch") -and -not (Test-TrustedWifiProfile $networkCategory)) {
    Stop-WithError "active_wifi_must_be_owner_trusted_private_or_domain_authenticated"
}

if (-not $wifiPrivate -or $networkCategory -eq "Unknown" -or $ipInfo.PrefixLength -lt 16 -or
    $ipInfo.PrefixLength -gt 29) {
    Stop-WithError "active_wifi_must_have_a_bounded_rfc1918_subnet_and_known_windows_profile"
}

$wasWatch = $Action -eq "Watch"
if ($wasWatch) {
    if (-not (Test-LinuxScriptPath $LinuxScriptPath)) { Stop-WithError "canonical_wsl_script_path_required" }
    $wslExe = Join-Path $env:WINDIR "System32\wsl.exe"
    if (-not (Test-Path $wslExe)) { Stop-WithError "wsl_executable_unavailable" }
    $refresh = & $wslExe --exec bash -lc "'$LinuxScriptPath' network-refresh-config" 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-WithError "wsl_network_configuration_refresh_failed" }
    $ipOutput = (& $wslExe --exec ip -4 -o addr show dev eth0 2>&1) -join "`n"
    $wslMatch = [regex]::Match($ipOutput, '\binet\s+(?<address>172\.(?:1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3})/')
    if (-not $wslMatch.Success) { Stop-WithError "current_wsl_nat_ipv4_unavailable" }
    $PreviousWslAddress = ((& $wslExe --exec bash -lc "cat ~/.local/state/ghar-sajag/gs179-laptop/windows-wsl-target 2>/dev/null || true") -join "").Trim()
    $WslAddress = $wslMatch.Groups["address"].Value
    $Action = "Start"
}

# Watch discovers the current WSL address after entering this script. Always
# validate the final address value (including that newly discovered value)
# before Start can mutate Windows forwarding or firewall state.
$wslPrivate = Is-Rfc1918 $WslAddress

$existingRule = Get-ExactFirewallRule
$mapRows = @(Get-PortProxyRows | Where-Object {
    $_.ListenAddress -eq $actualAddress -and $_.ListenPort -eq $ListenPort
})
if ($Action -eq "Start") {
    if (-not $wslPrivate -or $WslAddress -notmatch '^172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3}$') {
        Stop-WithError "current_wsl_nat_ipv4_required"
    }
    if ($SessionRestricted) {
        if ($EndpointKind -ne 'PhysicalHubIngress' -or $actualAddress -ne '192.168.1.6' -or
            $profile.Name -ne 'Airtel_Agrim' -or $ipInfo.PrefixLength -ne 24 -or $null -eq $existingRule) {
            Stop-WithError 'physical_session_network_scope_mismatch'
        }
        $addressFilter=$existingRule | Get-NetFirewallAddressFilter
        $helper=Get-CimInstance Win32_Service -Filter "Name='iphlpsvc'"
        if (@(Get-NetTCPConnection -State Listen -LocalPort 8445 -ErrorAction SilentlyContinue | Where-Object {
            $_.LocalAddress -ne '192.168.1.6' -or $_.OwningProcess -notin @(4,$helper.ProcessId)
        }).Count -gt 0) { Stop-WithError 'physical_session_port_conflict' }
        if ((@($addressFilter.LocalAddress) -join ',') -ne '192.168.1.6' -or
            -not (Test-EquivalentIpv4Scope $addressFilter.RemoteAddress '192.168.1.0/24') -or
            (@($existingRule.Profile) -join ',') -ne $firewallProfile -or
            $existingRule.EdgeTraversalPolicy -ne 'Block' -or
            @(Get-PortProxyRows | Where-Object { $_.ListenPort -eq 8445 -and $_.ListenAddress -ne '192.168.1.6' }).Count -gt 0) {
            Stop-WithError 'physical_session_firewall_or_mapping_mismatch'
        }
    }
    $occupied = @(Get-NetTCPConnection -State Listen -LocalAddress $actualAddress -LocalPort $ListenPort -ErrorAction SilentlyContinue)
    if ($occupied.Count -gt 0 -and $mapRows.Count -eq 0) { Stop-WithError "wifi_https_port_already_owned_by_another_process" }
    if ($mapRows.Count -gt 1) { Stop-WithError "ambiguous_existing_portproxy_entries" }

    $createdFirewall = $false
    $oldFirewallAddress = $null
    $oldFirewallProfile = $null
    if ($null -eq $existingRule) {
        New-NetFirewallRule -Name $RuleName -DisplayName $RuleDisplayName `
            -Description $RuleDescription -Direction Inbound -Action Allow -Enabled True `
            -Protocol TCP -LocalAddress $actualAddress -LocalPort $ListenPort `
            -RemoteAddress $scope -Profile $firewallProfile -InterfaceAlias "Wi-Fi" -EdgeTraversalPolicy Block | Out-Null
        $createdFirewall = $true
    } else {
        $currentFirewallAddress = $existingRule | Get-NetFirewallAddressFilter
        $needsFirewallScopeUpdate =
            ((@($currentFirewallAddress.LocalAddress) -join ",") -ne $actualAddress) -or
            (-not (Test-EquivalentIpv4Scope $currentFirewallAddress.RemoteAddress $scope)) -or
            ((@($existingRule.Profile) -join ",") -ne $firewallProfile)
        if ($needsFirewallScopeUpdate) {
            $oldFirewallAddress = $currentFirewallAddress
            $oldFirewallProfile = $existingRule.Profile
            # The named GS-179 rule is preserved and narrowed to the current
            # Wi-Fi address/subnet only when its stored scope actually differs.
            $currentFirewallAddress |
                Set-NetFirewallAddressFilter -LocalAddress $actualAddress -RemoteAddress $scope | Out-Null
            Set-NetFirewallRule -Name $RuleName -Profile $firewallProfile | Out-Null
        }
    }
    $attemptedPortProxy = $false
    $originalMappingRemoved = $false
    try {
        if ($mapRows.Count -eq 0) {
            $attemptedPortProxy = $true
            & netsh.exe interface portproxy add v4tov4 listenaddress=$actualAddress listenport=$ListenPort connectaddress=$WslAddress connectport=$TargetPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_add_failed" }
        } elseif ($mapRows[0].TargetAddress -ne $WslAddress -or $mapRows[0].TargetPort -ne $TargetPort) {
            $knownPrevious = -not [string]::IsNullOrWhiteSpace($PreviousWslAddress) -and
                $mapRows[0].TargetAddress -eq $PreviousWslAddress -and
                $mapRows[0].TargetPort -eq $TargetPort
            if (-not $knownPrevious) { Stop-WithError "existing_portproxy_target_is_not_the_recorded_gs179_target" }
            & netsh.exe interface portproxy delete v4tov4 listenaddress=$actualAddress listenport=$ListenPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "known_old_portproxy_delete_failed" }
            $originalMappingRemoved = $true
            $attemptedPortProxy = $true
            & netsh.exe interface portproxy add v4tov4 listenaddress=$actualAddress listenport=$ListenPort connectaddress=$WslAddress connectport=$TargetPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_retarget_failed" }
        } elseif ($occupied.Count -eq 0) {
            # An old row can outlive the Wi-Fi address it was created for.
            # Re-add the exact same row to make IP Helper bind the now-current
            # address; never report Start success for a dormant forwarding row.
            & netsh.exe interface portproxy delete v4tov4 listenaddress=$actualAddress listenport=$ListenPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "stale_portproxy_delete_failed" }
            $originalMappingRemoved = $true
            $attemptedPortProxy = $true
            & netsh.exe interface portproxy add v4tov4 listenaddress=$actualAddress listenport=$ListenPort connectaddress=$WslAddress connectport=$TargetPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "stale_portproxy_refresh_failed" }
        }
        if (-not (Wait-PortProxyListener $actualAddress $ListenPort)) {
            Stop-WithError "portproxy_listener_not_active"
        }
    } catch {
        if ($attemptedPortProxy) {
            $partial = @(Get-PortProxyRows | Where-Object {
                $_.ListenAddress -eq $actualAddress -and $_.ListenPort -eq $ListenPort -and
                $_.TargetAddress -eq $WslAddress -and $_.TargetPort -eq $TargetPort
            })
            if ($partial.Count -eq 1) {
                & netsh.exe interface portproxy delete v4tov4 listenaddress=$actualAddress listenport=$ListenPort | Out-Null
            }
        }
        if ($originalMappingRemoved -and $mapRows.Count -eq 1) {
            & netsh.exe interface portproxy add v4tov4 `
                listenaddress=$($mapRows[0].ListenAddress) listenport=$($mapRows[0].ListenPort) `
                connectaddress=$($mapRows[0].TargetAddress) connectport=$($mapRows[0].TargetPort) | Out-Null
        }
        if ($createdFirewall) { Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue }
        elseif ($null -ne $oldFirewallAddress) {
            Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue |
                Get-NetFirewallAddressFilter |
                Set-NetFirewallAddressFilter -LocalAddress $oldFirewallAddress.LocalAddress `
                    -RemoteAddress $oldFirewallAddress.RemoteAddress | Out-Null
            Set-NetFirewallRule -Name $RuleName -Profile $oldFirewallProfile | Out-Null
        }
        throw
    }
    # Remove only stale rows that still target this known GS-179 listener and
    # the recorded prior/current WSL address. Unrecognized portproxy entries stay untouched.
    $knownTargets = @($WslAddress, $PreviousWslAddress) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $staleMaps = @(Get-PortProxyRows | Where-Object {
        $_.ListenPort -eq $ListenPort -and $_.ListenAddress -ne $actualAddress -and
        $_.TargetPort -eq $TargetPort -and $_.TargetAddress -in $knownTargets
    })
    foreach ($stale in $staleMaps) {
        & netsh.exe interface portproxy delete v4tov4 listenaddress=$($stale.ListenAddress) listenport=$($stale.ListenPort) | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-WithError "stale_owned_portproxy_cleanup_failed" }
    }
    [pscustomobject]@{ Action = "Start"; WifiName = $profile.Name; WifiAddress = $actualAddress; `
        NetworkCategory = $networkCategory; RemoteSubnet = $scope; ListenPort = $ListenPort; `
        TargetAddress = $WslAddress; TargetPort = $TargetPort; StaleOwnedMappingsRemoved = $staleMaps.Count; `
        FirewallRule = $RuleName } | ConvertTo-Json -Compress
    if ($wasWatch) {
        $record = & $wslExe --exec bash -lc "'$LinuxScriptPath' record-proxy-target '$WslAddress'" 2>&1
        if ($LASTEXITCODE -ne 0) { Stop-WithError "wsl_proxy_target_record_failed" }
        $advertise = & $wslExe --exec bash -lc "'$LinuxScriptPath' start-mdns-advertiser" 2>&1
        if ($LASTEXITCODE -ne 0) { Stop-WithError "wsl_mdns_advertiser_start_failed" }
    }
    exit 0
}
