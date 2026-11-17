// AGP 9 compiles Kotlin itself (built-in Kotlin), so there is no kotlin-android plugin.
// The classpath entry pins the Kotlin compiler to the same version as the Compose and
// serialization compiler plugins, as the AGP 9 release notes describe.
buildscript {
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.4.21")
    }
}

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.google.services) apply false
}
