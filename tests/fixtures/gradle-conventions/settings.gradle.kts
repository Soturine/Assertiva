pluginManagement {
    includeBuild("build-logic")
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
rootProject.name = "demo-conventions"
include(":app", ":core:data", ":shared")
listOf("feature-a").forEach { include(":features:$it") }
