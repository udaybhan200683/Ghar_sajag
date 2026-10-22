param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Audit", "Start", "Stop", "Watch", "RegisterWatch", "UnregisterWatch")]
    [string]$Action,
    [string]$WslAddress = "",
    [string]$PreviousWslAddress = "",
    [string]$LinuxScriptPath = ""
)

$ErrorActionPreference = "Stop"
$RuleName = "GS179-Local-LAN-HTTPS"
$RuleDescription = "GS-179 TEST_ONLY caregiver HTTPS, limited to the active owner Wi-Fi subnet."
$WatchTaskName = "Ghar Sajag GS-179 Trusted Wi-Fi Reconnect"
$ListenPort = 443
$TargetPort = 8444

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
    $taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
    <EventTrigger><Enabled>true</Enabled><Subscription><![CDATA[<QueryList><Query Id="0" Path="$eventPath"><Select Path="$eventPath">*[System[(EventID=10000)]]</Select></Query></QueryList>]]></Subscription></EventTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>$userSid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT3M</ExecutionTimeLimit><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>$escapedPowerShell</Command><Arguments>$escapedArguments</Arguments></Exec></Actions>
</Task>
"@
    Register-ScheduledTask -TaskName $WatchTaskName -Xml $taskXml -Force -ErrorAction Stop | Out-Null
    [pscustomobject]@{ Action = $Action; Task = $WatchTaskName; Triggers = "logon,Wi-Fi profile connected"; LinuxScriptPath = $LinuxScriptPath } | ConvertTo-Json -Compress
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
        & netsh.exe interface portproxy delete v4tov4 listenaddress=$owned.ListenAddress listenport=$owned.ListenPort | Out-Null
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
$wslPrivate = Is-Rfc1918 $WslAddress
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
    [pscustomobject]@{
        Action = $Action
        WifiName = $profile.Name
        NetworkCategory = $networkCategory
        WifiAddress = $actualAddress
        WifiPrefixLength = $ipInfo.PrefixLength
        ScopedRemoteSubnet = $scope
        WslAddress = $WslAddress
        PortProxyRows = (Get-PortProxyRows | ConvertTo-Json -Compress)
        FirewallRuleReadStatus = $firewallReadStatus
        FirewallRuleExists = $firewallExists
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

$existingRule = Get-ExactFirewallRule
$mapRows = @(Get-PortProxyRows | Where-Object {
    $_.ListenAddress -eq $actualAddress -and $_.ListenPort -eq $ListenPort
})
if ($Action -eq "Start") {
    if (-not $wslPrivate -or $WslAddress -notmatch '^172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3}$') {
        Stop-WithError "current_wsl_nat_ipv4_required"
    }
    $occupied = @(Get-NetTCPConnection -State Listen -LocalAddress $actualAddress -LocalPort $ListenPort -ErrorAction SilentlyContinue)
    if ($occupied.Count -gt 0 -and $mapRows.Count -eq 0) { Stop-WithError "wifi_https_port_already_owned_by_another_process" }
    if ($mapRows.Count -gt 1) { Stop-WithError "ambiguous_existing_portproxy_entries" }

    $createdFirewall = $false
    $oldFirewallAddress = $null
    $oldFirewallProfile = $null
    if ($null -eq $existingRule) {
        New-NetFirewallRule -Name $RuleName -DisplayName "Ghar Sajag GS-179 Local Validation HTTPS" `
            -Description $RuleDescription -Direction Inbound -Action Allow -Enabled True `
            -Protocol TCP -LocalAddress $actualAddress -LocalPort $ListenPort `
            -RemoteAddress $scope -Profile $firewallProfile -InterfaceAlias "Wi-Fi" -EdgeTraversalPolicy Block | Out-Null
        $createdFirewall = $true
    } else {
        $oldFirewallAddress = $existingRule | Get-NetFirewallAddressFilter
        $oldFirewallProfile = $existingRule.Profile
        # The named GS-179 rule is preserved and narrowed to the currently active
        # Wi-Fi address/subnet. It is never broadened to Any local/remote address.
        $existingRule | Get-NetFirewallAddressFilter |
            Set-NetFirewallAddressFilter -LocalAddress $actualAddress -RemoteAddress $scope | Out-Null
        Set-NetFirewallRule -Name $RuleName -Profile $firewallProfile | Out-Null
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
                listenaddress=$mapRows[0].ListenAddress listenport=$mapRows[0].ListenPort `
                connectaddress=$mapRows[0].TargetAddress connectport=$mapRows[0].TargetPort | Out-Null
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
        & netsh.exe interface portproxy delete v4tov4 listenaddress=$stale.ListenAddress listenport=$stale.ListenPort | Out-Null
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
