---
name: vibesms
description: Set up a user-owned Android phone as a VibeSMS terminal over authorized ADB, then give an AI agent secure, Key-scoped access to SMS, one-time verification codes, terminal status, and inbound call records. Use when an agent needs to install or configure VibeSMS on a USB-connected Android phone, receive SMS/OTP, wait for a fresh verification code, check terminal status, or inspect call events through sms.shareapi.ai or a self-hosted VibeSMS instance.
---

# VibeSMS

Connect an AI agent to a user-owned Android phone and SIM without exposing the whole SMS inbox. A single `VIBESMS_KEY` supports Android setup plus four focused inbox actions:

- Check whether the Android terminal is bound and online.
- Capture an event cursor before an external service sends a message.
- Wait for a fresh 4–8 digit verification code after that cursor.
- Read Key-isolated SMS and inbound call events.

The Android terminal uploads through a separate device credential, so the Agent Key cannot upload events or read another number. Use the bundled client for deterministic API calls.
Resolve `scripts/vibesms.py` relative to this `SKILL.md`; do not assume the current working directory contains the skill.

## Preconditions

- Require `VIBESMS_KEY` in the environment or agent Secret store.
- Use `VIBESMS_BASE_URL` only for a self-hosted instance; it defaults to `https://sms.shareapi.ai`.
- Never ask the user to paste a Key into chat, command arguments, source code, or logs.
- Never expose the Key in output. If it is missing, ask the user to configure the Secret.

## Set up Android over USB

1. Ask the user to connect and unlock the phone, enable USB debugging, and confirm whether to use SIM 1 or SIM 2. Do not guess on a dual-SIM phone.
2. Check that `adb devices` shows exactly one device in the `device` state. If it shows `unauthorized`, ask the user to approve the prompt on the phone.
3. Ensure `VIBESMS_KEY` is available as an environment Secret. Never paste it into chat or a shell command.
4. Run the deterministic installer, which downloads and verifies the signed APK, installs it, grants the required runtime permissions, invokes the ADB-only provisioning receiver, and checks the cloud heartbeat:

   ```bash
   python3 <skill-directory>/scripts/setup_android.py --sim-slot <1-or-2>
   ```

   Add `--serial <adb-serial>` only when more than one authorized device is connected. Use `--apk <signed-apk>` for an explicitly supplied local APK.
5. Report `bound`, `online`, `device_id`, and selected SIM. Do not report the Key or device Token.

The setup receiver is protected by Android's `android.permission.DUMP`, so ordinary applications cannot invoke it. The setup script passes the Key directly to `adb` without a host shell and never prints child command arguments.

## Receive a verification code

1. Capture a cursor immediately before triggering the external SMS:

   ```bash
   python3 <skill-directory>/scripts/vibesms.py status
   ```

2. Read the `cursor` value from the JSON response.
3. Trigger the user-authorized action that sends the SMS.
4. Wait for the first 4–8 digit code received after that cursor:

   ```bash
   python3 <skill-directory>/scripts/vibesms.py wait-otp --after-id <cursor> --timeout 60
   ```

5. Use the code only for the task the user authorized. Do not persist it after completion.

Always capture the cursor first. Without it, an older message could be mistaken for the new verification code.

## Check terminal status

Run:

```bash
python3 <skill-directory>/scripts/vibesms.py status
```

If `bound` is false, tell the user the Key has not been paired with an Android SIM. If `online` is false, explain that messages may still arrive after the terminal reconnects and replays its offline queue.

## Read inbox events

Run one of:

```bash
python3 <skill-directory>/scripts/vibesms.py inbox --after-id <cursor>
python3 <skill-directory>/scripts/vibesms.py inbox --type sms --limit 20
python3 <skill-directory>/scripts/vibesms.py inbox --type call --limit 20
```

Prefer `after-id` for task-specific reads. Return only the fields needed for the user's task; avoid repeating unrelated message content or phone numbers.

## Errors

- `401`: the Key is invalid, disabled, or rotated. Ask the user to update the Secret.
- `status=timeout`: no matching OTP arrived in time. Check terminal status, then retry only if the user still wants to wait.
- Network/TLS failure: report the endpoint and failure without printing headers or the Key.

Read [references/api.md](references/api.md) only when raw endpoint schemas or self-hosted integration details are needed.

## License

This Skill and the files under its directory are licensed under [Apache-2.0](LICENSE). The VibeSMS service and its deployment code are separately commercially licensed; this Skill license does not grant rights to the service-side source code.
