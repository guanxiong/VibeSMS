---
name: vibesms
description: Give an AI agent secure, Key-scoped access to SMS, one-time verification codes, Android terminal status, and inbound call records from a user-owned phone. Use when an agent needs to receive SMS/OTP, wait for a fresh verification code, check whether a VibeSMS terminal is online, or inspect call events through sms.shareapi.ai or a self-hosted VibeSMS instance.
---

# VibeSMS

Connect an AI agent to a user-owned Android phone and SIM without exposing the whole SMS inbox. A single `VIBESMS_KEY` gives the agent access only to its assigned phone number and supports four focused actions:

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
