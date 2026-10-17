package `in`.gharsajag.caregiver

import android.app.Activity
import android.net.Uri
import android.net.http.SslError
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.ByteArrayInputStream
import java.io.InputStream

/** Serves the shared PWA from the APK and permits network access only to its configured origin. */
object TrustedPwaWebView {
    private const val APP_ASSET_HOST = "appassets.androidplatform.net"
    private const val APP_ASSET_PREFIX = "/__caregiver_app__/"

    fun startUrl(origin: BackendOrigin?): String {
        val host = origin?.host ?: APP_ASSET_HOST
        return "https://$host$APP_ASSET_PREFIX" + "index.html"
    }

    fun create(activity: Activity, backendOrigin: BackendOrigin?): WebView {
        val trustedHost = backendOrigin?.host ?: APP_ASSET_HOST
        val view = WebView(activity)
        view.settings.javaScriptEnabled = true
        view.settings.domStorageEnabled = true
        view.settings.allowFileAccess = false
        view.settings.allowContentAccess = false
        view.settings.javaScriptCanOpenWindowsAutomatically = false
        view.settings.setSupportMultipleWindows(false)
        view.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        view.settings.safeBrowsingEnabled = true
        view.settings.mediaPlaybackRequiresUserGesture = true
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(view, false)
        view.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(v: WebView, request: WebResourceRequest): WebResourceResponse? {
                val uri = request.url
                if (uri.scheme.equals("https", ignoreCase = true) &&
                    uri.host?.equals(trustedHost, ignoreCase = true) == true &&
                    (uri.port == -1 || uri.port == 443) &&
                    uri.path?.startsWith(APP_ASSET_PREFIX) == true
                ) {
                    return serveBundledAsset(activity, uri, backendOrigin)
                }
                if (backendOrigin?.allows(uri.scheme, uri.host, uri.port) == true) return null
                return blockedResponse()
            }

            override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean =
                !request.url.scheme.equals("https", ignoreCase = true) ||
                    request.url.host?.equals(trustedHost, ignoreCase = true) != true ||
                    (request.url.port != -1 && request.url.port != 443)

            override fun onReceivedSslError(v: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
            }
        }
        view.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: android.webkit.PermissionRequest) {
                request.deny()
            }
        }
        return view
    }

    private fun serveBundledAsset(
        activity: Activity,
        uri: Uri,
        backendOrigin: BackendOrigin?,
    ): WebResourceResponse {
        val relative = uri.path.orEmpty().removePrefix(APP_ASSET_PREFIX)
        if (relative.isEmpty() || relative.startsWith("/") || relative.contains('\\') ||
            relative.split('/').any { it == "." || it == ".." }
        ) return errorResponse(404, "Not found")

        if (relative == "runtime-config.js") {
            val origin = backendOrigin?.baseUrl.orEmpty()
            val body = "window.PARIVAR_SAATHI_RUNTIME=Object.freeze({mode:\"caregiver\",backendOrigin:\"$origin\",caregiverApiConfigured:${backendOrigin != null},appVersion:\"0.4.0-connected-lite-staging\",sourceRevision:\"${BuildConfig.SOURCE_REVISION}\"});"
            return response("text/javascript", ByteArrayInputStream(body.toByteArray(Charsets.UTF_8)), backendOrigin)
        }

        val mime = mimeType(relative) ?: return errorResponse(404, "Not found")
        val stream: InputStream = try {
            activity.assets.open(relative)
        } catch (_: Exception) {
            return errorResponse(404, "Not found")
        }
        return response(mime, stream, backendOrigin)
    }

    private fun mimeType(path: String): String? = when (path.substringAfterLast('.', "").lowercase()) {
        "html" -> "text/html"
        "js", "mjs" -> "text/javascript"
        "css" -> "text/css"
        "svg" -> "image/svg+xml"
        "png" -> "image/png"
        "webmanifest", "json" -> "application/manifest+json"
        "ico" -> "image/x-icon"
        else -> null
    }

    private fun response(mime: String, body: InputStream, backendOrigin: BackendOrigin?): WebResourceResponse {
        val connectSource = backendOrigin?.baseUrl?.trimEnd('/') ?: "'self'"
        val csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; " +
            "img-src 'self' data:; connect-src 'self' $connectSource; object-src 'none'; " +
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return WebResourceResponse(
            mime,
            "UTF-8",
            200,
            "OK",
            mapOf(
                "Cache-Control" to "no-store",
                "Content-Security-Policy" to csp,
                "X-Content-Type-Options" to "nosniff",
                "Referrer-Policy" to "no-referrer",
            ),
            body,
        )
    }

    private fun blockedResponse(): WebResourceResponse = errorResponse(403, "Blocked by caregiver app origin policy")

    private fun errorResponse(code: Int, message: String): WebResourceResponse = WebResourceResponse(
        "text/plain",
        "UTF-8",
        code,
        if (code == 404) "Not Found" else "Forbidden",
        mapOf("Cache-Control" to "no-store", "X-Content-Type-Options" to "nosniff"),
        ByteArrayInputStream(message.toByteArray(Charsets.UTF_8)),
    )
}
