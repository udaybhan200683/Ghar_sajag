package in.gharsajag.caregiver

import java.net.URI
import java.util.Locale

/** Exact HTTPS origin selected by the installer. The app never accepts an HTTP or local server. */
data class BackendOrigin private constructor(
    val baseUrl: String,
    val host: String,
) {
    fun allows(scheme: String?, candidateHost: String?, port: Int): Boolean =
        scheme.equals("https", ignoreCase = true) &&
            candidateHost.equals(host, ignoreCase = true) &&
            (port == -1 || port == 443)

    companion object {
        private val dnsName = Regex(
            "^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+" +
                "[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$",
        )
        private val localOrReservedSuffixes = setOf("localhost", "local", "test", "example", "invalid")

        fun parse(input: String?): BackendOrigin? {
            val raw = input?.trim()?.takeIf { it.isNotEmpty() && it.length <= 2048 } ?: return null
            val uri = try {
                URI(raw)
            } catch (_: Exception) {
                return null
            }
            if (!uri.scheme.equals("https", ignoreCase = true)) return null
            if (uri.rawUserInfo != null || uri.rawQuery != null || uri.rawFragment != null) return null
            if (uri.port !in setOf(-1, 443)) return null
            if (uri.rawPath !in setOf("", "/")) return null

            val host = uri.host?.lowercase(Locale.ROOT) ?: return null
            if (!dnsName.matches(host)) return null
            if (host.split('.').any { it.isEmpty() || it.length > 63 }) return null
            val suffix = host.substringAfterLast('.')
            if (suffix.length < 2 || suffix in localOrReservedSuffixes) return null

            return BackendOrigin(baseUrl = "https://$host/", host = host)
        }
    }
}
