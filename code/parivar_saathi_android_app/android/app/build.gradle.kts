plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val sourceRevision = providers.environmentVariable("GITHUB_SHA").orNull
    ?.takeIf { it.matches(Regex("[0-9a-fA-F]{40}")) }
    ?.take(12)
    ?: "local"

android {
    namespace = "in.gharsajag.caregiver"
    compileSdk = 35
    defaultConfig {
        applicationId = "in.gharsajag.caregiver"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-dashboard"
        buildConfigField("String", "SOURCE_REVISION", "\"$sourceRevision\"")
        buildConfigField("boolean", "FCM_ENABLED", "false")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    testImplementation("junit:junit:4.13.2")
}
