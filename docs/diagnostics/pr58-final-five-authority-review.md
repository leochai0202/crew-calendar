# PR #58: final five-category authority check (DRAFT)

Baseline: `244e81925f30dc59c13b5fb1e9deafb0baaa2d3a`. This focused review supersedes the five-item unresolved list in the previous Chinese-primary English review. It does not authorize production publication or merge.

## Resolved: VTBS airborne departure radio instruction

The [CAAT published-issues index](https://aip.caat.or.th/) identified **01 OCT 2026, AIRAC AIP AMDT 10/26** as the effective issue at verification on 28 October 2026, with the next issue effective 29 October. [VTBS AD 2.22, section 6.1 in that issue](https://aip.caat.or.th/2026-10-01-AIRAC/html/eAIP/VT-AD-2.VTBS-en-GB.html) requires an airborne departing aircraft to contact Suvarnabhumi Departure on 119.25 MHz before the relevant approach-sector transfer, subject to other ATC instructions. The [06 AUG 2026 archived issue](https://aip.caat.or.th/2026-08-06-AIRAC/html/eAIP/VT-AD-2.VTBS-en-GB.html) contains the same requirement.

This supports a radio **contact instruction**, not automatic aircraft tuning, automatic frequency selection or an uncommanded avionics function. The company manual's abbreviated Chinese departure item (page 315) and its unreliable English rendering (page 1171) remain unchanged in provenance. The source-bound reviewed English now states the contact instruction and preserves the ATC exception and transfer sequence. The Chinese briefing text is unchanged.

The reviewed data records the official URL, issue, section, publisher, verification date, supported-text hash and a conservative target-date validity interval: **2026-10-01 through 2026-10-28**. Starting 29 October, the correction fails its publication gate until the newly effective issue is rechecked. This is not an assertion that every later AIP/NOTAM/SUP has been reviewed.

Minimal generic code validates the optional authority evidence and its exact supported body, retains both manual originals, checks the target date and preserves existing quantity, action, condition and provenance guards. It does not fetch sources at runtime, rewrite matching/ranking algorithms or alter the other unresolved operational data.

## Remaining: no verified currently effective authority obtained

| Category | Company manual Chinese / English pages | Unresolved operational question | Result |
|---|---|---|---|
| Guangzhou runway allocation | 987 / 1581 | Direction-dependent runway/use assignments, including 01/02/03 and 19/20/21 series | Remains blocked |
| Guangzhou W19 waypoint | 990 / 1582 | OLPAB versus OBLAP in the same route requirement | Remains blocked |
| Guangzhou speed/distance | 991 / 1583 | Speed 180 and distance 8 NM versus the English 8 knots wording | Remains blocked |
| Pudong PAPI | 586 / 1367 | Runway-specific distance, angle and MEHT association | Remains blocked |

The official China eAIP portal returned a JavaScript-only shell; bounded browser retrieval did not yield the current original operational pages. Other official AIS endpoints did not provide a usable current original. This is an **evidence-access limitation**, not proof that the authority has no answer. No account/login barrier was observed or inferred. Historical mirrors, old news, matching number sets, plausible spelling and simulator charts were not accepted as current authoritative confirmation. No data in these four categories was corrected or silently suppressed.

## Actual isolated acceptance

Company manual: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.

SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.

Read-only frozen real ICS input: `26e9391e6053c7223386346f0e90be2dbc5b6644`.

| Target | Before this check | After this check | Status | Remaining instances |
|---|---:|---:|---|---|
| 2026-10-26 | 4 | 3 | FAILED_SAFE | Guangzhou runway allocation, W19 waypoint, speed/distance |
| 2026-10-28 | 3 | 2 | FAILED_SAFE | Guangzhou runway allocation, Pudong PAPI |

Both dates retain every selected Chinese and English fact identity. Complete Chinese bodies are byte-identical to the baseline. Only the single applicable VTBS departure-contact English paragraph changes on each date; unrelated English facts are unchanged. No content compression or fact deletion was used. Complete diagnostic previews and per-fact provenance are in the adjacent `independent-language-20261026-audit.*` and `independent-language-20261028-audit.*` files.

Both dates produced **no `.success`, no new formal text**, and preserved all four dated/latest Chinese/English last-good sentinel files. The VTBS standalone airport check now passes; the four remaining source categories still block publication. Diagnostic previews are not valid/sendable formal briefings.

## Validation and scope

- Final targeted suite: **302 passed**.
- Final full local pytest: **1013 passed**, 0 failures, errors or skips (849.284 seconds; JUnit report inspected).
- Tests cover date-bound authority use, source/body identity, changed frequency, omitted ATC exception, reversed transfer sequence and unsupported automatic-tuning claims. Existing raw-source conflict tests remain active.
- Final commit diff check and both same-head GitHub CI results are recorded in the PR review summary after upload; no production run is required or authorized.
- No workflow YAML, PDF, profile, ICS, calendar, scraper, authentication/OTP, grouping, scheduling, publishing transport or main branch was changed. Keep PR #58 **Draft**; do not merge or publish.
