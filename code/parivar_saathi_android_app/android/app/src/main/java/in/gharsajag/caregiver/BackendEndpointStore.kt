package `in`.gharsajag.caregiver

import android.content.Context

/** The backend URL is configuration, not a credential. Android private app storage keeps it local. */
object BackendEndpointStore {
    private const val PREFS = "parivar_saathi_server"
    private const val URL = "https_origin"

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

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(URL)
            .apply()
    }
}
