package `in`.gharsajag.caregiver

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendOriginTest {
    // GS177-ANDROID-ORIGIN-001: positive, negative, boundary and recovery coverage.
    @Test
    fun acceptsPublicHttpsRootAndNormalizesIt() {
        val origin = BackendOrigin.parse("  HTTPS://Care.GharSajag.in/  ")
        assertNotNull(origin)
        assertEquals("https://care.gharsajag.in/", origin?.baseUrl)
    }

    @Test
    fun rejectsNonHttpsLocalReservedAndCredentialBearingUrls() {
        val invalid = listOf(
            "http://care.gharsajag.in/",
            "https://localhost/",
            "https://api.local/",
            "https://api.invalid/",
            "https://127.0.0.1/",
            "https://user:password@care.gharsajag.in/",
            "https://care.gharsajag.in:8443/",
            "https://care.gharsajag.in/app/",
            "https://care.gharsajag.in/?actor=demo",
            "https://care.gharsajag.in/#token",
            "https://care_gharsajag.in/",
            "https://care.gharsajag.x/",
            "not a URL",
        )
        invalid.forEach { assertNull("unexpectedly accepted: $it", BackendOrigin.parse(it)) }
    }

    @Test
    fun allowsNavigationOnlyToTheConfiguredTlsOrigin() {
        val origin = BackendOrigin.parse("https://care.gharsajag.in")
        assertNotNull(origin)
        assertTrue(origin!!.allows("https", "care.gharsajag.in", -1))
        assertTrue(origin.allows("HTTPS", "CARE.GHARSAJAG.IN", 443))
        assertFalse(origin.allows("http", "care.gharsajag.in", -1))
        assertFalse(origin.allows("https", "attacker.example.org", 443))
        assertFalse(origin.allows("https", "care.gharsajag.in", 8443))
    }

    @Test
    fun invalidBuildOriginDoesNotNormalizeIntoATrustedOrigin() {
        assertNull(BackendOrigin.parse("http://care.gharsajag.in"))
        assertEquals(
            "https://care.gharsajag.in/",
            BackendOrigin.parse("https://care.gharsajag.in")?.baseUrl,
        )
    }

    @Test
    fun privateLanOriginRequiresExplicitTestOnlyBuildPermission() {
        assertNull(BackendOrigin.parse("https://192.168.1.6"))
        assertEquals(
            "https://192.168.1.6/",
            BackendOrigin.parse("https://192.168.1.6/", allowTestOnlyPrivateIpv4 = true)?.baseUrl,
        )
        listOf("https://8.8.8.8", "https://172.15.1.2", "https://172.32.1.2",
            "https://192.168.001.6", "https://10.0.0.256", "https://127.0.0.1")
            .forEach { assertNull("unexpectedly accepted: $it", BackendOrigin.parse(it, true)) }
    }

    @Test
    fun normalLaunchUsesBundledPwaAssetsWithConfiguredOrOfflineOrigin() {
        val configured = BackendOrigin.parse("https://care.gharsajag.in")
        assertEquals(
            "https://care.gharsajag.in/__caregiver_app__/index.html",
            TrustedPwaWebView.startUrl(configured),
        )
        assertEquals(
            "https://appassets.androidplatform.net/__caregiver_app__/index.html",
            TrustedPwaWebView.startUrl(null),
        )
    }

    @Test
    fun debugEndpointIsBuildConfiguredAndUserRuntimeOverrideIsAbsent() {
        assertTrue(BuildConfig.DEV_ENDPOINT_CONFIG_ALLOWED)
        assertNull(BackendOrigin.parse(""))
    }
}
