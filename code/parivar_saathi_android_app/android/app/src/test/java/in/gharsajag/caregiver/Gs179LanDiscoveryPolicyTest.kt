package `in`.gharsajag.caregiver

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Gs179LanDiscoveryPolicyTest {
    // GS177-LAN-NSD-001: bounded discovery metadata, private-address and TLS identity policy.
    private val host = "desktop-3qqu64b.local"
    private val serviceName = "GharSajag-GS179-desktop-3qqu64b"
    private val attributes = mapOf(
        "profile" to "GS179_TEST_ONLY",
        "tls_host" to host,
        "protocol" to "1",
    )

    @Test
    fun acceptsOnlyExpectedTestOnlyHttpsServiceAndLaptopIdentityHint() {
        assertTrue(Gs179LanDiscoveryPolicy.matchesService(
            serviceName, "_https._tcp.", 443, attributes, host,
        ))
        assertFalse(Gs179LanDiscoveryPolicy.matchesService(
            "Other-Laptop", "_https._tcp.", 443, attributes, host,
        ))
        assertFalse(Gs179LanDiscoveryPolicy.matchesService(
            serviceName, "_http._tcp.", 443, attributes, host,
        ))
        assertFalse(Gs179LanDiscoveryPolicy.matchesService(
            serviceName, "_https._tcp.", 8443, attributes, host,
        ))
        assertFalse(Gs179LanDiscoveryPolicy.matchesService(
            serviceName, "_https._tcp.", 443, attributes + ("profile" to "COMMERCIAL"), host,
        ))
        assertFalse(Gs179LanDiscoveryPolicy.matchesService(
            serviceName, "_https._tcp.", 443, attributes + ("tls_host" to "attacker.local"), host,
        ))
    }

    @Test
    fun acceptsOnlyPrivateIpv4ServiceAddresses() {
        listOf("10.0.0.8", "172.16.1.2", "172.31.255.1", "192.168.1.8")
            .forEach { assertTrue(it, Gs179LanDiscoveryPolicy.isPrivateIpv4(it)) }
        listOf(null, "8.8.8.8", "172.15.1.2", "172.32.1.2", "192.168.001.8",
            "192.168.1.256", "desktop.local", "127.0.0.1", "169.254.1.2")
            .forEach { assertFalse("unexpected private address: $it", Gs179LanDiscoveryPolicy.isPrivateIpv4(it)) }
    }

    @Test
    fun boundsHttpsProbesToFourDistinctPrivateAddressesPerNetworkGeneration() {
        val attempted = setOf("192.168.1.2", "192.168.1.3", "10.0.0.4", "172.16.0.5")
        assertFalse(Gs179LanDiscoveryPolicy.canProbeAddress("192.168.1.2", attempted))
        assertFalse(Gs179LanDiscoveryPolicy.canProbeAddress("192.168.1.6", attempted))
        assertFalse(Gs179LanDiscoveryPolicy.canProbeAddress("8.8.8.8", emptySet()))
        assertTrue(Gs179LanDiscoveryPolicy.canProbeAddress("192.168.1.6", attempted - "10.0.0.4"))
    }

    @Test
    fun exactDnsSanAndPersistedKeyPinAreRequiredAfterDiscovery() {
        assertTrue(Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(host, listOf(host)))
        assertTrue(Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(host, listOf("DESKTOP-3QQU64B.LOCAL.")))
        assertFalse(Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(host, listOf("other.local")))
        assertFalse(Gs179LanDiscoveryPolicy.certificateNamesExpectedHost(host, listOf("*.local")))
        assertTrue(Gs179LanDiscoveryPolicy.serverKeyMatches(null, "a".repeat(64)))
        assertTrue(Gs179LanDiscoveryPolicy.serverKeyMatches("a".repeat(64), "A".repeat(64)))
        assertFalse(Gs179LanDiscoveryPolicy.serverKeyMatches("a".repeat(64), "b".repeat(64)))
    }

    @Test
    fun verifiedSameOriginReconnectsOnlyAfterWifiRouteChanges() {
        val origin = "https://192.168.1.8/"
        assertTrue(Gs179LanDiscoveryPolicy.shouldReloadForVerifiedEndpoint(origin, origin, true))
        assertFalse(Gs179LanDiscoveryPolicy.shouldReloadForVerifiedEndpoint(origin, origin, false))
        assertTrue(Gs179LanDiscoveryPolicy.shouldReloadForVerifiedEndpoint(
            "https://192.168.1.6/", origin, false,
        ))
    }
}
