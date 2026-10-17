package `in`.gharsajag.caregiver

import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebView
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback

/** Loads the deployed caregiver PWA after the owner supplies its real HTTPS origin. */
class MainActivity : ComponentActivity() {
    private var web: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val current = web
                if (current != null && current.canGoBack()) current.goBack() else finish()
            }
        })
        val origin = BackendEndpointStore.load(this)
        if (origin == null) showSetup() else showDashboard(origin)
    }

    private fun showSetup(errorMessage: String? = null) {
        destroyWebView()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(32), dp(24), dp(24))
        }
        root.addView(TextView(this).apply {
            text = "Parivar Saathi"
            textSize = 26f
        }, matchWidth())
        root.addView(TextView(this).apply {
            text = "Connect to the Ghar Sajag caregiver service. Enter the HTTPS address provided by your administrator. The app will only navigate within that HTTPS origin."
            textSize = 16f
            setPadding(0, dp(16), 0, dp(16))
        }, matchWidth())
        val input = EditText(this).apply {
            hint = "HTTPS server address"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(BackendEndpointStore.load(this@MainActivity)?.baseUrl.orEmpty())
        }
        root.addView(input, matchWidth())
        val feedback = TextView(this).apply {
            text = errorMessage.orEmpty()
            setTextColor(0xffb3261e.toInt())
            setPadding(0, dp(8), 0, dp(8))
        }
        root.addView(feedback, matchWidth())
        root.addView(TextView(this).apply {
            text = "This test build has no push notifications, voice calling, or automatic escalation. It contains no demo account or local dashboard."
            textSize = 14f
            setPadding(0, dp(8), 0, dp(20))
        }, matchWidth())
        root.addView(Button(this).apply {
            text = "Open caregiver PWA"
            setOnClickListener {
                val origin = BackendOrigin.parse(input.text?.toString())
                if (origin == null) {
                    feedback.text = "Enter a public HTTPS domain with no path, credentials, query, or custom port."
                } else {
                    BackendEndpointStore.save(this@MainActivity, origin)
                    showDashboard(origin)
                }
            }
        }, matchWidth())
        setContentView(root)
    }

    private fun showDashboard(origin: BackendOrigin) {
        destroyWebView()
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(12), dp(4), dp(8), dp(4))
        }
        toolbar.addView(TextView(this).apply {
            text = "Dashboard-only build · calls and notifications disabled"
            textSize = 12f
            setPadding(0, dp(10), 0, dp(10))
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        toolbar.addView(Button(this).apply {
            text = "Server"
            setOnClickListener { changeServer() }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(toolbar, matchWidth())

        val dashboard = TrustedPwaWebView.create(this, origin)
        web = dashboard
        root.addView(dashboard, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)
        dashboard.loadUrl(origin.baseUrl)
    }

    private fun changeServer() {
        val current = web
        web = null
        current?.stopLoading()
        current?.destroy()
        CookieManager.getInstance().removeAllCookies {
            runOnUiThread {
                CookieManager.getInstance().flush()
                BackendEndpointStore.clear(this)
                showSetup()
            }
        }
    }

    private fun destroyWebView() {
        web?.stopLoading()
        web?.destroy()
        web = null
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun matchWidth() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT,
    )

    override fun onResume() {
        super.onResume()
        web?.onResume()
    }

    override fun onPause() {
        web?.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        destroyWebView()
        super.onDestroy()
    }
}
