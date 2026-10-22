param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Start", "Stop", "Worker", "Validate")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$ServiceType = "_https._tcp"
$ServicePort = 443
$WorkerMutexName = "Local\GharSajagGS179MdnsWorker"
$StopEventName = "Local\GharSajagGS179MdnsStop"

if (-not ("GharSajag.Gs179DnsSd" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Net;
using System.Runtime.InteropServices;
using System.Threading;

namespace GharSajag {
    public static class Gs179DnsSd {
        private const uint DnsRequestPending = 9506;
        private static readonly DnsRegisterComplete Completion = OnComplete;

        [UnmanagedFunctionPointer(CallingConvention.Winapi)]
        private delegate void DnsRegisterComplete(uint status, IntPtr context, IntPtr instance);

        [StructLayout(LayoutKind.Sequential)]
        private struct DnsServiceRegisterRequest {
            public uint Version;
            public uint InterfaceIndex;
            public IntPtr ServiceInstance;
            public DnsRegisterComplete CompletionCallback;
            public IntPtr QueryContext;
            public IntPtr Credentials;
            [MarshalAs(UnmanagedType.Bool)] public bool UnicastEnabled;
        }

        private sealed class CallbackState {
            public readonly ManualResetEvent Completed = new ManualResetEvent(false);
            public uint Status;
        }

        public sealed class Registration : IDisposable {
            private readonly CallbackState callbackState;
            private GCHandle callbackHandle;
            private DnsServiceRegisterRequest request;
            private bool disposed;

            internal Registration(IntPtr instance, uint interfaceIndex) {
                callbackState = new CallbackState();
                callbackHandle = GCHandle.Alloc(callbackState);
                request = new DnsServiceRegisterRequest {
                    Version = 1,
                    InterfaceIndex = interfaceIndex,
                    ServiceInstance = instance,
                    CompletionCallback = Completion,
                    QueryContext = GCHandle.ToIntPtr(callbackHandle),
                    UnicastEnabled = false
                };
                uint result = DnsServiceRegister(ref request, IntPtr.Zero);
                if (result != DnsRequestPending) {
                    Free();
                    throw new InvalidOperationException("DnsServiceRegister returned " + result);
                }
                if (!callbackState.Completed.WaitOne(5000)) {
                    // The pending native operation still owns the request and
                    // callback context. The worker must exit; process lifetime
                    // then withdraws the advertisement without freeing live state.
                    throw new InvalidOperationException("GS179_MDNS_FATAL_registration_timeout");
                }
                if (callbackState.Status != 0) {
                    Free();
                    throw new InvalidOperationException("mDNS service registration did not complete");
                }
            }

            public void Dispose() {
                if (disposed) return;
                disposed = true;
                callbackState.Completed.Reset();
                uint result = DnsServiceDeRegister(ref request, IntPtr.Zero);
                if (result != DnsRequestPending) {
                    throw new InvalidOperationException("GS179_MDNS_FATAL_deregistration_failed_" + result);
                }
                if (!callbackState.Completed.WaitOne(5000)) {
                    // Do not free a request/context still owned by the native API.
                    // The worker exits and Windows withdraws it with process exit.
                    throw new InvalidOperationException("GS179_MDNS_FATAL_deregistration_timeout");
                }
                Free();
            }

            private void Free() {
                if (request.ServiceInstance != IntPtr.Zero) {
                    DnsServiceFreeInstance(request.ServiceInstance);
                    request.ServiceInstance = IntPtr.Zero;
                }
                if (callbackHandle.IsAllocated) callbackHandle.Free();
                callbackState.Completed.Dispose();
            }
        }

        [DllImport("dnsapi.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        private static extern IntPtr DnsServiceConstructInstance(
            [MarshalAs(UnmanagedType.LPWStr)] string serviceName,
            [MarshalAs(UnmanagedType.LPWStr)] string hostName,
            ref uint ipv4Address,
            IntPtr ipv6Address,
            ushort port,
            ushort priority,
            ushort weight,
            uint propertyCount,
            [MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.LPWStr)] string[] keys,
            [MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.LPWStr)] string[] values);

        [DllImport("dnsapi.dll", ExactSpelling = true)]
        private static extern uint DnsServiceRegister(ref DnsServiceRegisterRequest request, IntPtr cancel);

        [DllImport("dnsapi.dll", ExactSpelling = true)]
        private static extern uint DnsServiceDeRegister(ref DnsServiceRegisterRequest request, IntPtr cancel);

        [DllImport("dnsapi.dll", ExactSpelling = true)]
        private static extern void DnsServiceFreeInstance(IntPtr instance);

        private static void OnComplete(uint status, IntPtr context, IntPtr instance) {
            if (instance != IntPtr.Zero) DnsServiceFreeInstance(instance);
            if (context == IntPtr.Zero) return;
            CallbackState state = (CallbackState)GCHandle.FromIntPtr(context).Target;
            lock (state) {
                state.Status = status;
                state.Completed.Set();
            }
        }

        public static Registration Register(string hostLabel, string address, uint interfaceIndex) {
            byte[] octets = IPAddress.Parse(address).GetAddressBytes();
            uint ipv4 = ((uint)octets[0] << 24) | ((uint)octets[1] << 16) |
                        ((uint)octets[2] << 8) | octets[3];
            string host = hostLabel + ".local";
            string instance = "GharSajag-GS179-" + hostLabel + "." + "_https._tcp.local";
            string[] keys = new string[] { "profile", "tls_host", "protocol" };
            string[] values = new string[] { "GS179_TEST_ONLY", host, "1" };
            IntPtr service = DnsServiceConstructInstance(instance, host, ref ipv4, IntPtr.Zero,
                443, 0, 0, (uint)keys.Length, keys, values);
            if (service == IntPtr.Zero) throw new InvalidOperationException("DnsServiceConstructInstance failed");
            return new Registration(service, interfaceIndex);
        }

        public static bool CanConstructTestOnlyAdvertisement(string hostLabel, string address) {
            byte[] octets = IPAddress.Parse(address).GetAddressBytes();
            uint ipv4 = ((uint)octets[0] << 24) | ((uint)octets[1] << 16) |
                        ((uint)octets[2] << 8) | octets[3];
            string host = hostLabel + ".local";
            string instance = "GharSajag-GS179-" + hostLabel + "." + "_https._tcp.local";
            string[] keys = new string[] { "profile", "tls_host", "protocol" };
            string[] values = new string[] { "GS179_TEST_ONLY", host, "1" };
            IntPtr service = DnsServiceConstructInstance(instance, host, ref ipv4, IntPtr.Zero,
                443, 0, 0, (uint)keys.Length, keys, values);
            if (service == IntPtr.Zero) return false;
            DnsServiceFreeInstance(service);
            return true;
        }

        public static string ApiVersion { get { return "Windows DNS-SD mDNS API / TEST_ONLY"; } }
    }
}
"@
}

