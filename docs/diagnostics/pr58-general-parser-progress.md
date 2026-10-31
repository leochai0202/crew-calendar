# PR #58 — generic parser follow-up (DRAFT, not release acceptance)

## Source and isolation

Authoritative source: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.
Real-duty input was read from main `c142ed97e1a9fb2b97c40270704a8606a6c1288e` into temporary directories; checkout ICS files were not changed. No production workflow, authentication, OTP, manual sync or publisher was executed.

This report supersedes the previous revision's counts, not its historical evidence. It does **not** claim all-airport bilingual acceptance or merge readiness.

## Generic mechanisms changed

- English headings accept mixed case, code-only headings and same-page Basic Information ICAO/IATA metadata. Binding remains exact ICAO; another airport's metadata cannot be borrowed. Multiple same-ICAO chapters can be read. A typical-event heading must be an explicit heading, not a prose mention.
- Chinese and English section mappings preserve operational/special/other sections. Numbered items, inline list markers, conditional parents and page continuations retain source boundaries. Decimal slopes are not list ordinals. Numbered dates lose only the list marker, not the date.
- Basic-information duplicates are deduplicated by field and actual source value before pairing. Matching uses category, phase, order, critical anchors and bounded procedure concepts, retaining ambiguity/gaps. No translation or English prose editor is used.
- Complete administrative sentences can be removed without deleting adjacent refuelling boarding/fire-cover restrictions. Bare frequency tables are distinct from operational radio/PDC/contact instructions. Passport/customs transport and jet-bridge codes are not flight-deck facts.
- Mixed-role source records can split into independently supported clauses under one parent source identity. Dependent condition continuations stay with the parent; an independent explicit role change terminates the preceding inherited condition. Role applicability remains mandatory.
- Explicit operating date windows and directional routes are evaluated against the duty; event-history routes do not become restrictions. No airport/date/flight-specific production branch was added.
- Comparison-only normalization handles extraction spacing and equivalent units/actors. Changed distances, waypoint spelling conflicts, wrong aviation concepts, readback polarity and missing English remain failures. Rendered source text is not rewritten to match the comparison.
- Source page mapping supplies precise physical pages when uniquely locatable; ambiguous cases retain chapter ranges, not invented page numbers. Removed administrative original sentences remain in provenance.

## All-airport structural inventory

[Inventory](all-manual-chapter-structure.json): 177 Chinese chapters, 79 English chapters, 76 Chinese chapters with exact-ICAO English matches, zero cross-ICAO identity errors. Every recognized Chinese chapter was structurally scanned. This does not establish that unmatched chapters have no English, nor that matched chapters are semantically complete.

Real source previews additionally cover Shenyang, Nanjing and Xiamen. Separate departure/arrival ID lists and original-language paragraphs are included in the audit files. These samples still expose unresolved issues; they are not reported as successful production briefings.

## Real isolated acceptance

| Duty date | Current errors | Status | Last-good preserved | Success marker |
|---|---:|---|---|---|
| 2026-10-26 | 16 (baseline 44) | FAILED_SAFE | true | absent |
| 2026-10-28 | 25 | FAILED_SAFE | true | absent |

The October 26 selection contains 89 group-fact instances: 84 source-backed English counterparts and 5 missing counterparts. Generic fallback and generated translation remain zero. Source-backed does not mean bilingual validation passed. The two non-continuous flight groups remain independent and both require English; no incomplete formal output was published.

[Every one of the original 44 errors](pr58-bilingual-error-review.md) and [full candidate evidence](pr58-bilingual-error-review.json) include source identity, Chinese/English texts, pages, phases, token sets, same-/other-phase English candidates in original order, and current outcomes. Twenty-one baseline error instances now have validated counterparts. Four unselected instances are explicitly not counted as paired fixes: two administrative stair/escalator instances and two other-route instances. Two parity errors remain derived failures. Seventeen baseline instances remain unresolved, and are not all claimed to be genuine source gaps.

[October 26 complete rendered diagnostic samples](source-only-manual-audit.md) and [October 28 samples](source-only-20261028-audit.md) contain both languages and role previews. They are prominently labelled FAILED_SAFE diagnostics, not sendable briefings.

## Source evidence and blockers

