package `in`.gharsajag.caregiver

import java.net.URI
import java.util.Locale

/** Exact HTTPS origin compiled into the app by its protected build configuration. */
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

        fun parse(input: String?, allowTestOnlyPrivateIpv4: Boolean = false): BackendOrigin? {
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
            if (allowTestOnlyPrivateIpv4) {
                if (!isPrivateIpv4(host)) return null
            } else {
                if (!dnsName.matches(host)) return null
                if (host.split('.').any { it.isEmpty() || it.length > 63 }) return null
                val suffix = host.substringAfterLast('.')
                if (suffix.length < 2 || suffix in localOrReservedSuffixes) return null
            }

            return BackendOrigin(baseUrl = "https://$host/", host = host)
        }

        private fun isPrivateIpv4(host: String): Boolean {
            val parts = host.split('.')
            if (parts.size != 4) return false
            val octets = parts.map { part ->
                if (part.isEmpty() || (part.length > 1 && part.startsWith('0')) ||
                    part.any { !it.isDigit() }) return false
                part.toIntOrNull()?.takeIf { it in 0..255 } ?: return false
            }
            return octets[0] == 10 ||
                (octets[0] == 172 && octets[1] in 16..31) ||
                (octets[0] == 192 && octets[1] == 168)
        }
    }
}
