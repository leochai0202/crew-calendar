# Preparation publication recovery

Production evidence: Nov 20 run **44233727202**, job **134564716615**, generated SUCCESS and uploaded the artifact before failing publication. The generated commit was based on eaf78ed; scheduler commit a095f4a independently added `2026-11-20_meta.json`. Rebase failed with add/add. Main retained only `generation_attempt`, so the old checker suppressed recovery indefinitely.

Nov 19 run **44267211099**, job **134674610422**, likewise passed generation/upload and failed the commit step. Its artifact is PARTIAL_RELEASE, not all-group approval.

## Repair boundaries

Both calendar/scheduler and preparation use `crew-calendar`, `cancel-in-progress: false`, `queue: max`. GitHub's bounded queue retains up to 100 pending runs, rather than silently replacing one pending run; it does not guarantee unlimited queuing. Cron, login, OTP, scraper, ICS rules and FlightHub are untouched.

The preparation publisher builds one commit on the freshly fetched main tree with an isolated index and a non-force push. It permits only an intervening receipt-only dated-state edit; any changed formal output blocks. It does not rebase generated JSON. Newer concurrent latest metadata is retained. Relevant code/config/manual/ICS edits stop stale publication. Three attempts maximum; a missing push response is reconciled by checking commit ancestry. It stages only validated dated/group outputs and metadata, never arbitrary historical files, experience state or `.success`.

Accepted dispatch receipts have a two-hour publication grace, attempt count and AWAITING_PUBLICATION state. Missing publication then permits at most three total attempts per task/input identity, followed by RECOVERY_EXHAUSTED. Actual FAILED_SAFE for the same inputs remains suppressed, not misrepresented as published. New inputs/tasks remain eligible.

## Actual artifact audit (no regeneration)

The immutable uploaded artifacts were downloaded and tested with the real headless copy-button verifier. Both dates' task fingerprints and entire generation-input manifests matched the current repo sources before recovery. The original-source copy format, personal introduction, PF/PM paragraphs and copy payload were checked.

| Date / artifact run | Business state | Actual copy test | Formal eligibility |
|---|---|---|---|
| 2026-11-20 / 44233727202 | SUCCESS | Two buttons passed | 9C6353 / 9C6354, one continuous group, Chinese validated |
| 2026-11-19 / 44267211099 | PARTIAL_RELEASE | Four buttons passed | Only 9C7604Y eligible; 9C7603Y / 9C7604X remains FAILED_SAFE |

The Nov 19 blocked group is the existing Changchun PAPI runway/value association conflict (Chinese p288 / English p1096). PAPI is excluded from copy text but the source-review guard remains; this PR does not choose operating data or waive any safety check. Both complete original-copy groups remain available. Copies are MANUAL_ORIGINAL_NOT_RELEASE, not company operational approval.

Automated regression covers receipt add/add, published-output conflict refusal, stale inputs, concurrent unrelated main updates, lost push responses without duplicate publication, protected historical body, bounded recovery and safe workflow queuing. Exact final local/CI results and production recovery SHAs are reported in the PR after all gates complete.
