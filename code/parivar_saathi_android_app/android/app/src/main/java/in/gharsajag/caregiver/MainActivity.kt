package `in`.gharsajag.caregiver

import android.os.Bundle
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen

/** Opens the bundled Parivar Saathi PWA; the service origin is fixed at build time. */
class MainActivity : ComponentActivity() {
    private var web: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        val backendOrigin = BackendOrigin.parse(BuildConfig.BACKEND_ORIGIN)
        val dashboard = TrustedPwaWebView.create(this, backendOrigin)
        web = dashboard
        setContentView(dashboard)
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
