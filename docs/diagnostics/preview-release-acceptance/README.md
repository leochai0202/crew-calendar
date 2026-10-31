# PREVIEW / RELEASE acceptance — Draft PR #58

These are complete **review previews, not approved operational briefings**.
No production workflow, login, OTP or publication was invoked. PR #58 remains
Draft. No main, ICS, profile, workflow YAML or publishing transport was changed.

## Complete bilingual previews

| Real duty date | Chinese | English | Evidence and source metadata |
|---|---|---|---|
| 2026-10-05 | [Full CN](2026-10-05/preview_zh.txt) | [Full EN](2026-10-05/preview_en.txt) | [Review](2026-10-05/review.md), [metadata](2026-10-05/preview_meta.json) |
| 2026-10-26 | [Full CN](2026-10-26/preview_zh.txt) | [Full EN](2026-10-26/preview_en.txt) | [Review](2026-10-26/review.md), [metadata](2026-10-26/preview_meta.json) |
| 2026-10-28 | [Full CN](2026-10-28/preview_zh.txt) | [Full EN](2026-10-28/preview_en.txt) | [Review](2026-10-28/review.md), [metadata](2026-10-28/preview_meta.json) |

The text files include every selected paragraph, inline UNVERIFIED markers and
an appendix containing the original source text and page numbers. Each group
also has separate CN/EN files. The previews retain independent language facts,
not an artificial one-to-one bilingual selection.

Source: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.
Frozen real ICS input: main `915f7bafcde707d5f1f911dffff993a36d561239`.
The authoritative machine-readable results, counts and errors are in
[acceptance.json](acceptance.json).

## Small implementation boundary

- `--mode preview` renders into `agent_output/flight_prep/previews/<date>/`,
  always labels the output PREVIEW, sets `publishable=false`, and returns 3.
  It never writes formal dated/latest files, formal metadata, airport experience
  or a success marker. A stale formal marker cannot turn this exit into a
  successful release step.
- The existing default RELEASE path still performs all source, operating-data,
  applicability and content checks. It now also writes this review sidecar
  before deciding whether release is permitted. Existing always-uploaded
  diagnostics already include `agent_output/flight_prep/`; no new publishing
  infrastructure or workflow behavior was introduced.
- RELEASE errors retain FAILED_SAFE, do not write new formal text, remove the
  current release marker and preserve the dated/latest last-good text. A valid
  isolated RELEASE is tested too; PREVIEW is never itself publishable.
- Fixed template sections contain personal experience, PF/PM feedback, an
  actual-route overview, sourced typical events, core threats, and intact
  en-route/general source paragraphs. No paragraph budget or summary was added.
- Generic fixes preserve parenthesized event headings, wrapped decimal
  frequencies, source-item/runway boundaries, route prefixes and exact
  procedure/altitude anchors. Reviewed translations are immutable source-bound
  data, not runtime translation or airport-specific Python branches. A reviewed
  English paragraph may cite multiple Chinese records only when every original
  record, page and hash binds successfully.
- The workflow inventory test supports the approved main training workflow's
  additional consent/preflight gates and exact ciphertext-only artifact action,
  retaining the earlier login/cleanup/secret guards. No workflow YAML or PR #59
  dependency installation was copied into this PR.

## Explicit remaining limitations — not a release claim

The four previously established operational source categories remain blocked:

| Category | Company Chinese page | Company English page | Required confirmation |
|---|---:|---:|---|
| Guangzhou runway operating allocation | 987 | 1581 | Authoritative direction/runway/arrival/departure mapping |
| W19 OLPAB / OBLAP | 990 | 1582 | Effective authoritative waypoint/route record |
| Speed 180 and distance 8 NM / printed 8 knots | 991 | 1583 | Authoritative speed/distance instruction and units |
| Pudong PAPI runway/value associations | 586 | 1367 | Effective per-runway distance/angle/MEHT table |

The October 5 English source also contains four explicitly named-route records
whose endpoint identity is not yet reliably resolved by the current manual
heading/approved-name registry (English p.1352). They remain visible and marked
in PREVIEW; they now block RELEASE rather than silently masquerading as
generally applicable instructions. This is a program/data applicability issue,
not a fifth company operational-data conflict and not proof that the PDF lacks
the relevant English chapters. No airport identity was guessed to make it pass.

Manual English still contains awkward/unreviewed wording, for example
`three-way approach`, `skidway`, and `single-shot acceleration altitude`.
The complete diagnostic text intentionally exposes these rather than pretending
that a successful render is a professional-English sign-off. The source-bound
corrections in this revision address the verified `13th mountain` regression,
ILS/landing-configuration/taxi-event errors and the listed reviewed records;
they are not a blanket approval of every printed English sentence. Final
professional-language and applicability review is still required for RELEASE.

PR #59 remains separate. Until its dependency change is approved and integrated,
merge-preview CI can fail on main's missing PyMuPDF dependency before Flight
Prep tests run. The actual final CI outcome is reported on PR #58, not assumed
green here.

## Repeatable isolated verification

`scripts/accept_flight_prep_preview.py` uses one disposable workspace, read-only
Git snapshots of the two real ICS files and the actual manual. It verifies
every selected CN/EN fact appears in the complete corresponding preview,
continuous/non-continuous groups, foreign-crew bilingual output, no preview
success marker, no preview writes to formal/config files, and failed-release
last-good preservation. Any RELEASE simulation occurs only in that temporary
workspace, which is removed afterward.

Local and GitHub test results are recorded in the PR delivery report. These
diagnostics do not authorize merging, a production dispatch or operational use.
