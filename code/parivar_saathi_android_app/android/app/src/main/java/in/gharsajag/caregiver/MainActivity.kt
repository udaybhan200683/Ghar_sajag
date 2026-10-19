package `in`.gharsajag.caregiver

import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebView
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat

/** Opens the bundled Parivar Saathi PWA; the service origin is fixed at build time. */
class MainActivity : ComponentActivity() {
    private var web: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        // Android 15+ draws edge-to-edge. Reserve status/navigation-bar and
        // display-cutout space outside the WebView so on-screen system keys
        // cannot cover the app's bottom tabs or simulation controls.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val safeContent = FrameLayout(this)
        val backendOrigin = BackendOrigin.parse(
            BuildConfig.BACKEND_ORIGIN,
            allowTestOnlyPrivateIpv4 = BuildConfig.GS179_LOCAL_LAN_TEST_ONLY,
        )
        val dashboard = TrustedPwaWebView.create(this, backendOrigin)
        safeContent.addView(dashboard, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        ViewCompat.setOnApplyWindowInsetsListener(safeContent) { view, insets ->
            val safe = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            view.setPadding(safe.left, safe.top, safe.right, safe.bottom)
            insets
        }
        web = dashboard
        setContentView(safeContent)
        ViewCompat.requestApplyInsets(safeContent)
        dashboard.loadUrl(TrustedPwaWebView.startUrl(backendOrigin))

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
}
