# Android app

Kotlin + Jetpack Compose, minSdk 28, target/compile SDK 36, AGP 9, Gradle version catalog (`apps/android/gradle/libs.versions.toml`).

**Status: in progress.** Build configuration and security manifest are in place. Screens and the Gradle wrapper land in the next commit; iOS was prioritised first.

## Security configuration (built)

- `allowBackup=false` and `data_extraction_rules.xml` exclude all app data from cloud backup and device transfer.
- `network_security_config.xml`: HTTPS only. Debug builds alone allow cleartext to `10.0.2.2`/`localhost` for local development.
- Release builds require `saige.apiBaseUrl` to be `https://` (the build fails otherwise).
- Release signing is read from a git-ignored `keystore.properties` or CI secrets (`SAIGE_KEYSTORE_*`), never from the repository.

## Build

```bash
cd apps/android
./gradlew assembleDebug                         # APK → app/build/outputs/apk/debug
./gradlew bundleRelease -Psaige.apiBaseUrl=https://vault.example.com   # AAB
```

## Planned

Compose screens matching iOS (Home, Files, Search, Ask, Settings), BiometricPrompt app lock, `FLAG_SECURE`, Android Keystore token storage, CameraX + ML Kit document scanner, share-target intent filters, an encrypted offline queue, and instrumentation tests.
