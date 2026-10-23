package `in`.gharsajag.caregiver

import android.content.Context
import android.os.Build
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.net.Inet4Address
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.URL
import java.security.MessageDigest
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLPeerUnverifiedException
import org.json.JSONObject

/** Pure policy for locating the expected TEST_ONLY laptop. DNS-SD fields are hints only. */
internal object Gs179LanDiscoveryPolicy {
    const val SERVICE_TYPE = "_https._tcp."
    const val SERVICE_PROFILE = "GS179_TEST_ONLY"
    const val MAX_PROBE_ADDRESSES = 4
    const val MAX_PENDING_RESOLVES = 2
    private const val INSTANCE_PREFIX = "GharSajag-GS179-"

    fun expectedServiceName(expectedTlsHost: String): String? {
        val origin = BackendOrigin.parse("https://$expectedTlsHost", allowTestOnlyLanEndpoint = true)
            ?: return null
        if (!origin.host.endsWith(".local")) return null
        return INSTANCE_PREFIX + origin.host.removeSuffix(".local")
    }

    fun matchesService(
        serviceName: String?,
        serviceType: String?,
        port: Int,
        attributes: Map<String, String>,
        expectedTlsHost: String,
    ): Boolean = serviceMismatchReason(
        serviceName, serviceType, port, attributes, expectedTlsHost,
    ) == null

    fun serviceMismatchReason(
        serviceName: String?,
        serviceType: String?,
        port: Int,
        attributes: Map<String, String>,
        expectedTlsHost: String,
    ): String? {
        val expectedName = expectedServiceName(expectedTlsHost) ?: return "invalid_expected_tls_host"
        val normalizedType = serviceType?.trim()?.trimEnd('.')?.lowercase() ?: return "missing_service_type"
        val normalizedAttributes = attributes.mapKeys { it.key.lowercase() }
        if (!serviceName.equals(expectedName, ignoreCase = true)) return "service_name_mismatch"
        if (normalizedType != SERVICE_TYPE.trimEnd('.')) return "service_type_mismatch"
        if (port != 443) return "service_port_mismatch"
        if (normalizedAttributes["profile"] != SERVICE_PROFILE) return "profile_txt_mismatch"
        if (!normalizedAttributes["tls_host"].equals(expectedTlsHost, ignoreCase = true)) return "tls_host_txt_mismatch"
        if (normalizedAttributes["protocol"] != "1") return "protocol_txt_mismatch"
        return null
    }

    fun isPrivateIpv4(address: String?): Boolean {
        val parts = address?.split('.') ?: return false
        if (parts.size != 4) return false
        val octets = parts.map { part ->
            if (part.isEmpty() || (part.length > 1 && part.startsWith('0')) ||
                part.any { !it.isDigit() }) return false
            part.toIntOrNull()?.takeIf { it in 0..255 } ?: return false
        }
        return octets[0] == 10 ||
            (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 192 && octets[1] == 168)
    }

    fun canProbeAddress(address: String?, attemptedAddresses: Set<String>): Boolean =
        isPrivateIpv4(address) && address !in attemptedAddresses &&
            attemptedAddresses.size < MAX_PROBE_ADDRESSES

    fun privateIpv4Addresses(addresses: Collection<InetAddress>): List<String> =
        addresses.filterIsInstance<Inet4Address>()
            .map { it.hostAddress }
            .filter { isPrivateIpv4(it) }
            .distinct()

    fun certificateNamesExpectedHost(expectedTlsHost: String, dnsNames: Collection<String>): Boolean =
        dnsNames.any { it.trimEnd('.').equals(expectedTlsHost, ignoreCase = true) }

    fun serverKeyMatches(expectedPin: String?, observedPin: String): Boolean =
        expectedPin == null || MessageDigest.isEqual(
            expectedPin.lowercase().toByteArray(Charsets.US_ASCII),
            observedPin.lowercase().toByteArray(Charsets.US_ASCII),
        )

    fun shouldReloadForVerifiedEndpoint(
        currentOrigin: String?,
        candidateOrigin: String,
        wifiRouteChanged: Boolean,
    ): Boolean = currentOrigin != candidateOrigin || wifiRouteChanged
}

