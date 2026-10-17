import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val sourceRevision = providers.environmentVariable("GITHUB_SHA").orNull
    ?.takeIf { it.matches(Regex("[0-9a-fA-F]{40}")) }
    ?.take(12)
    ?: "local"

fun configuredBackendOrigin(propertyName: String): String {
    val raw = providers.gradleProperty(propertyName).orNull?.trim().orEmpty()
    if (raw.isEmpty()) return ""
    val uri = try { URI(raw) } catch (_: Exception) {
        throw GradleException("$propertyName must be a public HTTPS origin")
    }
    val host = uri.host?.lowercase() ?: throw GradleException("$propertyName must contain a DNS host")
    val labels = host.split('.')
    val dnsLabel = Regex("^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if (!uri.scheme.equals("https", ignoreCase = true) || uri.rawUserInfo != null ||
        uri.rawQuery != null || uri.rawFragment != null || uri.port !in setOf(-1, 443) ||
        uri.rawPath !in setOf("", "/") || labels.size < 2 || labels.any { !dnsLabel.matches(it) } ||
        labels.last().length < 2 || labels.last() in setOf("local", "localhost", "test", "example", "invalid")
    ) throw GradleException("$propertyName must be a public HTTPS origin without path, credentials, query, fragment, or custom port")
    return "https://$host/"
}

val caregiverDebugOrigin = configuredBackendOrigin("caregiverDebugBackendOrigin")
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
            if (pilotSigningConfigured) signingConfig = signingConfigs.getByName("pilot")
        }
        getByName("release") {
            buildConfigField("String", "BACKEND_ORIGIN", "\"$caregiverReleaseOrigin\"")
            buildConfigField("boolean", "DEV_ENDPOINT_CONFIG_ALLOWED", "false")
        }
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets.getByName("main").assets.srcDir(file("../../../tools/sim/pwa"))
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    testImplementation("junit:junit:4.13.2")
}
