"""Review-only output; never creates a release marker or writes formal paths."""
from dataclasses import fields
from pathlib import Path

from crew_agents.common import atomic_write_json, atomic_write_text


NOTICE = "PREVIEW / 审核预览 — NOT FOR RELEASE / 不得作为正式运行资料发布"


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