/** Foreground-only NSD discovery. A candidate is saved only after normal HTTPS verification. */
internal class Gs179LanServerDiscovery(
    context: Context,
    private val expectedTlsHost: String,
    private val onVerifiedEndpoint: (BackendOrigin) -> Unit,
) {
    private val appContext = context.applicationContext
    private val nsd = appContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifi = appContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val main = Handler(Looper.getMainLooper())
    private val lock = Any()
    private val resolving = mutableSetOf<String>()
    private val attemptedAddresses = mutableSetOf<String>()
    private var listener: NsdManager.DiscoveryListener? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var generation = 0
    private var active = false
    private var expectedServiceFound = false

    fun start() {
        synchronized(lock) {
            if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) return
            if (active) {
                diagnostic("DISCOVERY_START_SKIPPED reason=already_active")
                return
            }
            if (Gs179LanDiscoveryPolicy.expectedServiceName(expectedTlsHost) == null) {
                diagnostic("DISCOVERY_START_SKIPPED reason=invalid_expected_host")
                return
            }
            active = true
            generation += 1
            resolving.clear()
            attemptedAddresses.clear()
            expectedServiceFound = false
            acquireMulticastLock()
            val startedForGeneration = generation
            val expectedName = Gs179LanDiscoveryPolicy.expectedServiceName(expectedTlsHost)
            diagnostic("DISCOVERY_START_REQUESTED serviceType=${Gs179LanDiscoveryPolicy.SERVICE_TYPE} generation=$startedForGeneration")
            val discovery = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(serviceType: String) {
                    diagnostic("DISCOVERY_STARTED serviceType=$serviceType generation=$startedForGeneration")
                }

                override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                    val matchesName = serviceInfo.serviceName.equals(expectedName, true)
                    val matchesType = serviceInfo.serviceType?.trim()?.trimEnd('.')?.lowercase() ==
                        Gs179LanDiscoveryPolicy.SERVICE_TYPE.trimEnd('.')
                    if (!matchesName || !matchesType) {
                        if (matchesName) diagnostic(
                            "SERVICE_IGNORED reason=unexpected_service_type type=${serviceInfo.serviceType?.take(80)}",
                        ) else if (matchesType) diagnostic(
                            "SERVICE_IGNORED reason=unexpected_instance name=${serviceInfo.serviceName.take(80)}",
                        )
                        return
                    }
                    synchronized(lock) {
                        if (active && generation == startedForGeneration) expectedServiceFound = true
                    }
                    val key = "${serviceInfo.serviceName.lowercase()}|${serviceInfo.serviceType.trim().lowercase()}"
                    val queued = synchronized(lock) {
                        when {
                            !active || generation != startedForGeneration -> "stale_generation"
                            resolving.size >= Gs179LanDiscoveryPolicy.MAX_PENDING_RESOLVES -> "pending_resolve_limit"
                            !resolving.add(key) -> "already_resolving"
                            else -> null
                        }
                    }
                    if (queued != null) {
                        diagnostic("SERVICE_RESOLVE_SKIPPED reason=$queued")
                        return
                    }
                    diagnostic("SERVICE_FOUND name=${serviceInfo.serviceName} type=${serviceInfo.serviceType}")
                    resolve(serviceInfo, key, startedForGeneration)
                }

                override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                    if (serviceInfo.serviceName.equals(expectedName, true)) {
                        diagnostic("SERVICE_LOST name=${serviceInfo.serviceName}")
                    }
                }

                override fun onDiscoveryStopped(serviceType: String) {
                    diagnostic("DISCOVERY_STOPPED serviceType=$serviceType generation=$startedForGeneration")
                }

                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    diagnostic("NSD_START_FAILED code=$errorCode")
                    stopIfCurrent(startedForGeneration)
                }

                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    diagnostic("NSD_STOP_FAILED code=$errorCode")
                }
            }
            listener = discovery
            try {
                nsd.discoverServices(Gs179LanDiscoveryPolicy.SERVICE_TYPE,
                    NsdManager.PROTOCOL_DNS_SD, discovery)
                val timerPosted = main.postDelayed({
                    val noneFound = synchronized(lock) {
                        active && generation == startedForGeneration && !expectedServiceFound
                    }
                    if (noneFound) {
                        diagnostic("DISCOVERY_NO_EXPECTED_SERVICE_FOUND timeoutMillis=$NO_SERVICE_DIAGNOSTIC_DELAY_MILLIS")
                    }
                }, NO_SERVICE_DIAGNOSTIC_DELAY_MILLIS)
                if (!timerPosted) diagnostic("DISCOVERY_DIAGNOSTIC_TIMER_FAILED reason=main_handler_rejected")
            } catch (error: RuntimeException) {
                diagnostic("NSD_START_FAILED type=${error.javaClass.simpleName}")
                stopIfCurrent(startedForGeneration)
            }
        }
    }

    fun stop() {
        val oldListener: NsdManager.DiscoveryListener?
        synchronized(lock) {
            if (!active && listener == null) return
            active = false
            generation += 1
            resolving.clear()
            attemptedAddresses.clear()
            oldListener = listener
            listener = null
        }
        if (oldListener != null) {
            try {
                nsd.stopServiceDiscovery(oldListener)
                diagnostic("DISCOVERY_STOP_REQUESTED")
            } catch (error: RuntimeException) {
                // Discovery may have failed before the framework registered the listener.
                diagnostic("DISCOVERY_STOP_FAILED type=${error.javaClass.simpleName}")
            }
        }
        synchronized(lock) {
            multicastLock?.let { held ->
                if (held.isHeld) held.release()
            }
            multicastLock = null
        }
    }

    fun restart() {
        stop()
        start()
    }

    private fun acquireMulticastLock() {
        try {
            multicastLock = wifi.createMulticastLock("gs179-lan-discovery").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (error: RuntimeException) {
            diagnostic("MULTICAST_LOCK_FAILED type=${error.javaClass.simpleName}")
        }
    }

    @Suppress("DEPRECATION")
    private fun resolve(info: NsdServiceInfo, key: String, callbackGeneration: Int) {
        val resolveListener = object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                diagnostic("SERVICE_RESOLVE_FAILED code=$errorCode name=${serviceInfo.serviceName}")
                removeResolving(key, callbackGeneration)
            }

            override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                val attributes = serviceInfo.attributes.mapValues { (_, value) ->
                    String(value, Charsets.UTF_8)
                }
                val mismatch = Gs179LanDiscoveryPolicy.serviceMismatchReason(
                        serviceInfo.serviceName, serviceInfo.serviceType, serviceInfo.port,
                        attributes, expectedTlsHost)
                if (mismatch != null) {
                    diagnostic("SERVICE_RESOLVED_REJECTED reason=$mismatch port=${serviceInfo.port}")
                    removeResolving(key, callbackGeneration)
                    return
                }
                diagnostic("SERVICE_RESOLVED_VALID serviceName=${serviceInfo.serviceName} port=${serviceInfo.port} txtKeys=${attributes.keys.sorted().joinToString(",")}")
                val resolvedAddresses = resolvedAddresses(serviceInfo)
                val ipv4Count = resolvedAddresses.count { it is Inet4Address }
                val privateAddresses = Gs179LanDiscoveryPolicy.privateIpv4Addresses(resolvedAddresses)
                if (privateAddresses.isEmpty()) {
                    diagnostic("SERVICE_RESOLVED_REJECTED reason=no_private_ipv4 hostCount=${resolvedAddresses.size} ipv4Count=$ipv4Count")
                    removeResolving(key, callbackGeneration)
                    return
                }
                val addressesToProbe = synchronized(lock) {
                    if (!active || generation != callbackGeneration) return@synchronized emptyList()
                    privateAddresses.filter { address ->
                        Gs179LanDiscoveryPolicy.canProbeAddress(address, attemptedAddresses) &&
                            attemptedAddresses.add(address)
                    }
                }
                if (addressesToProbe.isEmpty()) {
                    val current = isCurrent(callbackGeneration)
                    diagnostic("SERVICE_PROBE_SKIPPED reason=${if (current) "address_budget_exhausted" else "stale_generation"}")
                    removeResolving(key, callbackGeneration)
                    return
                }
                diagnostic("IPV4_CANDIDATES_SELECTED count=${addressesToProbe.size} addresses=${addressesToProbe.joinToString(",")}")
                Thread({
                    try {
                        val pairedPin = BackendEndpointStore.serverSpkiSha256(appContext)
                        val candidateNetwork = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                            serviceInfo.network else null
                        for (address in addressesToProbe) {
                            if (!isCurrent(callbackGeneration)) {
                                diagnostic("HTTPS_PROBE_ABORTED reason=stale_generation")
                                break
                            }
                            diagnostic("HTTPS_PROBE_STARTED address=$address expectedTlsHost=$expectedTlsHost spkiPinPresent=${pairedPin != null}")
                            val verifiedPin = Gs179LanTlsProbe.verify(
                                address, expectedTlsHost, pairedPin, candidateNetwork,
                            ) { reason -> diagnostic("HTTPS_PROBE_REJECTED address=$address reason=$reason") }
                            if (verifiedPin == null) continue
                            diagnostic("HTTPS_PROBE_VERIFIED address=$address caAndIpHostnameVerified=true dnsSanVerified=true spkiContinuityVerified=${pairedPin != null} readyz=true")
                            val origin = BackendOrigin.parse(
                                "https://$address", allowTestOnlyLanEndpoint = true,
                            )
                            if (origin == null) {
                                diagnostic("ENDPOINT_SAVE_REJECTED reason=invalid_verified_private_origin address=$address")
                                continue
                            }
                            // A completed probe from an old Wi-Fi generation must not persist its
                            // address after the phone has moved to another network.
                            val saveFailure = synchronized(lock) {
                                when {
                                    !active || generation != callbackGeneration -> "stale_generation"
                                    !BackendEndpointStore.saveVerifiedLanServer(appContext, origin, verifiedPin) ->
                                        "persistence_failure"
                                    else -> null
                                }
                            }
                            if (saveFailure != null) {
                                diagnostic("ENDPOINT_SAVE_REJECTED reason=$saveFailure address=$address")
                                continue
                            }
                            diagnostic("ENDPOINT_SAVED address=$address serverSpkiPinSaved=true")
                            val delivered = main.post {
                                if (isCurrent(callbackGeneration)) {
                                    diagnostic("VERIFIED_ENDPOINT_DELIVERED address=$address")
                                    onVerifiedEndpoint(origin)
                                } else {
                                    diagnostic("VERIFIED_ENDPOINT_DROPPED reason=stale_generation")
                                }
                            }
                            if (!delivered) diagnostic("VERIFIED_ENDPOINT_DROPPED reason=main_handler_rejected")
                            break
                        }
                    } catch (error: Exception) {
                        diagnostic("HTTPS_PROBE_EXCEPTION type=${error.javaClass.simpleName}")
                    } finally {
                        removeResolving(key, callbackGeneration)
                    }
                }, "gs179-lan-https-probe").apply {
                    isDaemon = true
                    start()
                }
            }
        }
        try {
            nsd.resolveService(info, resolveListener)
        } catch (error: RuntimeException) {
            diagnostic("SERVICE_RESOLVE_REQUEST_FAILED type=${error.javaClass.simpleName}")
            removeResolving(key, callbackGeneration)
        }
    }

    private fun removeResolving(key: String, callbackGeneration: Int) {
        synchronized(lock) {
            if (generation == callbackGeneration) resolving.remove(key)
        }
    }

    @Suppress("DEPRECATION")
    private fun resolvedAddresses(serviceInfo: NsdServiceInfo): List<InetAddress> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            serviceInfo.hostAddresses
        } else {
            listOfNotNull(serviceInfo.host)
        }

    private fun isCurrent(callbackGeneration: Int): Boolean = synchronized(lock) {
        active && generation == callbackGeneration
    }

    private fun stopIfCurrent(callbackGeneration: Int) {
        val shouldStop = synchronized(lock) { active && generation == callbackGeneration }
        if (shouldStop) stop()
    }

    private fun diagnostic(message: String) {
        if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) Log.i(TAG, "GS179_LAN_$message")
    }

    companion object {
        private const val TAG = "ParivarSaathiLan"
        private const val NO_SERVICE_DIAGNOSTIC_DELAY_MILLIS = 10_000L
    }
}

