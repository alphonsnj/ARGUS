# Sprint 3 local validation checkpoint — 2026-09-17

## Results

| Check | Result |
| --- | --- |
| API regression and live integration suite | 18 passed |
| API Ruff and strict mypy | Passed; 27 source files type-checked |
| Web lint and TypeScript | Passed |
| Docker API, worker, and Next.js production builds | Passed |
| DOCX, PNG OCR, scanned-PDF OCR, extraction and search | Passed against live services |
| EICAR test signature in DOCX | Rejected; no promoted object key, extracted text, or entities |
| Cross-user document read/list/search/retry and ordinary-user admin access | Denied |
| Redis stopped during upload | Accepted upload completed via database reconciliation |
| Worker SIGKILL while processing | Accepted upload recovered after restart |
| PostgreSQL stopped after upload acceptance | API 503 while unavailable; document completed after restart |
| Chrome desktop and 390px mobile workflow | Login, upload, automatic status, search, retry, logout and protected-route redirect passed |
| Browser page errors and horizontal overflow | None in tested workflow |
| npm audit | Zero reported vulnerabilities at time of check |
| Alembic | 20260829_0002 at head |

Outages ran only in the separate `argus-validation` Compose project. Tests used
temporary identities and generated evidence; existing administrator credentials
were not used or reset. Test records were cleaned up. Screenshots were visually
reviewed at `/tmp/argus-qa-desktop.png` and `/tmp/argus-qa-mobile.png`.

## Issues fixed during this pass

- Redis publication failure could strand a committed queued upload. The worker
  now reconciles queued/processing database rows under advisory locks even when
  Redis is unavailable, and retries dependency failures without exiting.
- Logout returned a Response with no status code. It now explicitly returns 204
  and clears the refresh cookie after revocation.
- The Documents page lacked search/retry controls and automatic status refresh.
  These now use the existing authenticated API. Request ordering avoids stale
  search results replacing newer results.
- Mobile metadata/grid overflow and the hidden mobile sign-out control were fixed.
  The frontend-design skill guided labeled controls and responsive/accessibility
  fixes while retaining the existing dark/mint design.
- Authentication-service and logout network failures now produce visible feedback.
- CI attempted to install a nonexistent dev extra. It now installs the declared
  dependency group and supplies non-secret example settings for unit tests.
- Next.js was updated to 15.5.25 and the sharp override to 0.35.4 following the
  audit findings. See the [Next.js advisory](https://github.com/advisories/GHSA-p293-qw3h-jr36)
  and [sharp advisory](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c).

## Scope of confidence

This is a working local checkpoint, not a claim of production readiness or a
completed independent security review. The outage tests cover specific process
and container failures, not disk loss or every distributed failure window.
The reported Python coverage excludes the separately running API/worker processes
and should not be interpreted as full live-service coverage.

See [repeatable verification and deployment limits](ingestion-verification.md).
GitHub Actions was corrected but has not been run on GitHub in this checkpoint.
No push or deployment was performed.
