param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Audit", "Start", "Stop")]
    [string]$Action,
    [string]$WifiAddress = "",
    [string]$WslAddress = "",
    [string]$PreviousWslAddress = "",
    [string]$ExpectedWifiName = ""
)

$ErrorActionPreference = "Stop"
$RuleName = "GS179-Local-LAN-HTTPS"
$RuleDescription = "GS-179 TEST_ONLY caregiver HTTPS, limited to the active owner Wi-Fi subnet."
$ListenPort = 443
$TargetPort = 8444

function Stop-WithError([string]$Message) {
    throw ("GS179-WINDOWS-PROXY BLOCKED: " + $Message)
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

function Get-ExactFirewallRule([string]$ExpectedSubnet) {
    $rule = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule) { return $null }
    $port = $rule | Get-NetFirewallPortFilter
    $address = $rule | Get-NetFirewallAddressFilter
    $interface = $rule | Get-NetFirewallInterfaceFilter
    $local = @($address.LocalAddress) -join ","
    $remote = @($address.RemoteAddress) -join ","
    $parts = $ExpectedSubnet.Split("/")
    $expectedNetwork = [System.Net.IPAddress]::Parse($parts[0]).GetAddressBytes()
    $prefix = [int]$parts[1]
    $maskBytes = New-Object byte[] 4
    for ($index = 0; $index -lt 4; $index++) {
        $remaining = $prefix - ($index * 8)
        if ($remaining -ge 8) { $maskBytes[$index] = 255 }
        elseif ($remaining -le 0) { $maskBytes[$index] = 0 }
        else { $maskBytes[$index] = [byte]((255 -shl (8 - $remaining)) -band 255) }
    }
    $windowsSubnet = ([System.Net.IPAddress]::new($expectedNetwork)).ToString() + "/" +
        ([System.Net.IPAddress]::new($maskBytes)).ToString()
    if ($rule.Direction -ne "Inbound" -or $rule.Action -ne "Allow" -or
        $rule.Enabled -ne "True" -or $rule.Profile -ne "Public" -or
        $port.Protocol -ne "TCP" -or $port.LocalPort -ne "$ListenPort" -or
        $local -ne $WifiAddress -or $remote -notin @($ExpectedSubnet, $windowsSubnet) -or
        (@($interface.InterfaceAlias) -join ",") -ne "Wi-Fi" -or
        $rule.Description -ne $RuleDescription) {
        Stop-WithError "existing_firewall_rule_does_not_match_gs179_lan_scope"
    }
    return $rule
}

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithError "administrator_token_required_for_scoped_portproxy_and_firewall_rule"
}

$adapter = Get-NetAdapter -Name "Wi-Fi" -ErrorAction SilentlyContinue
if ($null -eq $adapter -or $adapter.Status -ne "Up") { Stop-WithError "wifi_adapter_not_up" }
$profile = Get-NetConnectionProfile -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
    Where-Object { $_.IPv4Connectivity -ne "Disconnected" } | Select-Object -First 1
if ($null -eq $profile) { Stop-WithError "active_wifi_profile_unavailable" }
$ipInfo = Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.AddressState -eq "Preferred" } | Select-Object -First 1
if ($null -eq $ipInfo) { Stop-WithError "active_wifi_ipv4_unavailable" }
$actualAddress = $ipInfo.IPAddress
$expectedNameMatches = [string]::IsNullOrWhiteSpace($ExpectedWifiName) -or
    $profile.Name -eq $ExpectedWifiName
$addressMatches = [string]::IsNullOrWhiteSpace($WifiAddress) -or $actualAddress -eq $WifiAddress
$wifiPrivate = Is-Rfc1918 $actualAddress
$wslPrivate = Is-Rfc1918 $WslAddress
$scope = Get-Ipv4Network $actualAddress $ipInfo.PrefixLength

if ($Action -eq "Audit") {
    [pscustomobject]@{
        Action = $Action
        WifiName = $profile.Name
        NetworkCategory = $profile.NetworkCategory
        WifiAddress = $actualAddress
        WifiPrefixLength = $ipInfo.PrefixLength
        ScopedRemoteSubnet = $scope
        WslAddress = $WslAddress
        PortProxyRows = (Get-PortProxyRows | ConvertTo-Json -Compress)
        FirewallRuleExists = ($null -ne (Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue))
        Port443Listeners = (@(Get-NetTCPConnection -State Listen -LocalAddress $actualAddress -LocalPort $ListenPort -ErrorAction SilentlyContinue).Count)
    } | ConvertTo-Json -Compress
    exit 0
}

if (-not $wifiPrivate -or -not $addressMatches -or -not $expectedNameMatches -or
    $profile.NetworkCategory -ne "Public" -or $ipInfo.PrefixLength -lt 16 -or
    $ipInfo.PrefixLength -gt 29) {
    Stop-WithError "wifi_identity_or_private_subnet_changed"
}

$existingRule = Get-ExactFirewallRule $scope
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
    if ($null -eq $existingRule) {
        New-NetFirewallRule -Name $RuleName -DisplayName "Ghar Sajag GS-179 Local Validation HTTPS" `
            -Description $RuleDescription -Direction Inbound -Action Allow -Enabled True `
            -Protocol TCP -LocalAddress $actualAddress -LocalPort $ListenPort `
            -RemoteAddress $scope -Profile Public -InterfaceAlias "Wi-Fi" -EdgeTraversalPolicy Block | Out-Null
        $createdFirewall = $true
    }
    $attemptedPortProxy = $false
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
            $attemptedPortProxy = $true
            & netsh.exe interface portproxy add v4tov4 listenaddress=$actualAddress listenport=$ListenPort connectaddress=$WslAddress connectport=$TargetPort | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_retarget_failed" }
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
        if ($createdFirewall) { Remove-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue }
        throw
    }
    [pscustomobject]@{ Action = "Start"; WifiName = $profile.Name; WifiAddress = $actualAddress; `
        NetworkCategory = $profile.NetworkCategory; RemoteSubnet = $scope; ListenPort = $ListenPort; `
        TargetAddress = $WslAddress; TargetPort = $TargetPort; FirewallRule = $RuleName } | ConvertTo-Json -Compress
    exit 0
}

if ($Action -eq "Stop") {
    if ($mapRows.Count -gt 0) {
        $targetIsKnown = $mapRows[0].TargetPort -eq $TargetPort -and
            ($mapRows[0].TargetAddress -eq $WslAddress -or
             (-not [string]::IsNullOrWhiteSpace($PreviousWslAddress) -and
              $mapRows[0].TargetAddress -eq $PreviousWslAddress))
        if (-not $targetIsKnown) { Stop-WithError "refusing_to_remove_unrecognized_portproxy_target" }
        & netsh.exe interface portproxy delete v4tov4 listenaddress=$actualAddress listenport=$ListenPort | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-WithError "portproxy_delete_failed" }
    }
    if ($null -ne $existingRule) { Remove-NetFirewallRule -Name $RuleName }
    [pscustomobject]@{ Action = "Stop"; PortProxyRemoved = ($mapRows.Count -gt 0); `
        FirewallRuleRemoved = ($null -ne $existingRule); WifiAddress = $actualAddress } | ConvertTo-Json -Compress
    exit 0
}
