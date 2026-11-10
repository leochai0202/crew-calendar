"""Review-only output; never creates a release marker or writes formal paths."""
from dataclasses import fields
from html import escape
from pathlib import Path

from crew_agents.common import atomic_write_json, atomic_write_text


NOTICE = "PREVIEW / 审核预览 — NOT FOR RELEASE / 不得作为正式运行资料发布"


def source_review_queue(groups: list[dict], evidence: list[dict], version: str) -> list[dict]:
    """Stable review keys across duties; diagnostic only, never a release allowlist."""
    from crew_agents import flight_prep_agent as agent

    pending = {}

    def add(airport, source_ids, originals, kind, reason, group, pages):
        icao = agent.route_airport_identity(airport)
        ids = sorted(set(source_ids))
        hashes = sorted({agent.source_text_hash(text) for text in originals if text})
        identity = "|".join([icao, version, kind, *ids, *hashes])
        key = agent.source_text_hash(identity)
        item = pending.setdefault(key, dict(review_id=key, status="PENDING_AUTHORITY_REVIEW",
            icao=icao, airport=airport, manual_version=version, source_record_ids=ids,
            source_text_hashes=hashes, issue_type=kind, reasons=[], groups=[], source_pages=[]))
        for field, values in (("reasons", [reason]), ("groups", [group]), ("source_pages", pages)):
            item[field] = sorted(set(item[field]) | set(values))

    for issue in evidence:
        add(issue["airport"], issue.get("source_record_ids") or [issue["fact_id"]],
            [issue.get("chinese_original", ""), issue.get("english_original", "")],
            "SOURCE_FACT_REVIEW", issue["reason"], issue["group"],
            ["ZH:" + str(issue["chinese_page"]), "EN:" + str(issue["english_page"])])
    for group in groups:
        for airport, records in group.get("airport_fact_sources", {}).items():
            english = group.get("english_fact_sources", {}).get(airport, [])
            if records and not english:
                # This is a missing language chapter, not a demand to translate
                # every selected CN fact. Different duties share its review ID.
                add(airport, ["ENGLISH_CHAPTER_MATERIAL"], [],
                    "MISSING_RELIABLE_ENGLISH", "未定位可靠英文机场资料；须核查原件或取得审核译文，不自动翻译",
                    group["group_index"], ["ZH:" + str(raw.get("source_page", "")) for raw in records])
    return [pending[key] for key in sorted(pending)]


