plugins {
    kotlin("multiplatform") version "2.4.20"
}

kotlin {
    jvm()
    js { nodejs() }
    iosArm64()
    iosSimulatorArm64()

    sourceSets {
        commonTest.dependencies { implementation(kotlin("test")) }
    }
}
