# PR #58 — actual briefing content review (not deployment acceptance)

## Authority and boundaries

Read the current Google Drive `00_长期上下文` (modified 2026-11-10 14:40 UTC),
especially the locked section 0 and sections 3/10. The user's latest request
supersedes the earlier instruction to print every applicable manual record.
No merge, production dispatch, login, OTP or calendar work is authorized here.

Template: personal information/recency → latest PF/PM feedback → sourced typical
events → airport core threats, in actual operating order. No overall-risk or
generic-enroute-risk section, list numbering or airport-internal topic headings.

## Root cause and implemented changes

`source_verbatim` was doing two different jobs: preserving source wording and
bypassing briefing selection. `prepare_operational_facts` returned every
applicable source record, and `bilingual_typical_facts` bypassed its representative
selection entirely. Independent English selection had the same all-records behavior.

- All three now use a common source-preserving selection pass.
- Typical events are chosen by role and distinct event mechanism (normally 2–3).
  Exceptional mandatory-control/critical records remain protected. No invented
  event or padding when a source has fewer events.
- Core content has no arbitrary count/length ceiling: distinct restrictions,
  numbers, runway/procedure conditions, special performance and control measures
  survive. Routine runway dimension catalogues without a distinct restriction,
  empty reference-only paragraphs and literal duplicates do not automatically
  become briefing paragraphs.
- A table with inconsistent/unbound bilingual data is not treated as safely
  redundant. PAPI/source-conflict evidence remains in PREVIEW and still blocks
  RELEASE. Missing English is not filled by an automatic translation.
- Every new exclusion records the source text, source ID, page, section and
  reason. English applicability/duplicate exclusions now retain the same trace.
- Renderer removes list decoration without modifying decimal values, procedure
  references or action order; whole English word-boundary repair `itflies` →
  `it flies` changes whitespace only. Original source fields are untouched.
- An incomplete English airport section is explicitly marked in the copy payload.
  The acceptance report no longer labels file existence as bilingual completeness.

## Actual pages and copy payload

Read both original `crew-pr58-deployment-acceptance/{date}/copy.html` files,
including their entire textareas and copy handlers. Opened the original pages
in an isolated headless Edge context and clicked all four copy buttons against
a mocked clipboard; each copied exactly its displayed textarea. No production
profile, authentication or actual user clipboard was used.

New isolated outputs are under the local temporary directory
`crew-pr58-content-acceptance-final/{date}/`: `copy.html`, complete
`PREVIEW_group_01_zh.txt`, `PREVIEW_group_01_en.txt`, `preview_meta.json`,
`review.md` and `source_review_queue.json`. The original samples are preserved.

Input snapshot: `2cded5f669e845efb498f5f4551a72de9a8f90df`.
Manual: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.

## Before / after content audit

| Item | Before | After / safety boundary |
|---|---|---|
| Personal fields | 93 hours / 21 landings; 90-day and 30-day each 8; last landing 2026-10-01 | Unchanged; Pudong/Hongqiao excluded only from airport-recency sentence, not last landing |
| Typical events, Nov 13 | Pudong 2, Sanya 3 | Same sourced relevant events; no synthetic additional event |
| Typical events, Nov 14 | Pudong 2, no reliable Dongying event | Same; no invented Dongying event |
| Plain runway dimension table | Entire catalogue printed in both languages | Removed only when it adds no operating restriction and its known bilingual data are consistent; original retained in exclusions |
| Empty radio-failure/noise/depressurization references | Standalone paragraphs pointing elsewhere, no actual procedure content | Excluded with exact source/reason; real instructions, controls and EOSID references protected |
| `itflies` | English OCR join | `it flies`, original and all identifiers/numbers preserved |
| Numbered source paragraphs | Renderer could leak printed list ordinals | Removed in both languages; consecutive inline lists keep original order and paragraph spacing; decimals/references tested |
| PAPI table | Runway/value association conflict | Still visible and UNVERIFIED; not deleted to manufacture success |
| Dongying English | Only Pudong text, despite a second airport in the duty | Copy payload now explicitly says INCOMPLETE ENGLISH PREVIEW / ZSDY |
| Bilingual acceptance field | Misleading `complete_bilingual_groups=true` based on file existence | Required-language content completeness false for Nov 14, while atomic-release protection separately verified |

The new two-day review retained 31 CN / 30 EN selected source records on Nov 13
(previously 33 / 34), and 40 CN / 17 EN on Nov 14 (previously 41 / 18).
These counts are **not a quality target**. Most retained paragraphs are distinct
conditional restrictions or procedures for a return trip that uses both airport
roles. This is deliberately conservative pruning, not a claimed drastic summary.
Unknown runway/clearance conditions remain conditional; no runway is guessed.

## Content review and remaining blockers

Read all four resulting language texts, not just metadata. Both Chinese files
have the fixed template and full profile/feedback. Actual source-specific
SID changes, TCAS, unstable/high approaches, taxi guidance, RNAV/altimeter
checks, runway conditions and relevant route clearances remain. No arbitrary
cap removed their values/sequence. Pure pointer paragraphs and the plain runway
catalogue are gone. Source conflict tables intentionally remain lengthy in the
review draft; their inclusion is evidence, not approval for operational use.

- **Nov 13, 9C8801/9C8802:** PREVIEW / FAILED_SAFE. One blocker: ZSPD PAPI
  runway-to-distance/angle/MEHT association, Chinese page 586 / English page 1367.
- **Nov 14, 9C6687/9C6688:** PREVIEW / FAILED_SAFE. Three validation errors:
  the same PAPI conflict, missing reliable ZSDY English core material, and the
  resulting empty English airport section. The latter two report one underlying
  source gap; this is **not** a complete bilingual draft.
- No new authoritative PAPI data or reviewed Dongying English was obtained in
  this content-only task. No operating value, translation or source approval
  was fabricated. Exact authority requests remain in `pr58-review-reuse.md`.

Both days keep the existing continuous-flight grouping. Nonconsecutive group
regressions still require independent full templates. Both isolated failed
release attempts retain dated/latest last-good text byte-for-byte and create no
`.success`. PREVIEW copy buttons remain explicitly NOT FOR RELEASE.

## Validation evidence

The focused content/source/format/preview tests passed (175 tests). They check
actual preserved instructions/values, decimal/negation/condition counterexamples,
source exclusion reasons, no ordinal leakage, protected constraints, distinct
event selection, missing English warnings and copying/rollback behavior.
Full-suite and CI results are reported only when their runs actually finish.

This report is not a content-release certificate. PR #58 remains Draft; neither
of these two dates is approved as a formal operational briefing.
