# Complete source-section regression (review only)

Integrated main: `837fe8a8e1eefa985fff7156662a1554ac71296e`. Latest-main real-ICS/experience input and merge-preview base: `8181248e808a8f315a4142085288e275b3898075` (additional upstream generated files are preserved, not edited).
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
- Recurring seasonal source requirements remain complete regardless of the test month, including the printed month/season, risk, values and controls. Explicit operating validity windows, route/role restrictions and administrative exclusions remain active. English month ranges are not mistaken for unverified routes; additional real route clauses in the same paragraph are still checked.
- Reliable ordinary-airport elevation fields are retained without requiring highland classification. This does not infer a highland designation or change the source values.
- Restoring elevations exposed a truncated Chinese chapter heading (`机场运行特` immediately followed by its Latin name and explicit IATA/ICAO pair). The generic boundary detector now recognises that evidenced heading, preventing the next airport's elevation from leaking into the preceding airport. It does not change source values or accept unanchored prose as a chapter.
- A language with reliable core facts but no sourced typical events still retains the fixed empty typical-event heading, without an invented airport/event paragraph. This preserves the existing copy-format contract for newly restored basic fields.

Original-page visual checks: Chinese pages 586 (attribute-table runway assignment and low-visibility exception), 588 (winter low visibility), 949 (parenthetical ATC/deviation restriction and winter/spring wind conditions), 950 (landing deceleration controls and complete recurring month ranges), 1009 (noise/depressurization/radio-failure references). English page 1370 confirms the winter-condition wording. The corresponding English runway-attribute remark is extracted independently from page 1368. No operating data was corrected or translated.

## Actual isolated samples

| Date / real flight group | Chinese source facts | Original English source facts | Copy result | RELEASE |
|---|---:|---:|---|---|
| 2026-11-13 / 9C8801 + 9C8802 / Pudong–Sanya | 41 | 37 | SOURCE_COPY_READY | FAILED_SAFE |
| 2026-11-15 / 9C6617 + 9C6618 / Pudong–Lijiang | 58 | 21 | SOURCE_COPY_READY | FAILED_SAFE |

English for Lijiang was not reliably located; only actual Pudong English is copied on Nov 15. Missing English is not invented. Existing English wording, including questionable company-manual expressions, is not silently corrected. Sanya's original English contains such expressions as `Five-sided Chaos` and an incorrect RVSM expansion; source-copy availability is not approval of their operational accuracy.

Each date directory contains the complete Chinese text, available original English text and `copy.html`. Both real copy buttons were clicked in an isolated local browser; captured clipboard payloads passed the locked-template checks. No real clipboard, login/profile, network authentication or OTP was used.

Compared with PR head `1c69c22`, every prior body paragraph remains present (sometimes inside its restored complete source paragraph). All four text files exactly match their HTML textarea copy payloads. No PAPI/MEHT data, audit-state labels, numbering or extra risk sections enter those payloads. Month ranges such as `1-4` are preserved as source data, not mistaken for list numbering. Restored Lijiang wind, terrain and month-range values were checked against pages 949–950 without changing their conditions or units.

`acceptance.json` records: SOURCE_COPY_READY with exit 0, formal FAILED_SAFE, no `.success`, unchanged last-good sentinels/configuration, exact selected-body fact presence, fixed-format and actual copy-button checks. The generator was exercised in both preview and release modes **only in a disposable directory**.

## Per-source coverage

`coverage.json` lists every reconstructed PDF source record for the three airports, separately by language, source section/phase, source page, source record ID, original text, actual output and exclusion reason. It includes 89 record entries for Nov 13 and 90 for Nov 15; there are no `UNACCOUNTED` records. Counts include repeated source records, not unique paragraphs.

| Airport/language | Source records | Records represented in output | Excluded/audited records |
|---|---:|---:|---:|
| Pudong ZH | 24 | 21 | 3 |
| Pudong EN | 24 | 22 | 2 |
| Sanya ZH | 23 | 20 | 3 |
| Sanya EN | 18 | 16 | 2 |
| Lijiang ZH | 42 | 37 | 5 |
| Lijiang EN | 0 | 0 | 0 |

Exclusions are explicitly recorded: PAPI display policy, inapplicable route, non-operational administration/frequency-only fields, literal duplicates, or invalid source structure. Ordinary-airport elevations and recurring seasonal clauses are no longer excluded. Lijiang positive attributes repeated by the legacy basic-field collector remain in output once. November 13 has 79 output / 10 audited exclusions; November 15 has 80 output / 10 audited exclusions, with no unaccounted reconstructed source records.

The three sample chapters contain no separately matched threat-identification table. Generic threat-table row/phase/control preservation is therefore tested with synthetic table records, not falsely claimed as a real table present in these chapters.

## Remaining review / unchanged safety gates

- Pudong PAPI original source conflict: Chinese page 586 / English page 1367. Background only; still no formal release authorization.
- Lijiang reliable English material is missing from the located chapter set. Chinese copy is complete; English is not fabricated.
- Other manual translations and data remain as printed. This change does not claim to resolve company-source discrepancies.
- The non-continuous/continuous flight grouping implementation, source provenance checks, SOURCE_COPY_READY/RELEASE separation, last-good, and formal publication guard are unchanged. Their existing regression tests remain enabled.

Targeted tests: 207 passed; the real PDF before/after regression also passed separately after checking the page-822 chapter boundary. Full regression and CI results are reported on the PR for the exact tested commit. Two former seasonal-exclusion assertions were updated to require the original winter conditions, prohibition, clearance and instruction sequence instead. No safety checks are skipped. The user authorized Ready/merge after the integration and test gates pass; this does not authorize a manual production dispatch or formal RELEASE of blocked source data.
