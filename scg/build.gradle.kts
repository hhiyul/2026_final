import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

plugins {
    // 1. Spring Boot 3.2.x 계열은 매우 안정적입니다.
    id("org.springframework.boot") version "3.2.4"
    // 2. Gradle 8.x와 호환되는 버전으로 낮춤
    id("io.spring.dependency-management") version "1.1.4"
    kotlin("jvm") version "1.9.23"
    kotlin("plugin.spring") version "1.9.23"
}

group = "org.example"
version = "0.0.1-SNAPSHOT"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

// 3. Spring Boot 3.2.x와 완벽히 호환되는 Cloud 버전
extra["springCloudVersion"] = "2023.0.0"

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-reflect")

    // Netty 기반의 고성능 게이트웨이
    implementation("org.springframework.cloud:spring-cloud-starter-gateway")
    implementation("org.springframework.cloud:spring-cloud-starter-loadbalancer")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

dependencyManagement {
    imports {
        mavenBom("org.springframework.cloud:spring-cloud-dependencies:${property("springCloudVersion")}")
    }
}

tasks.withType<KotlinCompile> {
    kotlinOptions {
        freeCompilerArgs = listOf("-Xjsr305=strict")
        jvmTarget = "21"
    }
}

tasks.withType<Test> {
    useJUnitPlatform()
}