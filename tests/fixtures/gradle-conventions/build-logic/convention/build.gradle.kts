plugins {
    `kotlin-dsl`
}

gradlePlugin {
    plugins {
        register("androidLibrary") {
            id = "demo.android.library"
            implementationClass = "AndroidLibraryConventionPlugin"
        }
    }
}
