# Reusable source reviews — no operational-data approval implied

Reviews remain in `config/flight_prep_chinese_translations.json`. No second approval
database, online translator, scheduled reminder or release allowlist was added.

## Identity and validity

Existing reviews bind ICAO, manual version, source record IDs, both original text
hashes, pages, reviewed English body, reviewer and review date. An optional existing
`authority_evidence` also binds a dated state AIP section and supported-body hash.
No unverified authority URL, effective date or operating value was added this round.

A review can additionally declare `review_scope` with all five fields:

- `effective_from`, `effective_until_exclusive`: ISO dates; end is exclusive.
- `roles`: nonempty subset of `departure`, `arrival`.
- `routes`: directed pairs of ICAO codes; an empty list adds no route restriction.
- `runways`: runway designators covered by the approval; an empty list adds no
  approval restriction. A nonempty list must cover the original fact's explicit
  runway conditions. It never asserts which runway ATC has assigned.

Approval scope is not a new source fact or a reason to delete a fact. Every new duty
rechecks the review and any authority window. Outside approval scope, the original
English remains visible for review, but cannot use the reviewed translation to pass
RELEASE. Ordinary source role/route/season/date filtering still runs and records its
exclusion reasons. Rebinding clears stale in-memory approvals before validating the
current original texts; version/hash/page changes or withdrawal cannot retain one.

Legacy source-only translations remain version/hash-bound. They do not acquire a
fabricated authority expiry or expand an existing AIP validity window. Critical
numeric, runway, waypoint, unit and table conflicts still block even when a review
has a matching scope. Actual controlled evidence is needed before any such
correction can be implemented and accepted; scope metadata alone never clears it.

## Pending evidence, not permission

Each preview artifact now includes `source_review_queue.json`. Stable IDs combine
ICAO, manual version, source identity and original hashes. Repeated groups share one
record; future dates obtain the same ID for the same source problem. A missing
English chapter uses one airport/version-specific review ID, not a demand to pair or
translate every Chinese fact. The file is diagnostic, never imported as authority.

The original evidence and pages remain in `review.md` and `preview_meta.json`.
This does not introduce a persistent cross-run publication service: artifacts carry
stable keys that can be compared/combined without changing the generator or creating
repeated GitHub issues. No notifications are sent.

## Current authority acquisition and unresolved facts

The available `D:/Flight_Data` airport manual is still the 20261019 PDF. The nearby
update bundle is old application code/20260720 text, not new controlled operational
evidence; it was not executed or used to replace current facts.

Official China eAIP `https://www.eaipchina.cn/` and `/dataset` returned only a
JavaScript shell in text retrieval; the read-only browser open timed out. Search
results included historical/mirror/simulator material, which was not accepted as
current authority. No credential, login, OTP or download workaround was attempted.

Still required:

- ZSPD: controlled current PAPI runway-to-distance/angle/MEHT associations, resolving
  company-manual CN586 / EN1367 ambiguity.
- ZSDY: reliable English airport material or separately reviewed exact translations
  grounded in the available Chinese source pages 528–531. No English was invented.
- ZGGG: current direction-dependent runway allocation (CN987 / EN1581), W19 waypoint
  OLPAB versus OBLAP (CN990 / EN1582), and the speed/distance statement with 180 and
  8 NM versus printed 8 knots (CN991 / EN1583).

Until these are resolved, affected groups stay PREVIEW/FAILED_SAFE. Tests of the
approval machinery do not make these operational statements verified.

Latest actual test/CI counts and deployment state are reported separately after the
candidate completes testing; this document does not claim deployment.
