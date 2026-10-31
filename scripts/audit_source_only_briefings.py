"""Read real manual facts and run isolated offline preparation acceptance."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


def write_report(report: dict, path: Path) -> None:
    lines = ["# Independent-language manual extraction acceptance (DRAFT)", "",
             "This is a diagnostic preview, not a valid production briefing. FAILED_SAFE outputs must not be published.",
             "", f"Manual: {report['manual']}", f"Version: {report['version']}",
             f"SHA256: `{report['sha256']}`", "",
             "## Real-manual airport checks", "",
             "| Airport | ICAO | Chinese core selected | Independent English core | Acceptance | Blocking errors |",
             "|---|---|---:|---:|---|---:|"]
    for airport, result in report["airports"].items():
        lines.append(f"| {airport} | {result['icao']} | {len(result['core'])} | {len(result.get('english_core', []))} | {result['status']} | {len(result['errors'])} |")
    for airport, result in report["airports"].items():
        lines += ["", f"## {airport}: Chinese core source preview", "", result["chinese_core_preview"],
                  "", f"## {airport}: English core source preview", "",
                  result["english_core_preview"] or "FAILED_SAFE: no English counterpart was extracted. No translation or generic template was supplied.",
                  "", "### Every acceptance error", ""]
        lines += [f"- {error}" for error in result["errors"]]
        for role, sample in result.get("role_samples", {}).items():
            lines += ["", f"### {role}: source-only role selection preview", "",
                      sample["chinese_preview"], "", sample["english_preview"]]
    offline = report["offline"]
    lines += ["", "## Isolated real-duty generation", "", f"Target: {offline['target_date']}",
              f"Status: {offline['status']}; success marker: {offline['success_marker']}",
              f"Last-good files preserved on failure: {offline['last_good_preserved_on_failure']}",
              "", "Groups: " + str([group['flights'] for group in offline['groups']]), ""]
    lines += [f"- {error}" for error in offline["errors"]]
    for group in offline["groups"]:
        lines += ["", "### Actual isolated rendered group: " + "/".join(group["flights"]),
                  "", "FAILED_SAFE diagnostic text, not published.", "",
                  group.get("chinese_preview", ""), "", group.get("english_preview", "")]
    path.write_text("\n".join(lines), encoding="utf-8")


def audit(repo: Path, airports: list[str], target: str, output: Path, input_ref: str | None = None) -> None:
    input_sha = subprocess.run(["git", "rev-parse", input_ref], cwd=repo, capture_output=True, check=True, text=True).stdout.strip() if input_ref else None
    manual = agent.find_latest_airport_manual(repo / "knowledge")
    assert manual
    mapping = agent.extract_airport_mapping(repo / "crew_calendar_main.py")
    codes = {airport: agent.resolve_icao(airport, mapping) for airport in airports}
    risks, threats, records, warnings, source, version, _ = agent.airport_risks(repo, airports, codes, 10000)
    report = {"manual": manual.name, "version": version,
              "sha256": hashlib.sha256(manual.read_bytes()).hexdigest(),
              "sample_notice": "DRAFT SOURCE PREVIEW ONLY; not a publishable briefing when guards fail.",
              "warnings": warnings, "airports": {}, "offline": {}}
    english_index = agent.build_english_manual_index(agent.extract_pdf_text(str(manual.resolve()))[0])
    for airport in airports:
        # Two synthetic segments exercise both roles without altering the ICS.
        # They exist solely in this offline diagnostic process.
        events = tuple(CalendarEvent(
            uid=f"audit-{index}", summary=f"✈️ 9C000{index} {left}→{right}",
            start=datetime(2026, 1, 1, 9 + index), end=datetime(2026, 1, 1, 10 + index),
            description="", location="", properties={})
            for index, (left, right) in enumerate(((airport, "测试中转机场"), ("测试中转机场", airport))))
        duty = agent.DutyContext(events)
        core = agent.airport_operational_facts(duty, airport, threats.get(airport, []),
                                              date.fromisoformat(target), records.get(airport, []))
        typical = agent.bilingual_typical_facts(airport, risks.get(airport, []), threats.get(airport, []),
                                              date.fromisoformat(target).month, 10000,
                                              records.get(airport, []), duty, date.fromisoformat(target))
        all_facts = [*typical, *core]
        en_typical, en_core, en_all = agent.english_briefing_fact_sets(duty, date.fromisoformat(target), records)
        en_airport = [*en_typical[airport], *en_core[airport]]
        diagnostics = agent.validate_bilingual_facts(all_facts)
        errors = [*agent.validate_cross_language_conflicts(all_facts, en_airport, records),
                  *agent.validate_airport_fact_bindings(airport, all_facts),
                  *agent.validate_english_source_facts(airport, en_airport)]
        if not en_core[airport]:
            errors.append("NO_ENGLISH_CORE_SOURCE_FACTS: necessary English material not reliably available")
        if not core:
            errors.append("NO_CORE_SOURCE_FACTS_EXTRACTED: empty extraction is not successful acceptance")
        report["airports"][airport] = {
            "icao": codes[airport], "status": "FAILED_SAFE" if errors else "SUCCESS",
            "errors": errors, "typical": [asdict(fact) for fact in typical],
            "core": [asdict(fact) for fact in core],
            "english_core": [asdict(fact) for fact in en_core[airport]],
            "english_typical": [asdict(fact) for fact in en_typical[airport]],
            "bilingual_pairing_diagnostics": diagnostics,
            "chinese_core_preview": "\n\n".join(fact.zh for fact in core),
            "english_core_preview": "\n\n".join(agent.english_fact_output(fact) for fact in en_core[airport]),
            "source_records": records.get(airport, []),
        }
        chapters = agent.match_english_manual_chapters(english_index, codes[airport])
        candidates = []
        for chapter in chapters:
            chapter_text = agent.extract_pdf_layout_text(str(manual.resolve()), int(chapter["start_page"]), int(chapter["end_page"]))
            english_facts = agent.extract_english_manual_facts(chapter_text)
            page_map = agent.source_item_page_map(chapter_text.splitlines(), [fact.text for fact in english_facts], int(chapter["start_page"]))
            candidates.extend({**asdict(fact), "source_page": page_map.get(agent.normalize_text(fact.text), f"{chapter['start_page']}-{chapter['end_page']}")} for fact in english_facts)
        report["airports"][airport]["english_chapters"] = chapters
        report["airports"][airport]["english_candidates"] = candidates
        role_samples = {}
        for role, event in zip(("departure", "arrival"), events):
            exclusions = []
            selected = agent.prepare_operational_facts(
                event, airport, date.fromisoformat(target), core,
                max_items=10000, exclusion_log=exclusions,
            )
            role_samples[role] = {
                "selected_fact_ids": [fact.fact_id for fact in selected],
                "chinese_preview": "\n\n".join(agent.chinese_fact_output(fact) for fact in selected),
                "english_preview": "\n\n".join(agent.english_fact_output(fact) for fact in
                    agent.english_briefing_fact_sets(event, date.fromisoformat(target), records)[1][airport]),
                "exclusions": exclusions,
            }
        report["airports"][airport]["role_samples"] = role_samples

    captures = []
    original_chinese = agent.render_chinese_briefing
    original_render = agent.render_english_briefing
    original_validate = agent.validate_bilingual_facts
    original_extract = agent.extract_pdf_text
    original_fact_sets = agent.briefing_fact_sets
    original_english_fact_sets = agent.english_briefing_fact_sets
    selection_trace = {}
    source_text = original_extract(str(manual.resolve()))
    source_digest = report["sha256"]

    def extract(path):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() == source_digest:
            return source_text
        return original_extract(path)

    def chinese(duty, *args, **kwargs):
        content = original_chinese(duty, *args, **kwargs)
        captures.append({"flights": [event.flight_number for event in duty.events],
                         "chinese_preview": content, **selection_trace})
        return content

    def fact_sets(duty, *args, **kwargs):
        result = original_fact_sets(duty, *args, **kwargs)
        selection_trace.clear()
        selection_trace.update(
            routes=[list(event.route) for event in duty.events],
            exclusions=list(kwargs.get("exclusion_log") or []),
        )
        return result

    def render(duty, *args, **kwargs):
        content = original_render(duty, *args, **kwargs)
        captures[-1]["english_preview"] = content
        captures[-1]["english_facts"] = [asdict(fact) for airport in duty.route for fact in [*args[3].get(airport, []), *args[4].get(airport, [])]]
        captures[-1]["english_layout_changes"] = [
            {"fact_id": fact.fact_id, "source_page": fact.source_page, "before": fact.en,
             "after": agent.english_layout_text(fact.en),
             "non_whitespace_unchanged": "".join(fact.en.split()) == "".join(agent.english_layout_text(fact.en).split())}
            for airport in duty.route for fact in [*args[3].get(airport, []), *args[4].get(airport, [])]
            if fact.en != agent.english_layout_text(fact.en)
        ]
        return content

    def english_fact_sets(*args, **kwargs):
        result = original_english_fact_sets(*args, **kwargs)
        selection_trace["english_exclusions"] = list(args[3] if len(args) > 3 else kwargs.get("exclusion_log") or [])
        return result

    def validate(facts):
        errors = original_validate(facts)
        if captures and all(fact.language != "en" for fact in facts):
            captures[-1].update(facts=[asdict(fact) for fact in facts], bilingual_pairing_diagnostics=errors)
        return errors

    agent.render_english_briefing = render
    agent.render_chinese_briefing = chinese
    agent.validate_bilingual_facts = validate
    agent.extract_pdf_text = extract
    agent.briefing_fact_sets = fact_sets
    agent.english_briefing_fact_sets = english_fact_sets
    try:
        with tempfile.TemporaryDirectory(prefix="source-only-acceptance-") as temporary:
            isolated = Path(temporary)
            for directory in ("config", "knowledge"):
                shutil.copytree(repo / directory, isolated / directory)
            for name in ("flight.ics", "crew_calendar_main.py"):
                shutil.copy2(repo / name, isolated / name)
            if input_ref:
                # Read the latest production input into the isolated workspace
                # only. Never alter the checkout's ICS or main branch.
                result = subprocess.run(["git", "show", f"{input_sha}:flight.ics"], cwd=repo, capture_output=True, check=True)
                (isolated / "flight.ics").write_bytes(result.stdout)
            prep = isolated / "flight_preparation"
            prep.mkdir()
            sentinel = "LAST_GOOD_SENTINEL\n"
            protected_files = (f"{target}_航前准备.txt", f"{target}_航前准备_EN.txt", "latest.txt", "latest_en.txt")
            for name in protected_files:
                (prep / name).write_text(sentinel, encoding="utf-8")
            sys.argv = ["flight_prep_agent.py", "--repo", str(isolated), "--target-date", target, "--days-ahead", "1"]
            exit_code = agent.main()
            meta = json.loads((prep / f"{target}_meta.json").read_text(encoding="utf-8"))
            report["offline"] = {
                "input_ref": input_ref or "working-tree",
                "input_sha": input_sha,
                "target_date": target, "status": meta["status"], "exit_code": exit_code,
                "errors": meta.get("errors", []), "groups": captures,
                "success_marker": (prep / ".success").exists(),
                "last_good_preserved_on_failure": all((prep / name).read_text(encoding="utf-8") == sentinel
                    for name in protected_files) if exit_code else None,
                "last_good_files_checked": list(protected_files),
                "generated_files": [path.name for path in prep.glob("*.txt") if path.read_text(encoding="utf-8") != sentinel],
            }
    finally:
        agent.render_english_briefing = original_render
        agent.render_chinese_briefing = original_chinese
        agent.validate_bilingual_facts = original_validate
        agent.extract_pdf_text = original_extract
        agent.briefing_fact_sets = original_fact_sets
        agent.english_briefing_fact_sets = original_english_fact_sets
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(report, output.with_suffix(".md"))
    for airport, result in report["airports"].items():
        print(airport, result["status"], "CORE", len(result["core"]), "ERRORS", len(result["errors"]))
    print("OFFLINE", report["offline"]["status"], "ERRORS", len(report["offline"]["errors"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--airports", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-ref")
    args = parser.parse_args()
    audit(args.repo.resolve(), args.airports, args.target_date, args.output, args.input_ref)
