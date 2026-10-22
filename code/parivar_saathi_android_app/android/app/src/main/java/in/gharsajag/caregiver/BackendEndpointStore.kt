package `in`.gharsajag.caregiver

import android.content.Context

/** The backend URL is configuration, not a credential. Android private app storage keeps it local. */
object BackendEndpointStore {
    private const val PREFS = "parivar_saathi_server"
    private const val URL = "https_origin"
    private const val SERVER_SPKI_SHA256 = "server_spki_sha256"

    fun load(context: Context): BackendOrigin? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(URL, null)
            ?.let { BackendOrigin.parse(it, allowTestOnlyLanEndpoint = BuildConfig.GS179_LOCAL_LAN_TEST_ONLY) }

    fun save(context: Context, origin: BackendOrigin) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(URL, origin.baseUrl)
            .apply()
    }

    fun serverSpkiSha256(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(SERVER_SPKI_SHA256, null)

    /** Persist only after the TEST_ONLY CA, IP SAN, expected laptop DNS SAN and readiness probe pass. */
    fun saveVerifiedLanServer(context: Context, origin: BackendOrigin, spkiSha256: String): Boolean {
        if (!BuildConfig.GS179_LOCAL_LAN_TEST_ONLY ||
            !Gs179LanDiscoveryPolicy.isPrivateIpv4(origin.host) ||
            !spkiSha256.matches(Regex("[0-9a-f]{64}"))) {
            return false
        }
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(URL, origin.baseUrl)
            .putString(SERVER_SPKI_SHA256, spkiSha256)
            .commit()
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(URL)
            .remove(SERVER_SPKI_SHA256)
            .apply()
    }
}