| Item | Physical pages and evidence | Classification / disposition |
|---|---|---|
| W19 waypoint | Chinese 990: `MASGU-UPMIP-ATKAV-OLPAB-NOMAR`; English 1582: `MASGU-UPMIP-ATKAV-OBLAP-NOMAR`. Same W19 item; English page visually reviewed. | SOURCE_CONFLICT. Neither spelling selected; guard remains active. |
| STAR/runway confirmation | Chinese 313 Command Characteristics (4): `曼谷进近只给出进场STAR程序，不告知跑道…建立五边之前务必证实跑道和进近方式`. English 1169 has (1)–(3), then Pavement Characteristics; 1170 continues pavement. Full English chapter 1169–1182 text search has not found a reliable counterpart. | Corresponding-location discrepancy supported by page review; no claim of definitive entire-PDF absence. No translation/borrowed item. |
| Lijiang English chapter | Chinese 946–951, departure card 203; no reliable English ICAO chapter identified. Full extracted-text searches for ICAO/name/7358/PAN-53 did not resolve it. | Unresolved page review, **not** proven absent English. Raster-only/differently headed content not ruled out. |
| Refuelling restrictions | Chinese 314 and English 1171 contain boarding/fire-cover requirements alongside signature/jet-bridge administration. | Parser/filter issue repaired without deleting operating sentences; original text retained in provenance. |
| Special procedures | Chinese 317 and English 1174 contain noise, decompression and radio-failure references. | Parser/pairing issue repaired; not falsely called absent English. |
| Guangzhou weather | Chinese 986 separate weather items versus English 1581 combined meteorological paragraph. | Remaining multi-record/one-item pairing issue, not a confirmed source gap. |
| Guangzhou 919R | Chinese 986 prohibits/recommends against single-engine taxi at stand 919R; current English candidates have not safely matched it. | Unresolved source-page review; candidate absence alone is not source absence. |
| Guangzhou speed/distance | Chinese 991 specifies speed 180 to 8 nautical miles; English 1583 says `speed of 180 to 8 knots`. Both pages rendered and visually checked. | Confirmed SOURCE_CONFLICT in the printed bilingual item, not just extraction. Do not invent an equivalent English restriction. |
| Guangzhou runway rules | Chinese 987 has north/south allocations including RWY03/21; English 1581 has a shorter, materially different allocation. Both printed pages visually checked. Several Chinese extraction tokens contain `RWYO…`; the glyph alone is not permission for an O-to-0 replacement. | Confirmed incomplete/conflicting source counterpart. No guessed runway repair. |
| Guangzhou engine-out | Chinese 991 has a start-date reference; English 1583 adds chart/PBN references and omits that date. Both printed pages visually checked. | Confirmed source-content difference; guard remains active. |

Other critical/concept/gap errors are individually retained in the linked JSON. No unresolved item is silently reclassified as a warning. No USER_CONFIRMED translation was added.

## Regression assertion review

- Updated obsolete format locators for one global Typical heading followed by airport paragraphs. The downstream source, role and metadata checks remain.
- Elevation is allowed in Core, never repurposed as an incident. Metadata/fragment checks remain.
- Raw source `150°～320°`, `2万英尺`, `400英尺左右`, quoted/slash wording and extraction whitespace replace tests for previously editorially rewritten forms; the actual numbers and conditions are still asserted.
- The real conditional Runway 13 landing-configuration/speed item is not a detached bare-speed fragment. Tests retain its conditions and continue rejecting detached numeric facts.
- Actual IRS source text remains required; only extraction whitespace is normalized by its assertion.
- Real generation/last-good/source/parity tests remain acceptance gates, not converted into warning expectations.

| Previously failing regression | Review and retained acceptance requirement |
|---|---|
| August 4 confirmed format | Source keeps separate runway lengths and explicit prohibited-runway condition; tests no longer require an editor-combined sentence. |
| August 8 seasonal/task quality | Balanced bibliographic compilation citations are removed, but operating conditions and operational chart references remain guarded. |
| August 11 real groups | Source spelling/units/whitespace and raw `by ATC` are retained. Source records are not required to have a legacy paragraph-editor topic label. Numeric and conditional assertions remain. |
| August 12 roles/events | Landing/runway-vacating ground facts are arrival-only; neutral taxi facts remain both-role. Independent all-flight clauses do not inherit arrival restrictions. |
| October 5 English source regression | Complete conditional landing-configuration/speed source item remains; a detached bare speed is still rejected. |
| 9C8552 real source | Actual IRS alignment source content still required, comparing extraction whitespace only. |
| August 28 structure | Newly required source elevation is allowed in Core, while event/metadata/fragment restrictions remain. |
| August 14 real generation | Decimal slope is not removed as hierarchical numbering and does not masquerade as an output list. |
| September 10 quality | TCAS retains its topic even in an arrival phase. Required-topic diagnostics are emitted; arrival-only source remains excluded from departure. |
| PDF versus old TXT | Flattened legacy TXT containing genuine list/concatenation artifacts must fail safely, not be forced into a successful baseline. Latest-PDF authority and actual independent complete group outputs remain checked. |

## Validation

- Targeted source-only / manual-pairing / applicability-English-quality suite: **60 passed**, 0.69 seconds.
- Final complete `python -B -m pytest`: **755 passed**, 0 failed, completed at 100% in 758.18 seconds. Earlier interrupted or failed development snapshots are not counted as passing final runs.
- `git diff --check`: PASS.
- The previous 10 failing regression tests are no longer failing. This does not resolve the independent real-manual bilingual acceptance errors above; those are explicitly tested to preserve FAILED_SAFE and last-good behavior.

MERGE_READY=false. Keep PR #58 Draft. No production generation or merge is authorized by this diagnostic progress.
