<!-- kit: community · from the fleet default SECURITY policy (UPS-REPO-14), with fredgar-ai's scope added. -->

# Security Policy

> Which versions of fredgar-ai get security fixes, how to report a vulnerability privately, how fast you will hear back, and what is in scope.

## Supported versions

| Version | Supported |
| --- | --- |
| The latest release on `main` | ✅ |
| Anything older | ❌ |

Security fixes ship as patch releases through release-please ([docs/releasing.md](docs/releasing.md)).

## Reporting a vulnerability

**Do not open a public issue.** Email **amr.abdel@gmail.com** with the subject `fredgar-ai security`. GitHub private vulnerability reporting (**Security → Report a vulnerability**) is not enabled on this repository yet; email is the private channel until it is.

Please include the version or commit, what an attacker can do, and the steps to reproduce.

**Never include live credentials in a report.** Redact any `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, API token, session cookie, database URL or `USER_AGENT_EMAIL` value; describe where a secret leaks rather than pasting it.

## Response window

You will get an acknowledgement **within 7 days**. We then agree a fix timeline with you, and credit you in the advisory unless you ask us not to.

## Scope

In scope:

- The Django + DRF API under [`src/`](src/) (the `/api/v1/` routes, authentication and the `is_staff` write gate, the admin, the static-site generator).
- The Celery workers and the task-status endpoint (`/api/v1/tasks/{id}/`) and their results.
- The Vite/React frontend in [`frontend/`](frontend/) and the nginx image that serves it.
- Handling of secrets and contact data: `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `USER_AGENT_EMAIL` / `SEC_USER_AGENT_EMAIL` and the `X-Sec-User-Agent-Email` header.
- The container images and compose files in this repository.

Out of scope:

- The upstream SEC EDGAR (`data.sec.gov`, `www.sec.gov`) and FRED services themselves; report those to their operators.
- Data accuracy in SEC filings or FRED series, which is not a security issue.
- Vulnerabilities in third-party dependencies with no fredgar-ai-specific exploit path; Dependabot tracks those.
