# PR #58: independent original-language copy drafts

## Scope and safety boundary

This implements the user's final original-source copy policy. `copy.html` and
`SOURCE_COPY_group_XX_zh/en.txt` contain the fixed briefing body only. Review
labels, missing-language notices, source IDs, source pages and publication
errors remain outside the copied body, in the viewer and audit files.

English copy facts are selected independently from the English manual records
with reviewed Chinese translations disabled **before selection**. This avoids
using a translated paragraph's scope, restoring a whole parent paragraph over
an applicable clause, or substituting a translation into an original-text copy.
The original English wording and numerical inconsistencies are not corrected.
Chinese uses the already-selected source-verbatim manual facts. No new fact
limit, summary, airport-specific rule or manual edit is introduced.

Every copy fact retains its identity, original text, source file, version,
section and page under `source_copy_fact_sources` in `preview_meta.json`.
English exclusion reasons are retained separately. Even for a validated formal
group, this viewer copies manual originals, not reviewed RELEASE translations.

Copy drafts are **not company-approved operational RELEASEs**. Existing formal
validation, group publication, FAILED_SAFE, `.success` and last-good gates are
unchanged. Missing English does not block Chinese copying. It is indicated on
the page, without inventing an English replacement or appending a warning to
the copied body. An unavailable language's obsolete generated copy file is
removed only from its review directory, never from formal last-good files.

## Real isolated acceptance

- Input main: `f0b4ca9c4337c799c65053b91743206bdca27647`.
- Manual: `AirDropManual-机场特点汇总(Airport Information)20261019-Manual.pdf`.
- Manual SHA256: `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`.
- Output: `%TEMP%/crew-pr58-source-copy-final-acceptance/`.
- Both dates generated in a disposable workspace from actual main ICS.
- Both dates: actual Edge button clicks captured the clipboard API payload;
  payload equals the displayed complete body, without review labels/errors.
- All four copy texts were read in full; final file hashes match those reviewed.
- Fixed personal/recency, separate PF/PM, typical events and core-threat sections;
  paragraph spacing and no numbered/bulleted items verified.
- No production workflow, login, OTP or formal publication was triggered.

| Date | Actual group | Original ZH / EN facts | Copy acceptance | Formal protection |
| --- | --- | --- | --- | --- |
| 2026-11-13 | 9C8801 / 9C8802 | 31 / 30 | Both bodies, two copy buttons pass | PAPI association conflict remains blocked |
| 2026-11-14 | 9C6687 / 9C6688 | 40 / 17 | Complete available Chinese and sourced Pudong English; two buttons pass | PAPI and missing Dongying English remain blocked |

Nov 14 does **not** have a complete Dongying English briefing. The page explicitly
states that gap; it does not prevent the existing Chinese or sourced English
from being copied. Neither date creates a formal success marker. Both preserve
previous dated/latest last-good text and leave configuration unchanged.

## Reviewed copy file hashes (SHA256)

| Date / language | SHA256 |
| --- | --- |
| Nov 13 ZH | `238b29b70d02baf2dc8118c34dcad06b01472522a428f803122390d8150d33a6` |
| Nov 13 EN | `2ff67c324da63b320f917635b3dacdd0227e21277e207af8e73d4c97a8fe675f` |
| Nov 14 ZH | `3f60375894aebbF590a7409058ffc5f6e6e460fc9e10dbf44760792d0fbcacf4` |
| Nov 14 EN | `d9e01b895011df5f5ca27bd9e9d0ab8b05bb1635124be77b03591114cdbf0afe` |

Regression tests cover original-vs-translated selection, conflicting originals,
clean clipboard payloads, missing English with available Chinese, removal of a
stale review-only language file, validated-group copy fidelity, independent
groups and unchanged publication safety. Full-suite and both GitHub check
results are to be read against the exact PR head, not inferred from this report.
