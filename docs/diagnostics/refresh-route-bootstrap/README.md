# Refresh, route applicability and bounded archive recovery

Base / real task input: `b90d1a9565c8e7588dc1cb653ba0301eba9af891`.
These are **isolated original-source copy samples**, not new production releases.
No calendar, Flight Prep, login or OTP workflow was dispatched.

## Generation inputs and bounded refresh

`generation_inputs` records SHA256 content identities for the running Flight Prep code, its embedded templates, relevant configuration and the actual manual candidate chain selected by the existing resolver. Text CRLF/LF checkout differences are normalized so the Windows checker and Linux generator agree; binary manuals remain byte-exact. It does not use Git HEAD, daily ICS bytes or generated airport-experience state. The existing operational task fingerprint still handles actual task changes.

Legacy metadata is refreshed once when it has no matching input identity. A successful dispatch records a separate `generation_attempt` receipt through the scheduler's **existing metadata publication path**. It does not change a previous release status to SUCCESS, create `.success`, or write a briefing. The same task/input pair is not dispatched repeatedly even when a failed-safe job cannot publish its own metadata. A new task or input identity is eligible again. Cancellation clears the old receipt so restoration remains eligible. A failed API dispatch records no accepted receipt. The existing state publication call now supplies its known main snapshot (ICS publication commit/base, or bootstrap SHA) to the publisher's existing MAIN_MOVED guard, so a concurrent new preparation cannot be overwritten by an older receipt. No publisher or schedule-time logic changes. Publication/transport errors remain errors, not manufactured success; an absent/unpersisted receipt is not proof that a dispatch never reached GitHub.

The real Nov 18 old `PARTIAL_RELEASE` state now returns `generation_inputs_changed`, not `partial_release_matches_current_tasks`. The isolated simulated receipt then returns `generation_already_attempted_for_current_inputs`; a non-operational ICS refresh remains NO_ACTION. Real generation writes its input identity to dated and latest metadata; the newly generated partial state settles at NO_ACTION. See `audit.json` and `acceptance.json`.

## Source page and route evidence

Visual checks of the unchanged 20261019 PDF pages **621 and 623** confirm three independently labelled route restrictions:

| Existing wrong inclusion in Jieyang–Yangzhou group | Source | New result |
|---|---|---|
| 扬州-南昌、珠海可以申请直飞… | p621, `扬州泰州_core_record_30` | Excluded: explicit shared origin and multiple other destinations |
| 扬州南宁航路：… | p621, `扬州泰州_core_record_31` | Excluded: unambiguous concatenated airport route label |
| 扬州到兰州涉及释压程序… | p623, `扬州泰州_core_record_48` | Excluded: named route with explicit program applicability |

The parser uses existing unambiguous airport aliases and explicit syntax, not airport-specific branches. Synthetic tests cover joined labels, destination lists, 到/至/飞往, direction mismatch, unknown aliases and historical narrative. Historical typical incidents mentioning another route are retained; the real 珠海–扬州 approach event, its 1000/400 ft sequence, general airport risks and conditional approach controls remain in the complete copy body. No operating numbers or procedures were corrected. Each exclusion retains its source text, fact ID, section/page and reason in the audit.

## Actual Nov 18 samples

- `9C6569`: 上海虹桥 → 揭阳潮汕, its own complete Chinese and available original English copy. Hongqiao construction/runway source conflict still blocks this group's RELEASE (Chinese p545–551 / English p1361).
- `9C8833X`: 揭阳潮汕 → 扬州泰州, separately complete Chinese copy, available source English only. The three other-route paragraphs are absent from body and copy payload. No Yangzhou English was invented.
- The actual tasks have no foreign crew. Normal production language policy therefore permits the second group's validated Chinese RELEASE in the isolated run. Explicit bilingual review still reports missing reliable Yangzhou English; it does not pretend that a complete English release exists.
- Existing `PARTIAL_RELEASE` behavior remains: only the eligible second group is written in the disposable directory and gets the existing success marker. The blocked first group, aggregate dated text and latest last-good are untouched. This is **not** an all-group SUCCESS and no real repository output was replaced.
- Four actual copy buttons per view were exercised in an isolated headless browser; all copied payloads equal the fixed-format bodies. Personal introduction / separate PF and PM / typical events / core threats, unnumbered blank-line paragraphs and independent flight groups remain intact.

Full review files: `SOURCE_COPY_group_01_zh.txt`, `SOURCE_COPY_group_01_en.txt`, `SOURCE_COPY_group_02_zh.txt`, `SOURCE_COPY_group_02_en.txt`, `copy.html`.

## Network evidence and recovery

Runner: `DESKTOP-1HCRR8D`, existing proxy listener present. Failed production run `43974714669`, job `133675597237`, timed out all three archive attempts with only the old `MethodInvocationException` wrapper visible; no scraper ran.

Same fixed SHA, actual read-only network probes:

| Path | Result | Bytes | Total |
|---|---|---:|---:|
| Existing environment proxy, curl | HTTP 200 then timeout (exit 28) | 4,836,582 incomplete | 90.004 s |
| Command-only direct codeload, curl | HTTP 200, complete | 49,766,913 | 5.907 s |
| New helper, existing default path, later probe | Complete, CRC/SHA-root checked | complete archive | 10.263 s |

Evidence supports an **intermittently slow/failing proxy archive path**, not a permanently broken codeload endpoint or API authorization failure. A later default-path success is explicitly recorded; no persistent proxy settings were changed, and no claim is made about which upstream node caused it.

The first attempt still inherits environment/system proxy. Only an archive transport exception enables subsequent direct codeload recovery; API requests continue to inherit proxy. Maximum three attempts, 240 s archive/header+body cancellation, 90 s API bound and 5/15 s backoff remain. Controlled tests prove stalled-body recovery, final bounded failure and partial ZIP cleanup.

Production endpoints require HTTPS api.github.com and codeload.github.com, exact repository/full-SHA redirect path, no credentials in the URL authority, no automatic redirects or token forwarding to the archive request. Local loopback endpoints exist solely for network tests. Before workspace replacement, content length (when supplied), every ZIP entry/CRC, traversal/symlink rejection and repository + SHA archive root are verified. Only safe stage/type/byte/path-mode diagnostics are printed; no signed URL, token, response body or credentials are logged.

## Test gates and remaining limits

Targeted and full-suite counts plus branch/merge-preview CI links are recorded on the PR for its exact commit. No tests were disabled. Synthetic download tests do not access GitHub or production data.

Unresolved Hongqiao source conflict and unavailable Yangzhou English remain visible and protected. Network recovery is bounded, not a promise of success when both paths are unavailable. This PR does not trigger production or authorize bypassing formal RELEASE review.
