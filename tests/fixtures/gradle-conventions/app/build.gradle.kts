plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "demo.app"
    compileSdk = 35
    flavorDimensions += "tier"
    productFlavors {
        create("free") { dimension = "tier" }
        create("paid") { dimension = "tier" }
    }
}
