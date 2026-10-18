package in.gharsajag.caregiver

import android.Manifest
import android.os.Bundle
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import java.net.URLEncoder

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
        web = TrustedPwaWebView.create(this, allowAudio = true)
        setContentView(web)
        mic.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun openCall() {
        val callId = intent.getStringExtra("call_id") ?: return
        val encoded = URLEncoder.encode(callId, "UTF-8")
        web.loadUrl(BuildConfig.PWA_BASE_URL + "caregiver/call.html?call_id=" + encoded)
    }

    override fun onDestroy() {
        if (::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
