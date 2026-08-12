# VibeSMS Android Terminal

VibeSMS Terminal turns an Android 10+ phone into a private SMS and incoming-call endpoint for an Agent. The app accepts a one-time VibeSMS Key, binds the selected SIM, stores the returned device credential in Android Keystore-backed encrypted storage, and uploads events to `https://sms.shareapi.ai`.

## Runtime behavior

- Receives multipart SMS messages and incoming-call state changes.
- Resolves the subscription and SIM slot on dual-SIM devices.
- Persists events in a SQLite outbox before attempting delivery.
- Retries failed uploads with bounded exponential backoff after connectivity returns.
- Sends a Doze-aware heartbeat about every 9 minutes, with the 15-minute JobScheduler path retained as a fallback.
- Uses a short, bounded wake lock only while a lock-screen heartbeat is in flight.
- Encrypts both the scoped device upload token and each bound inbox Key with Android Keystore.

Android may ask for SMS, phone-state, and call-log permissions. The call-log permission is used only to improve caller-number availability; some devices or carrier builds may still report an incoming caller as unknown.

## License

The Android Terminal source in this directory is licensed under [Apache-2.0](LICENSE). It communicates with the separately licensed VibeSMS service; this license does not grant rights to deploy, copy, modify, or offer the service-side code.

## Build

The project requires JDK 17 and Android SDK API 36:

```bash
cd android
./gradlew :app:lintRelease :app:assembleDebug
```

Pull requests and pushes to `main` run the same checks in GitHub Actions. Version tags matching `v*` produce an unsigned release candidate plus the official Android signing tool as a short-lived Actions artifact. A maintainer signs the candidate locally and publishes the signed APK with `SHA256SUMS` in GitHub Releases, so the private release key never leaves the maintainer machine.

Maintainers with the ignored `signing/` material can run the non-logging local helper:

```bash
JAVA_HOME=/path/to/jdk-17 ./scripts/build-signed-release
```

## First connection

### Agent-assisted USB setup

After saving the user Key as the local `VIBESMS_KEY` Secret, connect and unlock the phone, approve USB debugging, and run the bundled Skill workflow:

```bash
python3 skills/vibesms/scripts/setup_android.py --sim-slot 1
```

The script downloads the signed v0.4.9 APK and `SHA256SUMS`, verifies it, installs it, grants required runtime permissions, adds the terminal to the Doze allowlist when the device permits it, invokes a receiver protected by Android's shell-only `DUMP` permission, and verifies the Key-scoped cloud status. Use `--sim-slot 2` only after explicitly choosing the second active SIM. The user Key is encrypted by Android Keystore and is never printed by the script.

### Manual setup

1. Install the signed APK from GitHub Releases.
2. Grant the requested permissions and exempt VibeSMS from aggressive battery optimization if the phone vendor offers that setting.
3. On Huawei devices, use the in-app **Huawei lock-screen keepalive check** to open App launch and Battery settings. The standard Android battery exemption is detected automatically; Huawei's App launch and sleep-network switches require manual confirmation because the vendor does not expose reliable read APIs to third-party apps. If successful heartbeats stop for more than 20 minutes, the app asks the user to review both settings.
4. Enter a Key issued by the VibeSMS administrator.
5. Select the intended SIM and tap **Connect terminal**.
6. Use **Sync now** to confirm that the queue drains and the cloud status updates.

Reconnecting the same Key, device, and SIM rotates the device token, which allows a clean reinstall without requiring an administrator to unbind the number first.