def write_preview(output: Path, target: str, groups: list[dict], errors: list[str],
                  manual: str, version: str) -> None:
    from crew_agents import flight_prep_agent as agent

    output.mkdir(parents=True, exist_ok=True)
    contents = {"zh": [], "en": []}
    evidence = []
    manifest = []
    known_fields = {item.name for item in fields(agent.BilingualFact)}
    for group in groups:
        issues = list(group.get("conflict_evidence", []))
        known_ids = {item["fact_id"] for item in issues}
        for records in group.get("english_fact_sources", {}).values():
            for raw in records:
                reasons = [error for error in errors if raw["fact_id"] in error]
                if reasons and raw["fact_id"] not in known_ids:
                    issues.append(dict(reason="; ".join(reasons), airport=raw["airport"], fact_id=raw["fact_id"],
                        source_record_ids=raw.get("source_record_ids", []),
                        english_record_ids=[raw.get("english_source_record_id", "")],
                        source_file=raw["source_file"], source_version=raw["source_version"],
                        chinese_page=raw["source_page"] if raw.get("source_text_zh") else "NOT_BOUND",
                        english_page=raw.get("english_source_page") or raw["source_page"],
                        chinese_original=raw.get("source_text_zh") or "未建立逐条中文绑定；英文原文独立保留。",
                        english_original=raw.get("source_text_en") or raw["text_en"]))
        evidence.extend({"group": group["group_index"], **issue} for issue in issues)
        files = {}
        for language, key, sources in (("zh", "_content", "airport_fact_sources"),
                                       ("en", "_english_content", "english_fact_sources")):
            body = str(group.get(key) or "")
            if not body:
                body = "NO RELIABLE LANGUAGE MATERIAL / 无可靠对应语言资料，禁止补造。\n"
            for records in group.get(sources, {}).values():
                for raw in records:
                    ids = {str(raw["fact_id"]), *raw.get("source_record_ids", []),
                           *str(raw.get("english_source_record_id", "")).split("|")}
                    matching = [issue for issue in issues if ids & {
                        issue["fact_id"], *issue["source_record_ids"], *issue["english_record_ids"]}]
                    if not matching:
                        continue
                    fact = agent.BilingualFact(**{k: v for k, v in raw.items() if k in known_fields})
                    text = (agent.chinese_fact_output(fact) + "。" if language == "zh"
                            else agent.english_paragraph_output(fact))
                    label = "待核实 / UNVERIFIED: " + "; ".join(
                        f"{item['fact_id']} (ZH p.{item['chinese_page']}; EN p.{item['english_page']})"
                        for item in matching)
                    body = body.replace(text, text + "\n\n[" + label + "]", 1)
            name = f"PREVIEW_group_{group['group_index']:02d}_{language}.txt"
            files[language] = name
            atomic_write_text(output / name, NOTICE + "\n\n" + body)
            contents[language].append(body.rstrip())
        private_matching = {"matched_people", "matched_flights", "matched_event_uids", "foreign_crew_names"}
        manifest.append({**{k: v for k, v in group.items() if not k.startswith("_") and k not in private_matching},
                         "preview_files": files})
    appendix = ["", "RELEASE REVIEW / 正式发布审核", "", *errors]
    for issue in evidence:
        appendix += ["", "UNVERIFIED / 待核实: " + issue["fact_id"],
                     f"ZH p.{issue['chinese_page']}: {issue['chinese_original']}",
                     f"EN p.{issue['english_page']}: {issue['english_original']}"]
    for language, bodies in contents.items():
        body = "\n\n====================\n\n".join(bodies)
        atomic_write_text(output / f"preview_{language}.txt", NOTICE + "\n\n" + body + "\n" + "\n".join(appendix) + "\n")
    meta = dict(status="PREVIEW", result_kind="PREVIEW", publishable=False,
                release_eligible=not errors, release_status="FAILED_SAFE" if errors else "VALIDATED_NOT_RELEASED",
                target_date=target, manual=manual, manual_version=version,
                errors=errors, conflicts=evidence, groups=manifest)
    queue = source_review_queue(groups, evidence, version)
    meta["source_review_ids"] = [item["review_id"] for item in queue]
    atomic_write_json(output / "source_review_queue.json", dict(
        schema_version=1, target_date=target, pending=queue,
        notice="Diagnostic only; review IDs are reusable across duties, never release authorization."))
    atomic_write_json(output / "preview_meta.json", meta)
    review = ["# " + NOTICE, "", f"Target: {target}",
              f"Release status: {meta['release_status']}", "",
              "## Release blockers / 正式发布阻断", "", *errors]
    for issue in evidence:
        review += ["", "## UNVERIFIED / 待核实: " + issue["fact_id"], "", issue["reason"],
                   "", f"Source: {issue['source_file']} / {issue['source_version']}",
                   "", "Chinese original, p." + issue["chinese_page"], "", issue["chinese_original"],
                   "", "English original, p." + issue["english_page"], "", issue["english_original"]]
    for language in ("zh", "en"):
        review += ["", "# Complete " + language.upper() + " PREVIEW", "",
                   "\n\n====================\n\n".join(contents[language])]
    atomic_write_text(output / "review.md", "\n".join(review) + "\n")
    write_copy_view(output, target, groups, set())


def write_copy_view(output: Path, target: str, groups: list[dict], released: set[int]) -> None:
    """Offline artifact viewer; labels and copy payloads never mix release/preview."""
    cards = []
    for group in groups:
        index = int(group["group_index"])
        is_release = index in released
        if is_release and (not group.get("release_eligible") or group.get("errors")):
            raise ValueError("Unvalidated group cannot be copied as RELEASE")
        kind = "RELEASE" if is_release else "PREVIEW / NOT FOR RELEASE"
        cards.append(f"<h2>{escape('/'.join(group.get('flight_numbers', [])))} — {kind}</h2>")
        for language, key in (("zh", "_content"), ("en", "_english_content")):
            if not group.get(key):
                continue
            body = str(group[key]) if is_release else (output / f"PREVIEW_group_{index:02d}_{language}.txt").read_text(encoding="utf-8")
            identity = f"g{index}-{language}"
            cards.append(f'<button type="button" data-copy="{identity}">复制 {kind} {language.upper()}</button>'
                         f'<textarea id="{identity}" readonly rows="18">{escape(body)}</textarea>')
    script = """document.querySelectorAll('button[data-copy]').forEach(button => {
button.addEventListener('click', async () => {
 const field = document.getElementById(button.dataset.copy);
 try {
  if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(field.value);
  else { field.focus(); field.select(); if (!document.execCommand('copy')) throw Error('copy'); }
  document.getElementById('copy-status').textContent = '已复制 / Copied';
 } catch (_) { document.getElementById('copy-status').textContent = '复制失败，请在文本框内手动复制 / Select text and copy'; }
}); });"""
    atomic_write_text(output / "copy.html", '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        f'<title>{escape(target)} 航前准备</title><style>body{{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:1rem}}'
        'textarea{display:block;width:100%;margin:1rem 0;white-space:pre-wrap}button{padding:.6rem 1rem;margin-top:1rem}</style>'
        f'<h1>{escape(target)} 航前准备</h1><p>仅 RELEASE 可作正式稿。PREVIEW 含未核实资料，禁止作为正式运行资料。'
        '部分分组通过时，整日合并稿及 latest 仍为 last-good，不代表本次全部任务。</p>'
        '<p id="copy-status" role="status" aria-live="polite"></p>' + "\n".join(cards) + '<script>' + script + '</script></html>')
