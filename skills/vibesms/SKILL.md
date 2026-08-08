---
name: vibesms
description: Read a Key-scoped VibeSMS inbox, check an Android SMS terminal, and wait for verification codes or call events. Use when an agent needs to receive SMS/OTP or inspect inbound call records through sms.shareapi.ai or a self-hosted VibeSMS instance.
---

# VibeSMS

Use the bundled client to access only the phone number assigned to `VIBESMS_KEY`.
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
