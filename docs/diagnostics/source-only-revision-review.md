# PR #58 — general parser revision (not release acceptance)

## Scope and verified source

Continue the same draft branch. No airport/date/flight-specific production branches or text replacements were added. No production workflow, scraper or authentication was run. The authoritative manual remains version 20261019, SHA256 `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.

## Generic changes

- Scan numbered Chinese source records across the whole chapter instead of combining overlapping legacy collectors. Unfamiliar numbered labels terminate the previous source record; Arabic and Chinese parenthesized numbering preserve phase boundaries; page footers do not terminate continuations.
- Continue English extraction in unknown numbered sections and `Other` sections. Preserve unnumbered prose under recognized sections. No translation, terminology substitution or English professionalization.
- Pair elevation/runway/PAPI fields by field identity rather than their relative position among unrelated paragraphs. Other records retain airport/category/phase/order/critical-anchor pairing and ambiguity rejection.
- Distinguish administrative/passenger transport/contact/bare-frequency material from operational radio procedures and ATC instructions. A building described as an aviation obstacle is not rejected merely because it is a hotel.
- Detect detached numeric limits even after a phase prefix. Reject unparsed yes/no attribute tables instead of emitting a flattened table as prose. This rejection is not proof all valuable table cells have been recovered; cell-level completeness remains a review concern.
- Check verbatim source controls against actual source text, not control wording synthesized by the legacy semantic classifier. Literal, condition, bilingual and selected-ID guards remain active.
- Remove structural Chinese labels without entering the old prose editor, retaining labels with operational subjects/conditions such as ATC requirements.

## Entire manual inventory

[All-chapter inventory](all-manual-chapter-structure.json): 177 recognized Chinese chapters, 74 English chapters, 73 ICAO-bound matches, zero cross-ICAO identity errors. All recognized Chinese chapters were scanned for source records and quality reasons. This is structural coverage, **not** proof of bilingual completeness. Unmatched chapters require page review; they are not automatically classified as missing English.

Additional real regression sample: Shenyang, besides the five requested airports. [Current full evidence](source-only-manual-audit.json) and [readable previews](source-only-manual-audit.md) include original records, Chinese/English source identities, all errors, actual real-duty rendering and separate departure/arrival previews.

## Real acceptance results

| Airport | Selected core candidates | Errors before | Errors now | Result |
|---|---:|---:|---:|---|
| 丽江三义 | 32 | 34 | 36 | FAILED_SAFE |
| 桂林两江 | 10 | 11 | 11 | FAILED_SAFE |
| 广州白云 | 37 | 31 | 29 | FAILED_SAFE |
| 曼谷素旺那普 | 36 | 17 | 16 | FAILED_SAFE |
| 上海浦东 | 16 | 5 | 6 | FAILED_SAFE |
| 沈阳桃仙 (additional sample) | 25 | not measured | 14 | FAILED_SAFE |

Counts are not selection targets and do not establish success. Broader source coverage and more conservative pairing can expose more gaps rather than reduce the count. Real 2026-10-26 still has **44 errors**, versus 44 on the previous head. Its 89 selected group-fact instances contain 69 source-backed English counterparts and 20 coverage gaps; generic fallback remains zero. Source-backed does not mean validation passed.

The current 44 errors comprise 20 missing English counterparts, 14 critical-fact mismatches, 8 concept mismatches, and 2 selected-ID parity failures. Source-semantic preservation errors in this real-duty audit are now zero; this does not resolve the independent bilingual errors.

| Airport | Departure core IDs | Arrival core IDs |
|---|---:|---:|
| 丽江三义 | 13 | 26 |
| 桂林两江 | 4 | 8 |
| 广州白云 | 29 | 25 |
| 曼谷素旺那普 | 21 | 29 |
| 上海浦东 | 8 | 13 |
| 沈阳桃仙 | 16 | 15 |

These role previews use isolated synthetic duties and are not formal briefings. Real 2026-10-26 remains two groups, `9C7289` and `9C7420`, with both languages required. The failure produced no `.success` and no formal text files. Dated/latest last-good sentinels survived unchanged in the temporary test workspace. Continuous `9C7605/9C7606` grouping remains tested.

## Source evidence and unresolved issues

1. **W19 source conflict, not a spelling decision:** Chinese page 990 says `MASGU-UPMIP-ATKAV-OLPAB-NOMAR`; English page 1582 says `MASGU-UPMIP-ATKAV-OBLAP-NOMAR`. The English page was rendered and visually checked. No token was substituted or ignored.
2. **STAR/runway-confirmation source discrepancy:** Chinese page 313 has Command Characteristics item (4), beginning `曼谷进近只给出进场STAR程序，不告知跑道`. Rendered English page 1169 has Command Characteristics (1)–(3), then Pavement Characteristics; page 1170 continues that pavement item. The corresponding location lacks the Chinese item. Whole English chapter text pages 1169–1182 was searched for the concept; no reliable counterpart identified. This is evidence of a discrepancy, not permission to translate or borrow another record.
3. **No reliable Lijiang English chapter identified:** Chinese chapter pages 946–951 exists; page 203 is a Chinese departure briefing card. Full text search found no English-page `ZPLJ`, Lijiang/Sanyi, 7358 or PAN-53 counterpart. No English text was invented. Raster-only or differently named content has not been conclusively ruled out; classify as unresolved page review, not proven absence based solely on a parser result.
4. Other numeric/concept mismatches, pairing gaps and paragraph completeness errors are expanded in the linked evidence with both source texts and chapter page ranges. They are **not all claimed to be true manual conflicts**; parser and source issues remain unresolved.
5. Raw-source generation still fails some old real-task regressions. Do not replace their safety assertions with success/warning expectations merely to make the suite green.

## Existing 13 failures: classification

- Obsolete assertions explicitly updated: numbered/per-airport event headings in the minimal structural fixture and August 4 assertion; rejecting airport elevation as core material. Elevation remains forbidden as a typical event.
- Genuine parser regression addressed with a dedicated test: a phase prefix hiding a detached bare-speed/altitude limit. The real October 5 regression remains active.
- The remaining real-generation tests remain acceptance gates, not deleted tests. Their final results must be read from the complete run, not inferred from targeted tests.

## Validation

- Targeted source-only/pairing/updated-format tests on the final source snapshot: **36 passed** (0.73 seconds); source-only/pairing subset: 29 passed.
- Final full pytest: **724 passed, 10 failed**, 701.43 seconds; completed at 100%. Earlier interrupted development snapshots are not counted as completed runs.
- `git diff --check`: PASS.

**MERGE_READY=false. Keep Draft.** This revision does not claim the requested all-airport production system or bilingual acceptance is complete.

### Complete remaining test-failure classification

| Test | Evidence / classification | Disposition |
|---|---|---|
| `test_real_august_four_final_confirmed_format` | New unnumbered format passes; a later assertion for the old combined 2410m/control wording fails. Source coverage versus obsolete rewriting expectation is not yet resolved. | Do not delete the fact assertion without source proof. |
| `test_real_august_eight_applies_season_task_and_topic_quality` | FAILED_SAFE from source-artifact validation. An isolated diagnostic renderer probe confirms `机场特点汇总-` remains in body text. | Genuine citation/filtering blocker; guard retained. |
| `test_real_august_eleven_writes_two_source_grounded_prep_reports` | Generation succeeds; assertion banning the source's colloquial `甩杆` fails. New policy forbids professional rewriting. | Old wording expectation needs reconciliation, not automatic rewriting. |
| `test_real_august_twelve_generalizes_event_and_role_filters` | Generation succeeds; test splits on the deleted per-airport event heading. | Obsolete section locator; downstream assertions still require verification. |
| `test_real_october_five_uses_source_backed_english_for_every_selected_fact` | Inline `2、速度160节` is still attached inside a longer source record. Standalone prefixed-fragment tests pass, but do not cover this source layout. | Genuine inline-boundary/hierarchy blocker; real regression retained. |
| `test_real_9c8552_exact_event_keeps_source_grounded_chinese_when_english_suppressed` | Generation succeeds but expected `IRS完全校准` not in current output. | Unresolved source/selection versus stale source expectation; do not simply remove assertion. |
| `test_real_august_twenty_eight_filters_pdf_structure_and_fragments` | Generation succeeds but forbidden-token assertion fails. Some previously forbidden attributes are now explicitly allowed, but the complete set requires individual reconciliation. | Not classified wholly obsolete. |
| `test_existing_august_regressions_still_generate[2026-08-14]` | New FAILED_SAFE in real generation, whereas the prior failing August 18 case now passes. | Genuine new regression, not hidden by aggregate improvement. |
| `test_real_september_ten_uses_latest_manual_quality_engine` | Generation succeeds; the helper's old airport substring extraction includes the typical section and another airport's core section under the new format. | Obsolete locator identified; source/role assertions must remain. |
| `test_real_flight_before_after_pdf_regression` | Baseline real generation still returns FAILED_SAFE. | Unresolved real safety-gate failure; no expectation weakened. |

The initial 13 failures are therefore not all solved or all stale. The old minimal-layout and elevation assertions were corrected and pass; August 26 and August 18 generation now passes; August 14 is a newly exposed failure. Every remaining failure stays visible.
