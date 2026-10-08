plugins {
    java
    jacoco
}

java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }

dependencies {
    testImplementation("junit:junit:4.13.2")
}

tasks.test { finalizedBy(tasks.jacocoTestReport) }
tasks.jacocoTestReport { reports { xml.required.set(true) } }
