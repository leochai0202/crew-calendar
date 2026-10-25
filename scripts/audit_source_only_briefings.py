"""Read real manual facts and run isolated offline preparation acceptance."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


def write_report(report: dict, path: Path) -> None:
    lines = ["# Source-only manual extraction acceptance (DRAFT)", "",
             "This is a diagnostic preview, not a valid production briefing. FAILED_SAFE outputs must not be published.",
             "", f"Manual: {report['manual']}", f"Version: {report['version']}",
             f"SHA256: `{report['sha256']}`", "",
             "## Real-manual airport checks", "",
             "| Airport | ICAO | Core candidates selected | English available | Acceptance | Errors |",
             "|---|---|---:|---:|---|---:|"]
    for airport, result in report["airports"].items():
        lines.append(f"| {airport} | {result['icao']} | {len(result['core'])} | {sum(bool(f['text_en']) for f in result['core'])} | {result['status']} | {len(result['errors'])} |")
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


def audit(repo: Path, airports: list[str], target: str, output: Path) -> None:
    manual = agent.find_latest_airport_manual(repo / "knowledge")
    assert manual
    mapping = agent.extract_airport_mapping(repo / "crew_calendar_main.py")
    codes = {airport: agent.resolve_icao(airport, mapping) for airport in airports}
    risks, threats, records, warnings, source, version, _ = agent.airport_risks(repo, airports, codes, 10000)
    report = {"manual": manual.name, "version": version,
              "sha256": hashlib.sha256(manual.read_bytes()).hexdigest(),
              "sample_notice": "DRAFT SOURCE PREVIEW ONLY; not a publishable briefing when guards fail.",
              "warnings": warnings, "airports": {}, "offline": {}}
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
        errors = [*agent.validate_bilingual_facts(all_facts), *agent.validate_airport_fact_bindings(airport, all_facts)]
        report["airports"][airport] = {
            "icao": codes[airport], "status": "FAILED_SAFE" if errors else "SUCCESS",
            "errors": errors, "typical": [asdict(fact) for fact in typical],
            "core": [asdict(fact) for fact in core],
            "chinese_core_preview": "\n\n".join(fact.zh for fact in core),
            "english_core_preview": "\n\n".join(fact.en for fact in core if fact.en),
            "source_records": records.get(airport, []),
        }
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
                "english_preview": "\n\n".join(fact.en for fact in selected if fact.en),
                "exclusions": exclusions,
            }
        report["airports"][airport]["role_samples"] = role_samples

    captures = []
    original_chinese = agent.render_chinese_briefing
    original_render = agent.render_english_briefing
    original_validate = agent.validate_bilingual_facts
    original_extract = agent.extract_pdf_text
    source_text = original_extract(str(manual.resolve()))
    source_digest = report["sha256"]

    def extract(path):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() == source_digest:
            return source_text
        return original_extract(path)

    def chinese(duty, *args, **kwargs):
        content = original_chinese(duty, *args, **kwargs)
        captures.append({"flights": [event.flight_number for event in duty.events],
                         "chinese_preview": content})
        return content

    def render(duty, *args, **kwargs):
        content = original_render(duty, *args, **kwargs)
        captures[-1]["english_preview"] = content
        return content

    def validate(facts):
        errors = original_validate(facts)
        if captures:
            captures[-1].update(facts=[asdict(fact) for fact in facts], bilingual_errors=errors)
        return errors

    agent.render_english_briefing = render
    agent.render_chinese_briefing = chinese
    agent.validate_bilingual_facts = validate
    agent.extract_pdf_text = extract
    try:
        with tempfile.TemporaryDirectory(prefix="source-only-acceptance-") as temporary:
            isolated = Path(temporary)
            for directory in ("config", "knowledge"):
                shutil.copytree(repo / directory, isolated / directory)
            for name in ("flight.ics", "crew_calendar_main.py"):
                shutil.copy2(repo / name, isolated / name)
            prep = isolated / "flight_preparation"
            prep.mkdir()
            sentinel = "LAST_GOOD_SENTINEL\n"
            for name in (f"{target}_航前准备.txt", "latest.txt", "latest_en.txt"):
                (prep / name).write_text(sentinel, encoding="utf-8")
            sys.argv = ["flight_prep_agent.py", "--repo", str(isolated), "--target-date", target, "--days-ahead", "1"]
            exit_code = agent.main()
            meta = json.loads((prep / f"{target}_meta.json").read_text(encoding="utf-8"))
            report["offline"] = {
                "target_date": target, "status": meta["status"], "exit_code": exit_code,
                "errors": meta.get("errors", []), "groups": captures,
                "success_marker": (prep / ".success").exists(),
                "last_good_preserved_on_failure": all((prep / name).read_text(encoding="utf-8") == sentinel
                    for name in (f"{target}_航前准备.txt", "latest.txt", "latest_en.txt")) if exit_code else None,
                "generated_files": [path.name for path in prep.glob("*.txt") if path.read_text(encoding="utf-8") != sentinel],
            }
    finally:
        agent.render_english_briefing = original_render
        agent.render_chinese_briefing = original_chinese
        agent.validate_bilingual_facts = original_validate
        agent.extract_pdf_text = original_extract
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
    args = parser.parse_args()
    audit(args.repo.resolve(), args.airports, args.target_date, args.output)
