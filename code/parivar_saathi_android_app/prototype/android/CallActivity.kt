package `in`.gharsajag.caregiver

import android.Manifest
import android.os.Bundle
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import android.webkit.WebView

/** A native notification opens the secure WebRTC answer page on the SAME PWA origin. */
class CallActivity : ComponentActivity() {
    private lateinit var web: WebView
    private val mic = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) openCall() else finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val callId = intent.getStringExtra("call_id") ?: ""
        if (!Regex("^c_[0-9a-f]{32}$").matches(callId)) { finish(); return }
        if (!BuildConfig.FCM_ENABLED) { finish(); return }
        val origin = BackendEndpointStore.load(this) ?: run { finish(); return }
        web = TrustedPwaWebView.create(this, allowAudio = true)
        setContentView(web)
        mic.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun openCall() {
        val callId = intent.getStringExtra("call_id") ?: return
        val origin = BackendEndpointStore.load(this) ?: return
        val callPage = Uri.parse(origin.baseUrl).buildUpon()
            .appendPath("caregiver")
            .appendPath("call.html")
            .appendQueryParameter("call_id", callId)
            .build()
        web.loadUrl(callPage.toString())
    }

    override fun onDestroy() {
        if (::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
