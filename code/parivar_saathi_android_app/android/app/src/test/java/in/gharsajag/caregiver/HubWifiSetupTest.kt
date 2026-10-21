package `in`.gharsajag.caregiver

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HubWifiSetupTest {
    private fun readyEvidence() = HubWifiProvisioningEvidence(
        securityVersion = 2,
        security2SessionAuthenticated = true,
        permanentHubIdentityVerified = true,
        oneUseHomePermitVerified = true,
        currentHomeEpoch = true,
        selectedNetworkCameFromHubScan = true,
        protectedCredentialStoreReady = true,
    )

    @Test fun discoveryNamesAreOnlyBoundedHints() {
        assertTrue(HubWifiDiscoveryPolicy.isCandidateName("PROV_S3_1"))
        listOf("HomeWiFi", "PROV_", "PROV_secret/password", "PROV_é", "PROV_" + "x".repeat(40))
            .forEach { assertFalse(HubWifiDiscoveryPolicy.isCandidateName(it)) }
    }

    @Test fun onlyExactBundledFirstPartyNavigationOpensDiscovery() {
        val host = "care.gharsajag.in"
        val page = "https://$host/__caregiver_app__/index.html"
        val destination = TrustedPwaWebView.HUB_WIFI_SETUP_URL
        assertTrue(HubWifiNavigationPolicy.canOpen(destination, page, host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination, page, host, false))
        assertFalse(HubWifiNavigationPolicy.canOpen("gharsajag://hub-wifi/add?password=x", page, host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "https://evil.example/__caregiver_app__/index.html", host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "https://$host/other", host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "https://$host.evil.example/__caregiver_app__/index.html", host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "http://$host/__caregiver_app__/index.html", host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "https://$host:8443/__caregiver_app__/index.html", host, true))
        assertFalse(HubWifiNavigationPolicy.canOpen(destination,
            "https://$host/__caregiver_app__/%", host, true))
    }

    @Test fun provisioningFailsClosedUntilSecurity2IdentityPermitAndProtectedStoreAreReady() {
        val ready = readyEvidence()
        assertTrue(HubWifiProvisioningGate.canRequestHubScan(ready))
        assertTrue(HubWifiProvisioningGate.canSubmitCredentials(ready))

        listOf(
            ready.copy(securityVersion = null),
            ready.copy(securityVersion = 1),
            ready.copy(security2SessionAuthenticated = false),
            ready.copy(permanentHubIdentityVerified = false),
            ready.copy(oneUseHomePermitVerified = false),
            ready.copy(currentHomeEpoch = false),
        ).forEach {
            assertFalse(HubWifiProvisioningGate.canRequestHubScan(it))
            assertFalse(HubWifiProvisioningGate.canSubmitCredentials(it))
        }
        assertFalse(HubWifiProvisioningGate.canSubmitCredentials(
            ready.copy(selectedNetworkCameFromHubScan = false)))
        assertFalse(HubWifiProvisioningGate.canSubmitCredentials(
            ready.copy(protectedCredentialStoreReady = false)))
    }
}
