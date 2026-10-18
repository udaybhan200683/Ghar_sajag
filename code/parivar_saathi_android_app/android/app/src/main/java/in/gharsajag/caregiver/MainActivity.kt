package in.gharsajag.caregiver

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.google.firebase.messaging.FirebaseMessaging

/** Existing Parivar Saathi web dashboard is authoritative UI: no parallel mock screens. */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = TrustedPwaWebView.create(this, allowAudio = false)
        setContentView(web)
        web.loadUrl(BuildConfig.PWA_BASE_URL)
        if (Build.VERSION.SDK_INT >= 33) notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            DeviceRegistration.register(this, token)
        }
    }

    override fun onResume() {
        super.onResume()
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token -> DeviceRegistration.register(this, token) }
    }

    @Deprecated("Use platform back dispatcher for future UI upgrades")
    override fun onBackPressed() { if (web.canGoBack()) web.goBack() else super.onBackPressed() }
    override fun onDestroy() { web.destroy(); super.onDestroy() }
}
