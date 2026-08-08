# Security Policy

VibeSMS handles SMS content, phone metadata, device credentials, and Agent access keys. Do not report vulnerabilities in public issues when a report contains secrets, personal data, or an exploitable reproduction.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting or open a private security advisory for `guanxiong/VibeSMS`. Include affected versions, impact, reproduction steps, and a proposed mitigation when available.

Do not include production keys, real phone numbers, SMS bodies, administrator credentials, signing keys, or database snapshots in a report. Use synthetic examples.

## Supported versions

Until the first tagged release, only the latest commit on `main` receives security fixes.

## Secret handling

- Device credentials, Agent keys, administrator passwords, Android signing keys, and `.env` files must never be committed.
- Production data under `data/` and local configuration under `config/local.env` are intentionally ignored.
- A leaked key must be revoked or rotated; removing it from Git history is not sufficient.
