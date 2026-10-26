"""Read-only whole-manual structural inventory; never creates briefings."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent


def inventory(repo: Path, output: Path, target: date) -> None:
    manual = agent.find_latest_airport_manual(repo / "knowledge")
    assert manual is not None
    text, warnings = agent.read_manual_text(manual)
    chinese = agent.build_manual_index(text)
    english = agent.build_english_manual_index(text)
    records = []
    for chapter in chinese:
        icao = str(chapter.get("icao") or "")
        en = agent.match_english_manual_chapter(english, icao) if icao else None
        typical, core = agent.extract_manual_lists(chapter, len(chapter["lines"]))
        rejections = Counter(agent.manual_source_quality_issue(value) for value in core)
        airport = str((agent.airport_registry_entry(icao) or {}).get("canonical_zh") or icao or "审计机场")
        eligible = []
        for number, original in enumerate(core):
            value = agent.filter_source_administrative_sentences(original)
            if not value or agent.manual_source_quality_issue(value):
                continue
            heading = agent.SOURCE_HEADING_RE.match(value)
            phase = agent._source_clause_phase(value, heading.group(1) if heading else "")
            eligible.append(agent.verbatim_manual_fact(airport, {
                "text_zh": value, "category": "core", "source_record_id": f"inventory:{number}",
                "source_original_text": original, "operational_phase": phase,
                "role_scope": agent.explicit_role_scope(value, phase),
            }, number))
        role_checks = {}
        for role, left, right in (("departure", airport, "审计对照机场"), ("arrival", "审计对照机场", airport)):
            duty = agent.CalendarEvent(uid="structure-audit", summary=f"9C0001 {left}→{right}",
                start=datetime.combine(target, datetime.min.time()).replace(hour=12),
                end=datetime.combine(target, datetime.min.time()).replace(hour=14),
                description="", location="", properties={})
            selected = agent.prepare_operational_facts(duty, airport, target, eligible, max_items=len(eligible), exclusion_log=[])
            role_checks[role] = {
                "selected": len(selected),
                "opposite_only_selected": sum(bool(f.role_scope) and role not in f.role_scope for f in selected),
                "duplicate_texts": len(selected) - len({agent.compact_key(f.zh) for f in selected}),
                "departure_performance_candidates": [f.zh for f in selected if role == "arrival" and "单发加速高度" in f.zh and "复飞" not in f.zh],
                "go_around_acceleration_mentions": [f.zh for f in selected if role == "arrival" and "复飞单发加速高度" in f.zh],
            }
        records.append({
            "header": chapter["header"], "icao": icao,
            "chinese_pages": [chapter.get("start_page"), chapter.get("end_page")],
            "chinese_typical_count": len(typical), "chinese_core_candidates": len(core),
            "candidate_quality": dict(rejections),
            "english_header": en.get("name") if en else None,
            "english_pages": [en["start_page"], en["end_page"]] if en else [],
            "english_identity_status": "ICAO_MATCHED" if en else "NOT_IDENTIFIED_REQUIRES_PAGE_REVIEW",
            "identity_error": bool(en and en.get("icao") != icao),
            "role_checks": role_checks,
        })
    result = {
        "manual": manual.name,
        "sha256": hashlib.sha256(manual.read_bytes()).hexdigest(),
        "chinese_chapter_count": len(chinese), "english_chapter_count": len(english),
        "matched_chapter_count": sum(bool(record["english_pages"]) for record in records),
        "identity_errors": sum(record["identity_error"] for record in records),
        "warnings": warnings, "chapters": records,
        "role_audit_date": target.isoformat(),
        "notice": "Structural inventory only, not proof of bilingual content equivalence or source absence.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "chinese_chapter_count", "english_chapter_count", "matched_chapter_count", "identity_errors")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-date", type=date.fromisoformat, default=date.today())
    arguments = parser.parse_args()
    inventory(arguments.repo.resolve(), arguments.output, arguments.target_date)
