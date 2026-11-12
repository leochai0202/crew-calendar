# PR #58 — locked-format acceptance, 2026-11-11

Authority: Google Drive `00_长期上下文`, section 0 item 10, read anew on
2026-11-11. This is format acceptance, not approval of aviation source data.

## Scope

- The Chinese fixed feedback heading occupies its own paragraph. PF and PM
  feedback each occupy a separate paragraph, with blank lines between all three.
- English uses the same paragraph structure. Existing controlled feedback words
  remain unchanged except sentence-initial capitalization and final punctuation.
- Each group's copyable preview starts directly with the personal introduction.
  The PREVIEW / NOT FOR RELEASE notice remains **inside the copied payload** as
  a footer, as well as on the page and button. Inline unverified-source notices
  and the missing-English warning remain. No preview can become a RELEASE.
- Validation rejects combined PF/PM paragraphs or an inline feedback heading.
- No selection, grouping, schedule, source approval, calendar, ICS, authentication,
  OTP or production publishing behavior was changed. No length target was added.

## Latest main and real inputs

Main checked/fetched: `d6b50e785c08be576eae42b4d55f9d8d1440400b`.
Since the preceding acceptance snapshot `aef8fac484c23df4cca3f114473475f5f99af6dc`,
only `crew_schedule.ics`, `flight.ics` and `flighty.ics` changed upstream.
No upstream generator change required a merge or production-file edit.
The isolated acceptance reads current main's actual ICS and experience records.

Manual: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.

## Actual full-text and copy checks

Fresh outputs: local temporary directory
`crew-pr58-locked-format-acceptance/{2026-11-13,2026-11-14}/`.
Each contains `copy.html`, `PREVIEW_group_01_zh.txt`,
`PREVIEW_group_01_en.txt`, source metadata and review evidence.

All four complete language texts were read, including their inline source
warnings. Each actual HTML copy button was clicked in an isolated Edge test;
the complete clipboard payload was compared character-for-character with the
displayed textarea and checked against the locked format. The clipboard adapter
was mocked, so the user's real clipboard/profile was not used or changed.

Verified: personal fields, exact Chinese feedback title, separate PF and PM,
fixed typical/core titles, airport order, independent paragraphs/blank lines,
no ordinal/bullet lists or removed risk sections. Existing group split/merge
regressions remain active; missing feedback is not invented.

For each of the four texts, the entire typical-events/core-threats portion is
unchanged from the preceding acceptance (excluding the relocated preview footer).
There was **no content reduction or change to an operating value/condition**.

## Safety result

| Task | Format/copy | Release result | Remaining source issue |
|---|---|---|---|
| Nov 13, 9C8801/9C8802 | Pass, both language previews | FAILED_SAFE, 1 error | ZSPD PAPI runway/value association, CN p.586 / EN p.1367 |
| Nov 14, 9C6687/9C6688 | Pass for available text; English explicitly incomplete | FAILED_SAFE, 3 errors | Same PAPI issue; reliable ZSDY English core missing and consequent empty English airport section |

The latter two Nov 14 errors are one underlying English-source gap. No English
material was fabricated. Both days create no release `.success`, preserve
dated/latest last-good text, and leave formal/configuration paths untouched in
preview mode. No production run was triggered. PR stays Draft, unmerged.

## Tests

Focused formatting/preview/metadata tests: 74 passed. Existing grouping and
short-valid-briefing tests: 7 passed. Full-suite and both CI results are reported
only after completion; a green test suite does not resolve the source blockers.
