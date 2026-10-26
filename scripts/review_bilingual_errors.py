"""Expand a committed audit's errors against the current isolated source audit."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent


def review(repo: Path, baseline_ref: str, current_path: Path, output: Path) -> None:
    baseline = json.loads(subprocess.run(
        ["git", "show", f"{baseline_ref}:docs/diagnostics/source-only-manual-audit.json"],
        cwd=repo, capture_output=True, check=True, encoding="utf-8",
    ).stdout)
    current = json.loads(current_path.read_text(encoding="utf-8"))
    entries = []
    for number, error in enumerate(baseline["offline"]["errors"], 1):
        group = next((group for group in baseline["offline"]["groups"] if error.startswith("/".join(group["flights"]))), None)
        new_group = next((item for item in current["offline"]["groups"] if group and item["flights"] == group["flights"]), None)
        entry = {"number": number, "before_error": error, "flights": group["flights"] if group else [],
                 "status": "UNRESOLVED", "source_evidence": []}
        if group and "身份不一致" in error:
            entry["status"] = "UNRESOLVED_DERIVED_PARITY" if any("身份不一致" in value and value.startswith("/".join(group["flights"])) for value in current["offline"]["errors"]) else "RESOLVED_DERIVED_PARITY"
            entry["selected_chinese_ids_before"] = [fact["fact_id"] for fact in group["facts"] if fact["text_zh"]]
            entry["selected_english_ids_before"] = [fact["fact_id"] for fact in group["facts"] if fact["text_en"]]
        elif group:
            fact = next((fact for fact in group["facts"] if re.search(re.escape(fact["fact_id"]) + r"(?!\d)", error)), None)
            if fact:
                match = next((item for item in (new_group or {}).get("facts", []) if item["airport"] == fact["airport"] and agent.compact_key(item["text_zh"]) == agent.compact_key(fact["text_zh"])), None)
                if match is None:
                    containing = [item for item in (new_group or {}).get("facts", [])
                        if item["airport"] == fact["airport"] and item["category"] == fact["category"]
                        and agent.compact_key(fact["text_zh"]) in agent.compact_key(item["text_zh"])]
                    match = containing[0] if len(containing) == 1 else None
                airport = current["airports"].get(fact["airport"], {})
                phase = agent._chinese_manual_fact_phase(fact["source_text_zh"], fact["category"])
                evidence = {
                    "airport": fact["airport"], "icao": airport.get("icao"), "category": fact["category"],
                    "operational_phase": fact["operational_phase"], "pairing_phase": phase,
                    "fact_id_before": fact["fact_id"], "source_record_ids": fact["source_record_ids"],
                    "source_file": fact["source_file"], "source_version": fact["source_version"],
                    "source_page_before": fact["source_page"], "source_heading": fact["source_heading"],
                    "source_section": fact["source_section"], "chinese_exact_text": fact["text_zh"],
                    "english_before": fact["text_en"], "english_page_before": fact["english_source_page"],
                    "english_chapters": airport.get("english_chapters", []),
                    "same_phase_english_candidates": [candidate for candidate in airport.get("english_candidates", []) if candidate["category"] == fact["category"] and candidate["phase"] == phase],
                    "other_phase_english_candidates": [candidate for candidate in airport.get("english_candidates", []) if candidate["category"] == fact["category"] and candidate["phase"] != phase],
                    "chinese_tokens": sorted(agent.manual_pairing_tokens(fact["text_zh"])),
                    "english_tokens_before": sorted(agent.manual_pairing_tokens(fact["text_en"])),
                }
                if match:
                    validation = agent.validate_bilingual_facts([agent.BilingualFact(**match)])
                    evidence.update(fact_id_after=match["fact_id"], source_page_after=match["source_page"],
                                    english_after=match["text_en"], english_page_after=match["english_source_page"],
                                    validation_after=validation,
                                    english_tokens_after=sorted(agent.manual_pairing_tokens(match["text_en"])))
                    entry["status"] = "UNRESOLVED" if validation else "COUNTERPART_VALIDATED"
                else:
                    entry["status"] = "NOT_SELECTED_REQUIRES_EXCLUSION_REVIEW"
                    evidence["duty_routes"] = (new_group or {}).get("routes", [])
                    evidence["exclusion_candidates"] = [item for item in (new_group or {}).get("exclusions", [])
                        if item.get("airport") == fact["airport"] and item.get("clause") and (
                            agent.compact_key(str(item.get("clause", ""))) in agent.compact_key(fact["text_zh"])
                            or agent.compact_key(fact["text_zh"]) in agent.compact_key(str(item.get("clause", ""))))]
                entry["source_evidence"].append(evidence)
        entries.append(entry)
    result = {"baseline_ref": baseline_ref, "manual": current["manual"], "sha256": current["sha256"],
              "errors_before": len(baseline["offline"]["errors"]), "errors_after": len(current["offline"]["errors"]),
              "outcomes": dict(Counter(entry["status"] for entry in entries)), "entries": entries,
              "current_errors": current["offline"]["errors"],
              "notice": "Candidate absence is not proof of source absence. Not-selected records are not counted as fixed."}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# PR #58: every baseline bilingual error", "",
             "Diagnostic evidence only. Not a formal briefing; unresolved items remain FAILED_SAFE.",
             "", f"Before: {result['errors_before']}; current: {result['errors_after']}", "",
             "The JSON companion includes every same-phase and other-phase English candidate in source order.", ""]
    for entry in entries:
        lines.extend([f"## {entry['number']}: {'/'.join(entry['flights'])}", "",
                      entry["before_error"], "", "Outcome: " + entry["status"], ""])
        for evidence in entry["source_evidence"]:
            lines.extend([f"Airport: {evidence['airport']} / {evidence['icao']}; category: {evidence['category']}; phase: {evidence['operational_phase']}",
                          "", "Source record: " + ", ".join(evidence["source_record_ids"]), "",
                          "Chinese page: " + str(evidence.get("source_page_after") or evidence["source_page_before"]), "",
                          evidence["chinese_exact_text"], "",
                          "English page: " + str(evidence.get("english_page_after") or evidence["english_page_before"]), "",
                          evidence.get("english_after", evidence["english_before"]) or "UNRESOLVED: no safely paired English text.", "",
                          "Validation: " + str(evidence.get("validation_after", "Not selected; see exclusion evidence in JSON")), ""])
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("errors_before", "errors_after", "outcomes")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.repo.resolve(), args.baseline_ref, args.current, args.output)
