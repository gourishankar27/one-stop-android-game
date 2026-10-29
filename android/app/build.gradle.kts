import org.jetbrains.kotlin.gradle.dsl.JvmTarget

import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.onejob.game"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.onejob.game"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            buildConfigField("String", "WS_ENDPOINT", endpointLiteral("oneJobDebugWsUrl"))
            val cleartext = providers.gradleProperty("oneJobAllowDebugCleartext").orElse("false").get()
            require(cleartext in setOf("true", "false")) { "oneJobAllowDebugCleartext must be true or false" }
            buildConfigField("boolean", "ALLOW_DEBUG_CLEARTEXT", cleartext)
        }
        release {
            isMinifyEnabled = false
            buildConfigField("String", "WS_ENDPOINT", endpointLiteral("oneJobReleaseWsUrl", release = true))
            buildConfigField("boolean", "ALLOW_DEBUG_CLEARTEXT", "false")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets.getByName("test").resources.srcDir(rootProject.file("../docs/protocol-fixtures"))
}

fun endpointLiteral(property: String, release: Boolean = false): String {
    val value = providers.gradleProperty(property).orElse("").get()
    if (value.isNotEmpty()) {
        val uri = runCatching { URI(value) }.getOrNull()
        require(uri != null && uri.host != null && uri.rawUserInfo == null && uri.rawQuery == null &&
            uri.rawFragment == null && uri.rawPath == "/ws" &&
            uri.scheme in (if (release) setOf("wss") else setOf("ws", "wss"))) {
            "Endpoint must be a credential-free WebSocket /ws URL (release requires WSS)"
        }
    }
    return "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.navigation:navigation-compose:2.9.5")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-savedstate:2.9.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")

    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test:runner:1.7.0")
    // Compose UI tests otherwise select Espresso 3.5.0, which fails on API 37.
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
