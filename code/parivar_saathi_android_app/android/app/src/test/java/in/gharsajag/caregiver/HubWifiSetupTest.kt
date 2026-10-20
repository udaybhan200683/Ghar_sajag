package `in`.gharsajag.caregiver

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HubWifiSetupTest {
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
}
