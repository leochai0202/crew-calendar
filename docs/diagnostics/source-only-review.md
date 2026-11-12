# Complete-chapter source-only extraction — DRAFT REVIEW

Initial-head baseline only. For the subsequent PR #58 revision and current test results, see [revision review](source-only-revision-review.md).

This branch is not production ready. Do not merge or publish diagnostic previews as formal briefings.

## Authoritative manual actually synchronized

- Existing Sync Airport Manual run: `40197711361`, job `121182064070`, success.
- Main manual commit: `936e6729c8ed20a1220423762a1ae2146b3d9227`.
- File: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
- SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.
- Git blob: `0fc1d748caf4a66ae48dfb35ce96c8ac0d33b3b5`.
- Real Windows source was checked with the existing sync validator. User source files were not deleted.
- The PDF is already on main; this code PR does not modify the PDF.

## Scope

Only Flight Prep extraction, provenance, source-only selection/rendering, its tests, and an isolated audit utility are changed. No authentication, ICS, calendar scraping, transport, scheduling, profile, or manual-sync business logic changes.

Typical events retain explicit event-section provenance. Core candidates include complete numbered basic information and positive operational attributes, runway/PAPI continuations and operational sections. The source-only path does not impose a small paragraph-count cap, translate, professionalize English, or substitute curated/USER_CONFIRMED templates for manual content. It retains duty-role, route, season, source-quality and bilingual guards.

Only generic chapter/section/order fixes needed from draft PR #56 were reused. PR #56 was not merged or modified. English chapters remain ICAO-bound. Ambiguous or incomplete bilingual pairing still fails safe.

## Real acceptance evidence — NOT SUCCESS

Full facts, source pages/headings, original English identities, rendered diagnostic text and every error are in [JSON](source-only-manual-audit.json) and the readable [report](source-only-manual-audit.md).

| Airport | Core candidates | Core English present | Errors | Result |
|---|---:|---:|---:|---|
| 丽江三义 | 31 | 0 | 34 | FAILED_SAFE |
| 桂林两江 | 10 | 9 | 11 | FAILED_SAFE |
| 广州白云 | 37 | 26 | 31 | FAILED_SAFE |
| 曼谷素旺那普 | 36 | 33 | 17 | FAILED_SAFE |
| 上海浦东 | 15 | 14 | 5 | FAILED_SAFE |

These counts describe diagnostic selections, not a hardcoded acceptance target. Gaps may still be extraction/pairing defects; an empty parser result alone is not proof the source PDF lacks English.

Lijiang Chinese pages 946–951 include 7358ft, the complex-airport attribute, both-runway EOSID, slope, navigation restrictions and arrival/departure procedures. The audit confirms these are selected. No reliable ICAO-bound Lijiang English counterpart was identified; the English preview is explicitly blocked, not invented. Visually reviewed source pages: 946, 947 and 950.

## Real-duty and grouping checks

- `9C7605 / 9C7606`: one group (regression test).
- Real `2026-10-26`, `9C7289 / 9C7420`: two independent groups.
- Foreign-crew duty: both groups enter Chinese and English rendering/validation.
- Selected bilingual source states: 75 source-backed, 11 coverage-gap; no concept fallback.
- Real-duty result: `FAILED_SAFE`, 44 validation errors.
- No `.success`, no new formal text files; dated/latest last-good sentinels remained unchanged in an isolated temporary workspace.
- Therefore real bilingual publication acceptance has NOT passed. No production Flight Prep run was triggered.

## Validation

- Source-only plus bilingual-pairing targeted suite: 19 passed.
- Full pytest: **711 passed, 13 failed**, 711.62 seconds. It completed at 100%; this is not a passing release result.
- `git diff --check`: PASS at preparation time.

## Remaining blockers

1. Real source-only bilingual coverage, critical-token/semantic equivalence and source-completeness errors in the linked report.
2. Legacy tests assuming older layout, capped selection, curated English or professionalization require careful reconciliation with the new explicit source-only policy; do not weaken guards to make them green. Failures are not all obsolete assertions: the October 5 regression still detects a detached bare-speed fragment, and several real generation tests fail safe. Those remain genuine blockers.
3. A valid Lijiang bilingual sample cannot yet be delivered. The linked Chinese/English previews are diagnostics, not approved flight briefings.

Keep this PR draft. No production merge, calendar run, authentication/OTP or production Flight Prep is authorized by these diagnostic results.

### Full-suite failed tests

1. `test_flight_prep_final_format.py::test_structurally_complete_briefing_has_no_length_floor`
2. `test_flight_prep_final_format.py::test_real_august_four_final_confirmed_format`
3. `test_flight_prep_final_format.py::test_real_august_eight_applies_season_task_and_topic_quality`
4. `test_flight_prep_final_format.py::test_real_august_eleven_writes_two_source_grounded_prep_reports`
5. `test_flight_prep_final_format.py::test_real_august_twelve_generalizes_event_and_role_filters`
6. `test_flight_prep_foreign_crew.py::test_real_october_five_uses_source_backed_english_for_every_selected_fact`
7. `test_flight_prep_foreign_crew.py::test_real_9c8552_exact_event_keeps_source_grounded_chinese_when_english_suppressed`
8. `test_flight_prep_output_standard.py::test_manual_structure_fields_are_not_operational_facts[机场标高：10ft]`
9. `test_flight_prep_output_standard.py::test_real_august_twenty_six_generates_with_local_guard_fallbacks`
10. `test_flight_prep_output_standard.py::test_real_august_twenty_eight_filters_pdf_structure_and_fragments`
11. `test_flight_prep_output_standard.py::test_existing_august_regressions_still_generate[2026-08-18]`
12. `test_flight_prep_output_standard.py::test_real_september_ten_uses_latest_manual_quality_engine`
13. `test_flight_prep_pdf.py::test_real_flight_before_after_pdf_regression`
