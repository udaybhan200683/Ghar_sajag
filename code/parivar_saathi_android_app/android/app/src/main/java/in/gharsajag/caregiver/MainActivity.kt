package `in`.gharsajag.caregiver

import android.os.Bundle
import android.content.Intent
import android.app.AlertDialog
import android.text.InputType
import android.view.ViewGroup
import android.widget.EditText
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.Toast
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
    }

    override fun onPause() {
        web?.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        web?.stopLoading()
        web?.destroy()
        web = null
        super.onDestroy()
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
            .setNeutralButton("Use paired laptop") { _, _ -> resetBackendOrigin() }
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
        showDashboard()
    }
}
