# Complete source-section regression (review only)

Base main: `3e94303e1c81d12dbf87529b845e89c7206a231b`.
Manual: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.

These are isolated **source-copy samples**, not RELEASE or company-approved operating instructions. No workflow was dispatched. The original PDF, ICS, production profile/configuration, formal dated files and latest files were not modified.

## Changes supported by source evidence

- All applicable original incidents are retained. The old representative-three and shortest-same-incident-type selection no longer suppress different source facts.
- Runway data and published-procedure references are not discarded for being catalogue/reference-only entries.
- Positive inherent-attribute table remarks retain wrapped conditions and exceptions. English extraction reads the actual aligned Yes/No/Remarks columns, including remarks above the vertically centred YES label. No airport-specific values or names are in the new parser.
- Complete parenthetical controls are no longer rejected as fragments. Source-only records containing parenthetical sentences stay together instead of losing the explanation at a role/clause boundary.
- Threat/mitigation table rows retain their own departure/arrival scope and controls, without a row quota or cross-phase category aggregation.
- PAPI **data fields** are excluded from both bodies/copy payloads and retained in audit evidence. Operational instructions that merely mention PAPI are not deleted. Existing RELEASE conflict protection remains; removal from display is not authority to clear source review.

Original-page visual checks: Chinese pages 586 (attribute-table runway assignment and low-visibility exception), 949 (parenthetical ATC/deviation restriction), 950 (landing deceleration controls), 1009 (noise/depressurization/radio-failure references). The corresponding English runway-attribute remark is extracted independently from page 1368. No operating data was corrected or translated.

## Actual isolated samples

| Date / real flight group | Chinese source facts | Original English source facts | Copy result | RELEASE |
|---|---:|---:|---|---|
| 2026-11-13 / 9C8801 + 9C8802 / Pudong–Sanya | 38 | 35 | SOURCE_COPY_READY | FAILED_SAFE |
| 2026-11-15 / 9C6617 + 9C6618 / Pudong–Lijiang | 56 | 19 | SOURCE_COPY_READY | FAILED_SAFE |

English for Lijiang was not reliably located; only actual Pudong English is copied on Nov 15. Missing English is not invented. Existing English wording, including questionable company-manual expressions, is not silently corrected. Sanya's original English contains such expressions as `Five-sided Chaos` and an incorrect RVSM expansion; source-copy availability is not approval of their operational accuracy.

Each date directory contains the complete Chinese text, available original English text and `copy.html`. Both real copy buttons were clicked in an isolated local browser; captured clipboard payloads passed the locked-template checks. No real clipboard, login/profile, network authentication or OTP was used.

`acceptance.json` records: SOURCE_COPY_READY with exit 0, formal FAILED_SAFE, no `.success`, unchanged last-good sentinels/configuration, exact selected-body fact presence, fixed-format and actual copy-button checks. The generator was exercised in both preview and release modes **only in a disposable directory**.

## Per-source coverage

`coverage.json` lists every reconstructed PDF source record for the three airports, separately by language, source section/phase, source page, source record ID, original text, actual output and exclusion reason. It includes 89 record entries for Nov 13 and 90 for Nov 15; there are no `UNACCOUNTED` records. Counts include repeated source records, not unique paragraphs.

| Airport/language | Source records | Records represented in output | Excluded/audited records |
|---|---:|---:|---:|
| Pudong ZH | 24 | 19 | 5 |
| Pudong EN | 24 | 20 | 4 |
| Sanya ZH | 23 | 19 | 4 |
| Sanya EN | 18 | 16 | 2 |
| Lijiang ZH | 42 | 37 | 5 |
| Lijiang EN | 0 | 0 | 0 |

Exclusions are explicitly recorded: PAPI display policy, existing ordinary-airport elevation policy, inapplicable season/route, non-operational administration/frequency-only fields, literal duplicates, or invalid source structure. Lijiang positive attributes repeated by the legacy basic-field collector remain in output once. Partial seasonal clauses retain their exclusion reasons alongside the full source original.

The three sample chapters contain no separately matched threat-identification table. Generic threat-table row/phase/control preservation is therefore tested with synthetic table records, not falsely claimed as a real table present in these chapters.

## Remaining review / unchanged safety gates

- Pudong PAPI original source conflict: Chinese page 586 / English page 1367. Background only; still no formal release authorization.
- Lijiang reliable English material is missing from the located chapter set. Chinese copy is complete; English is not fabricated.
- Other manual translations and data remain as printed. This change does not claim to resolve company-source discrepancies.
- The non-continuous/continuous flight grouping implementation, source provenance checks, SOURCE_COPY_READY/RELEASE separation, last-good, and formal publication guard are unchanged. Their existing regression tests remain enabled.

Full test and CI results are reported on the PR for the exact tested commit. No merge or production publication is authorized by this report.
