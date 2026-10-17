package `in`.gharsajag.caregiver

import android.content.Context
import android.webkit.CookieManager
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/** Token registration only via an existing authenticated web session; never use a simulator actor header. */
object DeviceRegistration {
    fun register(context: Context, fcmToken: String) {
        if (!BuildConfig.FCM_ENABLED) return
        val origin = BackendEndpointStore.load(context) ?: return
        val pref = context.getSharedPreferences("app", Context.MODE_PRIVATE)
        var id = pref.getString("device_id", null)
        if (id == null) {
            id = "d_" + UUID.randomUUID().toString().replace("-", "")
            pref.edit().putString("device_id", id).apply()
        }
        val deviceId = id
        Thread {
            try {
                val root = origin.baseUrl
                val cookie = CookieManager.getInstance().getCookie(root) ?: return@Thread
                // Production backend must validate session, same-site CSRF, current caregiver/Home.
                // No silent synthetic/development actor headers or token logging.
                val url = URL(root + "v1/voice/devices")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 10000
                connection.readTimeout = 10000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Cookie", cookie)
                connection.setRequestProperty("Origin", root.trimEnd('/'))
                connection.doOutput = true
                connection.outputStream.use { it.write(JSONObject().put("device_id", deviceId).put("token", fcmToken).toString().toByteArray()) }
                val result = connection.responseCode
                if (result !in 200..299) {
                    // Keep local state as NOT REGISTERED; next foreground session retries.
                }
                connection.disconnect()
            } catch (_: Exception) {
                // No fake successful registration on network/auth failures.
            }
        }.start()
    }
}
