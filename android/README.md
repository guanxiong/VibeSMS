# VibeSMS Android Terminal

VibeSMS Terminal turns an Android 10+ phone into a private SMS and incoming-call endpoint for an Agent. The app accepts a one-time VibeSMS Key, binds the selected SIM, stores the returned device credential in Android Keystore-backed encrypted storage, and uploads events to `https://sms.shareapi.ai`.

## Runtime behavior

- Receives multipart SMS messages and incoming-call state changes.
- Resolves the subscription and SIM slot on dual-SIM devices.
- Persists events in a SQLite outbox before attempting delivery.
- Retries failed uploads with bounded exponential backoff after connectivity returns.
- Schedules a heartbeat and outbox drain at least every 15 minutes.
- Never persists the user Key; only the scoped device upload token is retained.

Android may ask for SMS, phone-state, and call-log permissions. The call-log permission is used only to improve caller-number availability; some devices or carrier builds may still report an incoming caller as unknown.

## Build

The project requires JDK 17 and Android SDK API 36:

```bash
cd android
./gradlew :app:lintRelease :app:assembleDebug
```

Pull requests and pushes to `main` run the same checks in GitHub Actions. Version tags matching `v*` produce an unsigned release candidate plus the official Android signing tool as a short-lived Actions artifact. A maintainer signs the candidate locally and publishes the signed APK with `SHA256SUMS` in GitHub Releases, so the private release key never leaves the maintainer machine.

## First connection

1. Install the signed APK from GitHub Releases.
2. Grant the requested permissions and exempt VibeSMS from aggressive battery optimization if the phone vendor offers that setting.
3. Enter a Key issued by the VibeSMS administrator.
4. Select the intended SIM and tap **Connect terminal**.
5. Use **Sync now** to confirm that the queue drains and the cloud status updates.

Reconnecting the same Key, device, and SIM rotates the device token, which allows a clean reinstall without requiring an administrator to unbind the number first.