/** Uses Android's configured trust anchors and default hostname verifier; it never accepts TLS errors. */
internal object Gs179LanTlsProbe {
    private const val TIMEOUT_MILLIS = 3500
    private const val MAX_READY_BYTES = 4096

    fun verify(
        address: String,
        expectedTlsHost: String,
        expectedPin: String?,
        network: android.net.Network? = null,
        onDiagnostic: (String) -> Unit = {},
    ): String? {
        fun reject(reason: String): String? {
            if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) onDiagnostic(reason)
            return null
        }
        if (!Gs179LanDiscoveryPolicy.isPrivateIpv4(address)) return reject("non_private_ipv4")
        val connection = try {
            val url = URL("https://$address/readyz")
            (network?.openConnection(url) ?: url.openConnection()) as? HttpsURLConnection
                ?: return reject("https_connection_unavailable")
        } catch (error: Exception) {
            return reject("connection_open_${failureReason(error)}")
        }
        return try {
            connection.connectTimeout = TIMEOUT_MILLIS
            connection.readTimeout = TIMEOUT_MILLIS
            connection.instanceFollowRedirects = false
            connection.useCaches = false
            connection.requestMethod = "GET"
            connection.setRequestProperty("Accept", "application/json")
            val responseCode = connection.responseCode
            if (responseCode != 200) return reject("readyz_http_status_$responseCode")
            if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) onDiagnostic("platform_ca_and_ip_hostname_verified")
            val leaf = connection.serverCertificates.firstOrNull() as? X509Certificate
                ?: return reject("peer_certificate_missing")
            val dnsNames = leaf.subjectAlternativeNames.orEmpty().mapNotNull { entry ->
                if (entry.size >= 2 && entry[0] == 2) entry[1]?.toString() else null
            }
            if (!Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(expectedTlsHost, dnsNames)) {
                return reject("expected_laptop_dns_san_missing")
            }
            val pin = MessageDigest.getInstance("SHA-256")
                .digest(leaf.publicKey.encoded)
                .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
            if (!Gs179LanDiscoveryPolicy.serverKeyMatches(expectedPin, pin)) {
                return reject("saved_spki_pin_mismatch")
            }
            if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) {
                onDiagnostic("expected_laptop_dns_san_verified saved_spki_continuity=${expectedPin != null}")
            }
            val response = connection.inputStream.use { input ->
                val bytes = ByteArray(MAX_READY_BYTES + 1)
                var count = 0
                while (count < bytes.size) {
                    val read = input.read(bytes, count, bytes.size - count)
                    if (read < 0) break
                    count += read
                }
                if (count > MAX_READY_BYTES) return reject("readyz_response_oversized")
                String(bytes, 0, count, Charsets.UTF_8)
            }
            val readiness = try {
                JSONObject(response)
            } catch (_: Exception) {
                return reject("readyz_invalid_json")
            }
            if (readiness.optString("status") != "ready" ||
                readiness.optString("database") != "reachable") {
                return reject("readyz_database_not_ready")
            }
            if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) onDiagnostic("readyz_database_reachable")
            pin
        } catch (error: Exception) {
            reject("https_probe_${failureReason(error)}")
        } finally {
            connection.disconnect()
        }
    }

    internal fun failureReason(error: Exception): String = when (error) {
        is SocketTimeoutException -> "timeout"
        is SSLPeerUnverifiedException -> "hostname_verification_failed"
        is SSLHandshakeException -> "tls_chain_or_handshake_failed"
        else -> "io_${error.javaClass.simpleName}"
    }
}
