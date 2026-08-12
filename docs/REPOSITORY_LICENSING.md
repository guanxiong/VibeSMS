# VibeSMS repository licensing

This repository is source-available as a whole, but it is not wholly open source. Licenses are assigned by directory so that the Android client and Agent Skill can be used independently while the hosted-service implementation remains commercially licensed.

| Scope | License | What it covers |
| --- | --- | --- |
| `android/` | Apache-2.0 | VibeSMS Android Terminal source and its Android-specific documentation/scripts. |
| `skills/vibesms/` | Apache-2.0 | VibeSMS Agent Skill, bundled API client, setup script, and Skill references. |
| Everything else | Commercial / proprietary | Server API, web pages and consoles, service deployment, operational scripts, root configuration, and other files not expressly covered above. |

The Apache-2.0 text is in [../licenses/Apache-2.0.txt](../licenses/Apache-2.0.txt); each open directory includes a short `LICENSE` notice. The commercial terms are in [../LICENSE](../LICENSE).

## Publishing split repositories

The source paths remain in this repository so current Android builds and Skill distribution continue to work. For a standalone public mirror, publish only one of the following directory trees with its corresponding `LICENSE` file and the Apache-2.0 text:

- `android/` as the Android Terminal repository;
- `skills/vibesms/` as the VibeSMS Agent Skill repository.

Do not copy `server/`, `deploy/`, `bin/`, root Docker configuration, or root operational documents into those public mirrors without a separate commercial-license decision. The public components can be configured to use `https://sms.shareapi.ai` or a separately authorized compatible service.

## Contribution boundary

Contributions to `android/` and `skills/vibesms/` are intended to be accepted under Apache-2.0. Contributions elsewhere concern proprietary Service Software and require prior written agreement with the maintainer. This document describes repository licensing; it does not replace a contributor agreement or commercial contract.