function Test-Rfc1918([string]$Address) {
    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed) -or
        $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    if ($parsed.ToString() -ne $Address) { return $false }
    $bytes = $parsed.GetAddressBytes()
    return ($bytes[0] -eq 10) -or
        ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
        ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
}

function Test-TrustedWifiProfile([object]$NetworkCategory) {
    return ([string]$NetworkCategory) -in @("Private", "DomainAuthenticated")
}

function Get-EligibleWifi {
    $adapter = Get-NetAdapter -Name "Wi-Fi" -ErrorAction SilentlyContinue
    $profile = Get-NetConnectionProfile -InterfaceAlias "Wi-Fi" -ErrorAction SilentlyContinue |
        Where-Object { $_.IPv4Connectivity -ne "Disconnected" } | Select-Object -First 1
    $ip = Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.AddressState -eq "Preferred" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -First 1
    if ($null -eq $adapter -or $adapter.Status -ne "Up" -or $null -eq $profile -or
        -not (Test-TrustedWifiProfile $profile.NetworkCategory) -or $null -eq $ip -or
        $ip.PrefixLength -lt 16 -or $ip.PrefixLength -gt 29 -or -not (Test-Rfc1918 $ip.IPAddress)) {
        return $null
    }
    $hostLabel = $env:COMPUTERNAME.ToLowerInvariant()
    if ($hostLabel -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$') { return $null }
    return [pscustomobject]@{ Address = $ip.IPAddress; InterfaceIndex = [uint32]$adapter.ifIndex; HostLabel = $hostLabel }
}

function Test-CurrentHttpsListener([string]$Address) {
    return @(Get-NetTCPConnection -State Listen -LocalAddress $Address -LocalPort 443 -ErrorAction SilentlyContinue).Count -gt 0
}

function Open-StopEvent([bool]$Create) {
    $created = $false
    return [System.Threading.EventWaitHandle]::new(
        $false, [System.Threading.EventResetMode]::ManualReset, $StopEventName, [ref]$created)
}

if ($Action -eq "Validate") {
    $validAddresses = @("10.1.2.3", "172.16.1.1", "172.31.255.1", "192.168.1.8")
    $invalidAddresses = @("8.8.8.8", "172.15.1.1", "172.32.1.1", "192.168.001.8", "127.0.0.1")
    if (@($validAddresses | Where-Object { -not (Test-Rfc1918 $_) }).Count -gt 0 -or
        @($invalidAddresses | Where-Object { Test-Rfc1918 $_ }).Count -gt 0) {
        throw "GS179_WINDOWS_MDNS_VALIDATE_FAIL rfc1918_policy"
    }
    $trustedProfiles = @("Private", "DomainAuthenticated")
    $untrustedProfiles = @("Public", "Unknown")
    if (@($trustedProfiles | Where-Object { -not (Test-TrustedWifiProfile $_) }).Count -gt 0 -or
        @($untrustedProfiles | Where-Object { Test-TrustedWifiProfile $_ }).Count -gt 0) {
        throw "GS179_WINDOWS_MDNS_VALIDATE_FAIL trusted_wifi_profile_policy"
    }
    if (-not [GharSajag.Gs179DnsSd]::CanConstructTestOnlyAdvertisement("desktop-3qqu64b", "192.168.1.8")) {
        throw "GS179_WINDOWS_MDNS_VALIDATE_FAIL service_record_construction"
    }
    [pscustomobject]@{ Action = $Action; Api = [GharSajag.Gs179DnsSd]::ApiVersion; PolicyCases = 13; ServiceRecordConstruction = "PASS"; SocketOrRegistrationOpened = $false } |
        ConvertTo-Json -Compress
    exit 0
}

if ($Action -eq "Stop") {
    $stop = Open-StopEvent $true
    try { $stop.Set() } finally { $stop.Dispose() }
    [pscustomobject]@{ Action = $Action; AdvertisementStopped = "REQUESTED"; PortProxyChanged = $false; FirewallChanged = $false } |
        ConvertTo-Json -Compress
    exit 0
}

if ($Action -eq "Start") {
    $stop = Open-StopEvent $true
    try { $stop.Reset() } finally { $stop.Dispose() }
    $powershell = Join-Path $PSHOME "powershell.exe"
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-Action", "Worker")
    Start-Process -FilePath $powershell -ArgumentList $arguments -WindowStyle Hidden | Out-Null
    [pscustomobject]@{ Action = $Action; AdvertisementWorker = "START_REQUESTED"; ServiceType = $ServiceType; Port = $ServicePort; PersistentPrivilegedTaskRegistered = $false } |
        ConvertTo-Json -Compress
    exit 0
}

$createdNew = $false
$mutex = [System.Threading.Mutex]::new($true, $WorkerMutexName, [ref]$createdNew)
if (-not $createdNew) { $mutex.Dispose(); exit 0 }
$stop = Open-StopEvent $true
$registration = $null
$registeredTuple = ""
try {
    while (-not $stop.WaitOne(0)) {
        $wifi = Get-EligibleWifi
        $tuple = ""
        if ($null -ne $wifi -and (Test-CurrentHttpsListener $wifi.Address)) {
            $tuple = "$($wifi.Address)|$($wifi.InterfaceIndex)|$($wifi.HostLabel)"
        }
        if ($tuple -ne $registeredTuple) {
            if ($null -ne $registration) {
                $registration.Dispose()
                $registration = $null
                $registeredTuple = ""
            }
            if ($tuple -ne "") {
                try {
                    $registration = [GharSajag.Gs179DnsSd]::Register(
                        $wifi.HostLabel, $wifi.Address, $wifi.InterfaceIndex)
                    $registeredTuple = $tuple
                } catch {
                    if ($_.Exception.ToString().Contains("GS179_MDNS_FATAL_")) { throw }
                    # Fail closed. The Android client separately requires valid TLS and readyz.
                    $registration = $null
                    $registeredTuple = ""
                }
            }
        }
        if ($stop.WaitOne(3000)) { break }
    }
} finally {
    if ($null -ne $registration) { $registration.Dispose() }
    $stop.Dispose()
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
