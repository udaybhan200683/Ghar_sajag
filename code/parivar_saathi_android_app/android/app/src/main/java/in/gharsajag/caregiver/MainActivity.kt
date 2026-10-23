package `in`.gharsajag.caregiver

import android.os.Bundle
import android.content.Intent
import android.app.AlertDialog
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.LinkProperties
import android.text.InputType
import android.view.ViewGroup
import android.widget.EditText
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.Toast
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import kotlin.math.max

/** Opens the bundled Parivar Saathi PWA at its configured, strictly verified HTTPS origin. */
class MainActivity : ComponentActivity() {
    private var web: WebView? = null
    private lateinit var safeContent: FrameLayout
    private var backendOrigin: BackendOrigin? = null
    private var lanDiscovery: Gs179LanServerDiscovery? = null
    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var activeWifiNetwork: Network? = null
    private var activeWifiRouteSignature: String? = null
    private var lastVerifiedWifiNetwork: Network? = null
    private var lastVerifiedWifiRouteSignature: String? = null
    private var lanDiscoveryForeground = false

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        // Android 15+ draws edge-to-edge. Reserve status/navigation-bar and
        // display-cutout space outside the WebView so on-screen system keys
        // cannot cover the app's bottom tabs or simulation controls.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        safeContent = FrameLayout(this)
        val configuredOrigin = BackendOrigin.parse(
            BuildConfig.BACKEND_ORIGIN,
            allowTestOnlyLanEndpoint = BuildConfig.GS179_LOCAL_LAN_TEST_ONLY,
        )
        backendOrigin = if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY)
            BackendEndpointStore.load(this) ?: configuredOrigin else configuredOrigin
        ViewCompat.setOnApplyWindowInsetsListener(safeContent) { view, insets ->
            val safe = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            val keyboard = insets.getInsets(WindowInsetsCompat.Type.ime())
            view.setPadding(safe.left, safe.top, safe.right, max(safe.bottom, keyboard.bottom))
            insets
        }
        setContentView(safeContent)
        ViewCompat.requestApplyInsets(safeContent)
        showDashboard()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val current = web
                if (current != null && current.canGoBack()) current.goBack() else finish()
            }
        })
    }

    override fun onResume() {
        super.onResume()
        web?.onResume()
        startLanDiscovery()
    }

    override fun onPause() {
        stopLanDiscovery()
        web?.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        stopLanDiscovery()
        web?.stopLoading()
        web?.destroy()
        web = null
        super.onDestroy()
    }

    private fun startLanDiscovery() {
        if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) return
        val configuredOrigin = BackendOrigin.parse(
            BuildConfig.BACKEND_ORIGIN, allowTestOnlyLanEndpoint = true,
        ) ?: run {
            lanDiagnostic("DISCOVERY_APP_START_SKIPPED reason=invalid_backend_origin")
            return
        }
        if (!configuredOrigin.host.endsWith(".local")) {
            lanDiagnostic("DISCOVERY_APP_START_SKIPPED reason=configured_origin_not_local_dns")
            return
        }
        lanDiscoveryForeground = true
        lanDiagnostic("DISCOVERY_APP_FOREGROUND expectedTlsHost=${configuredOrigin.host}")

        if (lanDiscovery == null) {
            lanDiscovery = Gs179LanServerDiscovery(this, configuredOrigin.host) { verified ->
                val wifiRouteChanged = activeWifiNetwork != lastVerifiedWifiNetwork ||
                    activeWifiRouteSignature != lastVerifiedWifiRouteSignature
                lanDiagnostic("VERIFIED_ENDPOINT address=${verified.host} wifiRouteChanged=$wifiRouteChanged")
                if (Gs179LanDiscoveryPolicy.shouldReloadForVerifiedEndpoint(
                        backendOrigin?.baseUrl, verified.baseUrl, wifiRouteChanged,
                    )) {
                    backendOrigin = verified
                    lastVerifiedWifiNetwork = activeWifiNetwork
                    lastVerifiedWifiRouteSignature = activeWifiRouteSignature
                    Toast.makeText(this, "Laptop server reconnected securely", Toast.LENGTH_SHORT).show()
                    showDashboard()
                } else {
                    lanDiagnostic("VERIFIED_ENDPOINT_RELOAD_SKIPPED reason=origin_and_route_unchanged")
                }
            }
        }
        val manager = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        connectivityManager = manager
        if (networkCallback == null) {
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    lanDiagnostic("DEFAULT_NETWORK_AVAILABLE")
                    updateDiscoveryNetwork(network)
                }

                override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
                    updateDiscoveryNetwork(network, capabilities)
                }

                override fun onLinkPropertiesChanged(network: Network, linkProperties: LinkProperties) {
                    updateDiscoveryLinkProperties(network, linkProperties)
                }

                override fun onLost(network: Network) {
                    lanDiagnostic("DEFAULT_NETWORK_LOST isActiveWifi=${activeWifiNetwork == network}")
                    if (activeWifiNetwork == network) updateDiscoveryNetwork(null)
                }
            }
            networkCallback = callback
            try {
                manager.registerDefaultNetworkCallback(callback)
            } catch (error: RuntimeException) {
                networkCallback = null
                lanDiagnostic("NETWORK_CALLBACK_REGISTER_FAILED type=${error.javaClass.simpleName}")
            }
        }
        updateDiscoveryNetwork(manager.activeNetwork)
    }

    private fun updateDiscoveryNetwork(network: Network?, supplied: NetworkCapabilities? = null) {
        runOnUiThread {
            if (!lanDiscoveryForeground) return@runOnUiThread
            val manager = connectivityManager ?: return@runOnUiThread
            val capabilities = supplied ?: network?.let { manager.getNetworkCapabilities(it) }
            val onWifi = network != null &&
                capabilities?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
            if (!onWifi) {
                val hadWifi = activeWifiNetwork != null
                activeWifiNetwork = null
                activeWifiRouteSignature = null
                lanDiscovery?.stop()
                if (hadWifi) lastVerifiedWifiNetwork = null
                if (hadWifi || network == null) lanDiagnostic("WIFI_DISCOVERY_STOPPED reason=no_default_wifi_network")
                return@runOnUiThread
            }
            val routeSignature = network?.let { manager.getLinkProperties(it) }
                ?.let(::wifiRouteSignature)
            val networkChanged = activeWifiNetwork != network
            val routeChanged = routeSignature != null && activeWifiRouteSignature != null &&
                routeSignature != activeWifiRouteSignature
            activeWifiNetwork = network
            activeWifiRouteSignature = routeSignature
            if (networkChanged || routeChanged) {
                lanDiagnostic("WIFI_DISCOVERY_RESTART reason=${if (networkChanged) "network_changed" else "route_changed"}")
                lanDiscovery?.restart()
            } else {
                lanDiagnostic("WIFI_DISCOVERY_START_REQUESTED reason=network_current")
                lanDiscovery?.start()
            }
        }
    }

    private fun updateDiscoveryLinkProperties(network: Network, properties: LinkProperties) {
        runOnUiThread {
            if (!lanDiscoveryForeground || activeWifiNetwork != network) return@runOnUiThread
            val signature = wifiRouteSignature(properties)
            if (signature != activeWifiRouteSignature) {
                activeWifiRouteSignature = signature
                activeWifiNetwork = network
                lanDiagnostic("WIFI_DISCOVERY_RESTART reason=link_properties_changed")
                lanDiscovery?.restart()
            }
        }
    }

    private fun wifiRouteSignature(properties: LinkProperties): String {
        val addresses = properties.linkAddresses
            .map { "${it.address.hostAddress}/${it.prefixLength}" }
            .sorted()
        val routes = properties.routes
            .map { "${it.destination}:${it.gateway?.hostAddress.orEmpty()}" }
            .sorted()
        return "${addresses.joinToString(",")}|${routes.joinToString(",")}"
    }

    private fun stopLanDiscovery() {
        lanDiscoveryForeground = false
        networkCallback?.let { callback ->
            try {
                connectivityManager?.unregisterNetworkCallback(callback)
            } catch (error: RuntimeException) {
                // The callback may already have been removed by the system.
                lanDiagnostic("NETWORK_CALLBACK_UNREGISTER_FAILED type=${error.javaClass.simpleName}")
            }
        }
        networkCallback = null
        lanDiscovery?.stop()
    }

    private fun showDashboard() {
        val previous = web
        if (previous != null) {
            previous.stopLoading()
            safeContent.removeView(previous)
            previous.destroy()
        }
        val dashboard = TrustedPwaWebView.create(
            this,
            backendOrigin,
            onHubWifiSetup = { startActivity(Intent(this, HubWifiSetupActivity::class.java)) },
            onBackendReconnect = { showBackendReconnect() },
            onBackendReset = { resetBackendOrigin() },
        )
        safeContent.addView(dashboard, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        web = dashboard
        dashboard.loadUrl(TrustedPwaWebView.startUrl(backendOrigin))
    }

    private fun showBackendReconnect() {
        if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) return
        val input = EditText(this).apply {
            hint = "https://laptop-name.local"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(backendOrigin?.baseUrl.orEmpty())
        }
        AlertDialog.Builder(this)
            .setTitle("Reconnect to local server")
            .setMessage("Use the laptop's stable .local hostname when available. A private IPv4 address is a fallback and must match the laptop's current HTTPS certificate. The app always verifies the server certificate.")
            .setView(input)
            .setNegativeButton("Cancel", null)
            .setNeutralButton("Use paired laptop") { _, _ -> usePairedLaptop() }
            .setPositiveButton("Connect") { _, _ ->
                val candidate = BackendOrigin.parse(
                    input.text.toString(),
                    allowTestOnlyLanEndpoint = true,
                )
                if (candidate == null) {
                    Toast.makeText(this, "Use an HTTPS .local hostname or private IPv4 address.", Toast.LENGTH_LONG).show()
                    return@setPositiveButton
                }
                // WebView keeps normal platform trust-chain and hostname checks. SSL errors are
                // cancelled; saving an endpoint never grants it authentication.
                BackendEndpointStore.save(this, candidate)
                backendOrigin = candidate
                showDashboard()
            }
            .show()
    }

    private fun resetBackendOrigin() {
        if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) return
        BackendEndpointStore.clear(this)
        backendOrigin = BackendOrigin.parse(BuildConfig.BACKEND_ORIGIN, allowTestOnlyLanEndpoint = true)
        lanDiagnostic("PAIRING_RESET explicitTrustReset=true")
        showDashboard()
    }

    private fun usePairedLaptop() {
        if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) return
        val pairedOrigin = BackendOrigin.parse(
            BuildConfig.BACKEND_ORIGIN, allowTestOnlyLanEndpoint = true,
        )
        if (pairedOrigin == null || !pairedOrigin.host.endsWith(".local")) {
            lanDiagnostic("PAIRING_REQUEST_REJECTED reason=invalid_configured_local_origin")
            Toast.makeText(this, "The paired laptop address is unavailable.", Toast.LENGTH_LONG).show()
            return
        }
        val currentHost = backendOrigin?.host ?: "none"
        val pinPresent = BackendEndpointStore.serverSpkiSha256(this) != null
        lanDiagnostic("PAIRING_DISCOVERY_REQUESTED currentEndpointRetained=true currentHost=$currentHost savedSpkiPinPresent=$pinPresent")
        if (activeWifiNetwork != null) {
            if (lanDiscovery != null) {
                lanDiscovery?.restart()
            } else {
                lanDiagnostic("PAIRING_DISCOVERY_FAILED reason=discovery_instance_unavailable")
            }
        } else {
            lanDiagnostic("PAIRING_DISCOVERY_WAITING reason=no_active_wifi_network")
        }
    }

    private fun lanDiagnostic(message: String) {
        if (BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) Log.i(TAG, "GS179_LAN_$message")
    }

    companion object {
        private const val TAG = "ParivarSaathiLan"
    }
}
