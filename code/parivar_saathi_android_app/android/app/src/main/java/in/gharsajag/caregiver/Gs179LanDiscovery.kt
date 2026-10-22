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
import java.net.URL
import java.security.MessageDigest
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
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
    ): Boolean {
        val expectedName = expectedServiceName(expectedTlsHost) ?: return false
        val normalizedType = serviceType?.trim()?.trimEnd('.')?.lowercase() ?: return false
        val normalizedAttributes = attributes.mapKeys { it.key.lowercase() }
        return serviceName.equals(expectedName, ignoreCase = true) &&
            normalizedType == SERVICE_TYPE.trimEnd('.') && port == 443 &&
            normalizedAttributes["profile"] == SERVICE_PROFILE &&
            normalizedAttributes["tls_host"].equals(expectedTlsHost, ignoreCase = true) &&
            normalizedAttributes["protocol"] == "1"
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

    fun start() {
        synchronized(lock) {
            if (active || !BuildConfig.GS179_LOCAL_LAN_TEST_ONLY ||
                Gs179LanDiscoveryPolicy.expectedServiceName(expectedTlsHost) == null) return
            active = true
            generation += 1
            resolving.clear()
            attemptedAddresses.clear()
            acquireMulticastLock()
            val startedForGeneration = generation
            val discovery = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(serviceType: String) = Unit

                override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                    if (!serviceInfo.serviceName.equals(
                            Gs179LanDiscoveryPolicy.expectedServiceName(expectedTlsHost), true) ||
                        serviceInfo.serviceType?.trim()?.trimEnd('.')?.lowercase() !=
                            Gs179LanDiscoveryPolicy.SERVICE_TYPE.trimEnd('.')
                    ) return
                    val key = "${serviceInfo.serviceName.lowercase()}|${serviceInfo.serviceType.trim().lowercase()}"
                    synchronized(lock) {
                        if (!active || generation != startedForGeneration ||
                            resolving.size >= Gs179LanDiscoveryPolicy.MAX_PENDING_RESOLVES ||
                            !resolving.add(key)) return
                    }
                    resolve(serviceInfo, key, startedForGeneration)
                }

                override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

                override fun onDiscoveryStopped(serviceType: String) = Unit

                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.i(TAG, "GS179_LAN_NSD_START_FAILED code=$errorCode")
                    stopIfCurrent(startedForGeneration)
                }

                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.i(TAG, "GS179_LAN_NSD_STOP_FAILED code=$errorCode")
                }
            }
            listener = discovery
            try {
                nsd.discoverServices(Gs179LanDiscoveryPolicy.SERVICE_TYPE,
                    NsdManager.PROTOCOL_DNS_SD, discovery)
            } catch (error: RuntimeException) {
                Log.i(TAG, "GS179_LAN_NSD_START_FAILED type=${error.javaClass.simpleName}")
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
            } catch (_: RuntimeException) {
                // Discovery may have failed before the framework registered the listener.
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
            Log.i(TAG, "GS179_LAN_MULTICAST_UNAVAILABLE type=${error.javaClass.simpleName}")
        }
    }

    @Suppress("DEPRECATION")
    private fun resolve(info: NsdServiceInfo, key: String, callbackGeneration: Int) {
        val resolveListener = object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                removeResolving(key, callbackGeneration)
            }

            override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                val attributes = serviceInfo.attributes.mapValues { (_, value) ->
                    String(value, Charsets.UTF_8)
                }
                if (!Gs179LanDiscoveryPolicy.matchesService(
                        serviceInfo.serviceName, serviceInfo.serviceType, serviceInfo.port,
                        attributes, expectedTlsHost)) {
                    removeResolving(key, callbackGeneration)
                    return
                }
                val address = (serviceInfo.host as? Inet4Address)?.hostAddress
                if (!Gs179LanDiscoveryPolicy.isPrivateIpv4(address)) {
                    removeResolving(key, callbackGeneration)
                    return
                }
                val shouldProbe = synchronized(lock) {
                    active && generation == callbackGeneration &&
                        Gs179LanDiscoveryPolicy.canProbeAddress(address, attemptedAddresses) &&
                        attemptedAddresses.add(address!!)
                }
                if (!shouldProbe) {
                    removeResolving(key, callbackGeneration)
                    return
                }
                Thread({
                    try {
                        val pairedPin = BackendEndpointStore.serverSpkiSha256(appContext)
                        val candidateNetwork = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                            serviceInfo.network else null
                        val verifiedPin = Gs179LanTlsProbe.verify(
                            address!!, expectedTlsHost, pairedPin, candidateNetwork,
                        )
                        if (verifiedPin == null || !isCurrent(callbackGeneration)) {
                            return@Thread
                        }
                        val origin = BackendOrigin.parse(
                            "https://$address", allowTestOnlyLanEndpoint = true,
                        ) ?: return@Thread
                        // A completed probe from an old Wi-Fi generation must not persist its
                        // address after the phone has moved to another network.
                        val saved = synchronized(lock) {
                            active && generation == callbackGeneration &&
                                BackendEndpointStore.saveVerifiedLanServer(appContext, origin, verifiedPin)
                        }
                        if (!saved) return@Thread
                        main.post {
                            if (isCurrent(callbackGeneration)) onVerifiedEndpoint(origin)
                        }
                    } catch (error: Exception) {
                        Log.i(TAG, "GS179_LAN_PROBE_FAILED type=${error.javaClass.simpleName}")
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
        } catch (_: RuntimeException) {
            removeResolving(key, callbackGeneration)
        }
    }

    private fun removeResolving(key: String, callbackGeneration: Int) {
        synchronized(lock) {
            if (generation == callbackGeneration) resolving.remove(key)
        }
    }

    private fun isCurrent(callbackGeneration: Int): Boolean = synchronized(lock) {
        active && generation == callbackGeneration
    }

    private fun stopIfCurrent(callbackGeneration: Int) {
        val shouldStop = synchronized(lock) { active && generation == callbackGeneration }
        if (shouldStop) stop()
    }

    companion object {
        private const val TAG = "ParivarSaathiLan"
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
    ): String? {
        if (!Gs179LanDiscoveryPolicy.isPrivateIpv4(address)) return null
        val connection = try {
            val url = URL("https://$address/readyz")
            (network?.openConnection(url) ?: url.openConnection()) as? HttpsURLConnection ?: return null
        } catch (_: Exception) {
            return null
        }
        return try {
            connection.connectTimeout = TIMEOUT_MILLIS
            connection.readTimeout = TIMEOUT_MILLIS
            connection.instanceFollowRedirects = false
            connection.useCaches = false
            connection.requestMethod = "GET"
            connection.setRequestProperty("Accept", "application/json")
            if (connection.responseCode != 200) return null
            val leaf = connection.serverCertificates.firstOrNull() as? X509Certificate ?: return null
            val dnsNames = leaf.subjectAlternativeNames.orEmpty().mapNotNull { entry ->
                if (entry.size >= 2 && entry[0] == 2) entry[1]?.toString() else null
            }
            if (!Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(expectedTlsHost, dnsNames)) return null
            val pin = MessageDigest.getInstance("SHA-256")
                .digest(leaf.publicKey.encoded)
                .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
            if (!Gs179LanDiscoveryPolicy.serverKeyMatches(expectedPin, pin)) return null
            val response = connection.inputStream.use { input ->
                val bytes = ByteArray(MAX_READY_BYTES + 1)
                var count = 0
                while (count < bytes.size) {
                    val read = input.read(bytes, count, bytes.size - count)
                    if (read < 0) break
                    count += read
                }
                if (count > MAX_READY_BYTES) return null
                String(bytes, 0, count, Charsets.UTF_8)
            }
            val readiness = JSONObject(response)
            if (readiness.optString("status") != "ready" ||
                readiness.optString("database") != "reachable") return null
            pin
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }
}
