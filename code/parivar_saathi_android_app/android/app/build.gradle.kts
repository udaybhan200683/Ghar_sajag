plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.gms.google-services")
}

val pwaBaseUrl = (providers.gradleProperty("pwaBaseUrl").orNull ?: "https://example.invalid/").trimEnd('/') + "/"
require(pwaBaseUrl.startsWith("https://")) { "A HTTPS PWA base URL is required" }
require(Regex("^https://[A-Za-z0-9.-]+(?::[0-9]{2,5})?/([A-Za-z0-9_./-]*)$").matches(pwaBaseUrl)) {
    "Invalid PWA base URL"
}

android {
    namespace = "in.gharsajag.caregiver"
    compileSdk = 35
    defaultConfig {
        applicationId = "in.gharsajag.caregiver"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-preproduction"
        buildConfigField("String", "PWA_BASE_URL", "\"$pwaBaseUrl\"")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
}
