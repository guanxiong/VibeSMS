# VibeSMS Agent API

Base URL defaults to `https://sms.shareapi.ai`. Send the user Key on every request:

```http
Authorization: Bearer vbs_live_...
```

The Key is bound to one phone number and, after Android pairing, one `device_id` plus `sim_slot`. Responses never cross that binding.

## `GET /api/v1/status`

Returns Key metadata, binding state, terminal state, and `cursor`, the highest visible event ID. Capture `cursor` before triggering an external SMS.

## `GET /api/v1/inbox`

Query parameters:

- `after_id`: return events with a larger ID; defaults to `0`.
- `type`: `sms`, `call`, `test`, or empty for all.
- `limit`: 1–200; defaults to 100.

Events are returned oldest first so the response `cursor` can be used for the next read.

## `GET /api/v1/otp/wait`

Query parameters:

- `after_id`: cursor captured before the SMS-triggering action.
- `timeout`: long-poll duration from 0–60 seconds; defaults to 30.

Success returns `status=received`, a 4–8 digit `code`, the new `cursor`, and the source event. A normal no-message result returns `status=timeout` and the latest scanned cursor.

## Security boundary

The Agent API accepts only a user Key. Android event uploads use a separate device Token at `/api/v1/events` and `/api/v1/devices/heartbeat`; do not put device Tokens in Agent Secrets.
