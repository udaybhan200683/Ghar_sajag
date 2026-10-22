import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val sourceRevision = providers.environmentVariable("GITHUB_SHA").orNull
    ?.takeIf { it.matches(Regex("[0-9a-fA-F]{40}")) }
    ?.take(12)
    ?: "local"

val gs179LocalLanTestOnly = providers.gradleProperty("gs179LocalLanTestOnly")
    .orNull?.toBooleanStrictOrNull() ?: false

fun configuredBackendOrigin(propertyName: String, allowTestOnlyLanEndpoint: Boolean = false): String {
    val raw = providers.gradleProperty(propertyName).orNull?.trim().orEmpty()
    if (raw.isEmpty()) return ""
    val uri = try { URI(raw) } catch (_: Exception) {
        throw GradleException("$propertyName must be an HTTPS origin")
    }
    val host = uri.host?.lowercase() ?: throw GradleException("$propertyName must contain a DNS host")
    val labels = host.split('.')
    val dnsLabel = Regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    val privateIpv4 = run {
        val octets = host.split('.')
        if (octets.size != 4 || octets.any { !it.matches(Regex("0|[1-9][0-9]{0,2}")) }) false
        else {
            val values = octets.map { it.toIntOrNull() ?: 256 }
            values.all { it in 0..255 } && (
                values[0] == 10 ||
                    (values[0] == 172 && values[1] in 16..31) ||
                    (values[0] == 192 && values[1] == 168)
                )
        }
    }
    val localMdnsName = host.matches(Regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.local$"))
    val validHost = if (allowTestOnlyLanEndpoint) privateIpv4 || localMdnsName else {
        labels.size >= 2 && labels.all { dnsLabel.matches(it) } &&
            labels.last().length >= 2 && labels.last() !in setOf("local", "localhost", "test", "example", "invalid")
    }
    if (!uri.scheme.equals("https", ignoreCase = true) || uri.rawUserInfo != null ||
        uri.rawQuery != null || uri.rawFragment != null || uri.port !in setOf(-1, 443) ||
        uri.rawPath !in setOf("", "/") || !validHost
    ) throw GradleException("$propertyName must be an HTTPS origin without path, credentials, query, fragment, or custom port")
    if (allowTestOnlyLanEndpoint && !privateIpv4 && !localMdnsName) {
        throw GradleException("$propertyName must be a private IPv4 or single-label .local hostname for the GS-179 LAN TEST_ONLY profile")
    }
    return "https://$host/"
}

val caregiverDebugOrigin = configuredBackendOrigin(
    "caregiverDebugBackendOrigin",
    allowTestOnlyLanEndpoint = gs179LocalLanTestOnly,
)
if (gs179LocalLanTestOnly) {
    val lanTrustConfig = file("src/gs179LocalLan/res/xml/network_security_config.xml")
    val lanManifest = file("src/gs179LocalLan/AndroidManifest.xml")
    val trustConfigText = if (lanTrustConfig.isFile) lanTrustConfig.readText() else ""
    val testCaInBaseConfig = Regex("(?s)<base-config[^>]*>.*?<certificates\\s+src=\"@raw/gs179_local_lan_test_ca\"\\s*/>.*?</base-config>")
        .containsMatchIn(trustConfigText)
    if (!testCaInBaseConfig ||
        !lanManifest.isFile ||
        !lanManifest.readText().contains("android:networkSecurityConfig=\"@xml/network_security_config\"") ||
        !file("src/gs179LocalLan/res/raw/gs179_local_lan_test_ca.pem").isFile
    ) {
        throw GradleException("GS-179 LAN TEST_ONLY profile must trust only its bundled test CA in the app network-security configuration")
    }
}
val caregiverReleaseOrigin = configuredBackendOrigin("caregiverReleaseBackendOrigin")
val pilotKeyPath = System.getenv("GS177_KEYSTORE_PATH")
val pilotKeyPassword = System.getenv("GS177_KEYSTORE_PASSWORD")
val pilotAlias = System.getenv("GS177_KEY_ALIAS")
val pilotAliasPassword = System.getenv("GS177_KEY_PASSWORD")
val pilotSigningConfigured = listOf(pilotKeyPath, pilotKeyPassword, pilotAlias, pilotAliasPassword).all { !it.isNullOrBlank() }

android {
    namespace = "in.gharsajag.caregiver"
    compileSdk = 35
    defaultConfig {
        applicationId = "in.gharsajag.caregiver"
        minSdk = 26
        targetSdk = 35
        versionCode = 3
        versionName = "0.4.0-connected-lite-staging"
        buildConfigField("String", "SOURCE_REVISION", "\"$sourceRevision\"")
        buildConfigField("boolean", "FCM_ENABLED", "false")
    }
    signingConfigs {
        if (pilotSigningConfigured) create("pilot") {
            storeFile = file(pilotKeyPath!!)
            storePassword = pilotKeyPassword!!
            keyAlias = pilotAlias!!
            keyPassword = pilotAliasPassword!!
        }
    }
    buildTypes {
        getByName("debug") {
            buildConfigField("String", "BACKEND_ORIGIN", "\"$caregiverDebugOrigin\"")
            buildConfigField("boolean", "DEV_ENDPOINT_CONFIG_ALLOWED", "true")
            buildConfigField("boolean", "GS179_LOCAL_LAN_TEST_ONLY", gs179LocalLanTestOnly.toString())
            // The laptop LAN profile is always an installable TEST_ONLY build;
            // never sign it with the owner-controlled pilot key.
            if (pilotSigningConfigured && !gs179LocalLanTestOnly) {
                signingConfig = signingConfigs.getByName("pilot")
            }
        }
        getByName("release") {
            buildConfigField("String", "BACKEND_ORIGIN", "\"$caregiverReleaseOrigin\"")
            buildConfigField("boolean", "DEV_ENDPOINT_CONFIG_ALLOWED", "false")
            buildConfigField("boolean", "GS179_LOCAL_LAN_TEST_ONLY", "false")
        }
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets.getByName("main").assets.srcDir(file("../../../tools/sim/pwa"))
    if (gs179LocalLanTestOnly) {
        sourceSets.getByName("debug").manifest.srcFile(file("src/gs179LocalLan/AndroidManifest.xml"))
        sourceSets.getByName("debug").res.srcDir(file("src/gs179LocalLan/res"))
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    testImplementation("junit:junit:4.13.2")
}
