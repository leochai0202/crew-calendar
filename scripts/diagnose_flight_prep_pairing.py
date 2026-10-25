"""Offline bilingual evidence only; never writes production preparation files."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def expand_review(evidence: dict, review: dict) -> None:
    """Attach every status error to its full fact/candidate evidence."""
    evidence["page_review"] = review
    findings = review["source_findings"]
    for result in evidence["results"].values():
        expanded = []
        for number, error in enumerate(result["all_errors"], 1):
            group = next(g for g in result["groups"] if error.startswith(g["flight_group"] + "："))
            rows = [r for r in group["fact_errors"] if any(reason in error for reason in r["failure_reasons"])]
            matched_findings = [f for f in findings if any(
                set(f["source_record_ids"]) & set(r["source_record_ids"])
                and all(marker in r["selected_chinese_text"] for marker in f.get("selected_clause_markers", []))
                for r in rows)]
            matched = [f["id"] for f in matched_findings]
            classification = sorted({f["classification"] for f in matched_findings})
            if "身份不一致" in error:
                classification = ["C (dependent parity failure, guard unchanged)"]
            elif not classification:
                classification = ["C" if "配对缺失" in error else "B/C"]
            elif "A" in classification and "配对缺失" not in error:
                classification.append("C")
            expanded.append({"number": number, "flight_group": group["flight_group"],
                             "error": error, "fact_evidence": rows,
                             "classification": classification,
                             "page_review_finding_ids": matched,
                             "aggregate_dependency": "selected fact ID parity" if "身份不一致" in error else "",
                             "aggregate_selected_facts": group["selected_facts"] if "身份不一致" in error else []})
        result["expanded_errors"] = expanded


def write_review_markdown(before: dict, after: dict, review: dict, path: Path) -> None:
    lines = ["# PR #56 bilingual pairing evidence", "",
             f"Synchronized main: `{review['latest_main_sha']}`. PR remains draft; both dates remain FAILED_SAFE.",
             "", "This is diagnostic evidence, not an official briefing. No translated replacement or source spelling was generated.",
             "", "## Before / after", "", "| Target | Before errors | After errors | Chinese selected source IDs unchanged |",
             "|---|---:|---:|---|"]
    for date, result in after["results"].items():
        old = before["results"][date]
        unchanged = all({i for f in left["selected_facts"] for i in f["source_fact_ids"]}
                        == {i for f in right["selected_facts"] for i in f["source_fact_ids"]}
                        for left, right in zip(old["groups"], result["groups"]))
        lines.append(f"| {date} | {len(old['all_errors'])} | {len(result['all_errors'])} | {unchanged} |")
    lines += ["", "## Page-level classifications", "",
              "A = genuinely absent; B = extraction/token representation; C = structure/phase/order; D = source conflict or unresolved source-language semantic difference.",
              "Source-language review entries are distinguished from proven waypoint/unit conflicts; they do not authorize an automatic correction.", ""]
    for finding in review["source_findings"]:
        lines += [f"### {finding['id']} ({finding['classification']})", "",
                  f"ICAO: {finding['icao']}; Chinese page: {finding['chinese_page']}; English pages reviewed: {finding['english_pages_reviewed']}",
                  f"Source record IDs: `{finding['source_record_ids']}`", "",
                  f"Status: {finding['status']}; selected dates: {finding['selected_dates']}", ""]
        for field in ("chinese_exact_clause", "english_exact_clause", "evidence", "selection_note", "cross_reference_conclusion"):
            if finding.get(field):
                lines += [f"**{field}:** {finding[field]}", ""]
    lines += ["## W19 complete page contexts and cross-check", ""]
    for term, pages in after["waypoint_cross_references"].items():
        for page, value in pages.items():
            lines += [f"### {term} - PDF page {page}", "", "```text", value, "```", ""]
    for label, report in (("BEFORE", before), ("AFTER", after)):
        lines += [f"## {label}: every validation error", ""]
        for date, result in report["results"].items():
            for entry in result["expanded_errors"]:
                lines += [f"### {label} {date} error {entry['number']} - {entry['flight_group']}", "",
                          entry["error"], "",
                          f"Classification: {entry['classification']}", "",
                          f"Page-review findings: {entry['page_review_finding_ids']}", ""]
                if entry["aggregate_dependency"]:
                    lines += ["Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.", ""]
                for row in entry["fact_evidence"]:
                    lines += ["| Field | Evidence |", "|---|---|"]
                    fields = ("airport", "icao", "category", "operational_phase", "fact_id", "source_fact_ids", "source_record_ids",
                              "chinese_source_pages", "production_source_page_metadata", "chinese_source_heading", "chinese_source_section",
                              "matched_english_chapter", "pairing_source_phases", "selected_chinese_text", "source_original_texts",
                              "pairing_result", "chinese_critical_tokens", "english_critical_tokens", "failure_reasons")
                    for field in fields:
                        value = str(row[field]).replace("|", "\\|").replace("\n", " ")
                        lines.append(f"| {field} | {value} |")
                    lines += ["", "Same pairing-phase English candidates, in original extraction order:", ""]
                    for candidate in row["same_phase_english_candidates"]:
                        lines += [f"- {candidate['category']}/{candidate['phase']} sequence {candidate['sequence']}: {candidate['text']}"]
                    lines += [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def diagnose(repo: Path, dates: list[str], page_cache: Path | None = None) -> dict:
    manual = agent.find_latest_airport_manual(repo / "knowledge")
    assert manual is not None
    digest = hashlib.sha256(manual.read_bytes()).hexdigest()
    cached = json.loads(page_cache.read_text(encoding="utf-8")) if page_cache and page_cache.exists() else {}
    pages = {int(k): v for k, v in cached.get("pages", {}).items()} if cached.get("sha256") == digest else {}
    if not pages:
        reader = agent.PdfReader(str(manual))
        for number, page in enumerate(reader.pages, 1):
            pages[number] = agent.normalize_pdf_page(page.extract_text() or "")
        if page_cache:
            page_cache.write_text(json.dumps({"sha256": digest, "pages": pages}, ensure_ascii=False), encoding="utf-8")
    manual_text = "\n\n".join(pages.values())
    # Reuse exactly the production page normalization, without re-extracting
    # all pages for every offline target. No parser or auth behavior is changed.
    agent.extract_pdf_text = lambda _: (manual_text, ())
    index = agent.build_english_manual_index(manual_text)
    chinese_headers = [(number, line) for number, value in pages.items()
                       for line in value.splitlines() if agent.is_manual_airport_header(line)]
    mapping = agent.extract_airport_mapping(repo / "crew_calendar_main.py")
    chapters = {}
    captures = []
    records = {}
    group = ""
    original_risks = agent.airport_risks
    original_render = agent.render_chinese_briefing
    original_validate = agent.validate_bilingual_facts

    def risks(*args, **kwargs):
        result = original_risks(*args, **kwargs)
        records.update(result[2])
        return result

    def render(duty, *args, **kwargs):
        nonlocal group
        group = "/".join(event.flight_number for event in duty.events)
        return original_render(duty, *args, **kwargs)

    def validate(facts):
        errors = original_validate(facts)
        rows = []
        for fact in facts:
            specific = [e for e in original_validate([fact])
                        if not e.startswith("中英文选定事实身份不一致")]
            if not specific:
                continue
            icao = agent.resolve_icao(fact.airport, mapping)
            if icao not in chapters:
                chapter = agent.match_english_manual_chapter(index, icao)
                assert chapter is not None
                layout = agent.extract_pdf_layout_text(
                    str(manual.resolve()), chapter["start_page"], chapter["end_page"])
                chapters[icao] = {
                    **chapter, "layout_text": layout,
                    "candidates": [asdict(f) for f in agent.extract_english_manual_facts(layout)],
                    "pages": {str(p): pages[p] for p in range(chapter["start_page"], chapter["end_page"] + 1)},
                }
            chapter = chapters[icao]
            member_records = [r for r in records.get(fact.airport, [])
                              if r.get("source_record_id") in fact.source_record_ids]
            originals = list(fact.source_original_texts or fact.source_clauses or (fact.text_zh,))
            pairing_phases = sorted({agent._chinese_manual_fact_phase(value, fact.category)
                                     for value in originals})
            source_pages = []
            allowed_pages = set()
            for position, (start, heading) in enumerate(chinese_headers):
                if compact(heading) not in compact(fact.source_heading):
                    continue
                end = chinese_headers[position + 1][0] - 1 if position + 1 < len(chinese_headers) else max(pages)
                allowed_pages.update(range(start, max(start, end) + 1))
            for original in originals:
                # Locate by multiple original substrings, not by translated text.
                needles = [compact(s) for s in re.split(r"[。；，：]", original)
                           if len(compact(s)) >= 10]
                scores = {number: sum(len(n) for n in needles if n in compact(value))
                          for number, value in pages.items() if number in allowed_pages}
                best = max(scores.values(), default=0)
                if best:
                    source_pages.extend(n for n, score in scores.items() if score == best)
            rows.append({
                "flight_group": group, "airport": fact.airport, "icao": icao,
                "category": fact.category, "operational_phase": fact.operational_phase,
                "fact_id": fact.fact_id, "source_fact_ids": fact.source_fact_ids,
                "source_record_ids": fact.source_record_ids,
                "selected_chinese_text": fact.text_zh,
                "chinese_source_pages": sorted(set(source_pages)),
                "production_source_page_metadata": fact.source_page,
                "chinese_source_heading": fact.source_heading,
                "chinese_source_section": fact.source_section,
                "source_original_texts": originals, "source_records": member_records,
                "matched_english_chapter": {k: v for k, v in chapter.items()
                                            if k not in {"layout_text", "candidates", "pages"}},
                "pairing_source_phases": pairing_phases,
                "same_phase_english_candidates": [c for c in chapter["candidates"]
                                                   if c["category"] == fact.category and c["phase"] in pairing_phases],
                "render_phase_english_candidates": [c for c in chapter["candidates"]
                                                     if c["category"] == fact.category and c["phase"] == fact.operational_phase],
                "pairing_result": fact.text_en, "english_source": fact.english_source,
                "chinese_critical_tokens": sorted(agent.manual_pairing_tokens(fact.text_zh)),
                "english_critical_tokens": sorted(agent.manual_pairing_tokens(fact.text_en)),
                "failure_reasons": specific,
            })
        captures.append({"flight_group": group, "errors": errors, "fact_errors": rows,
                         "selected_fact_ids": [f.fact_id for f in facts],
                         "selected_facts": [asdict(f) for f in facts]})
        return errors

    agent.airport_risks = risks
    agent.render_chinese_briefing = render
    agent.validate_bilingual_facts = validate
    results = {}
    try:
        with tempfile.TemporaryDirectory(prefix="pr56-evidence-") as temporary:
            isolated = Path(temporary)
            for directory in ("config", "knowledge"):
                shutil.copytree(repo / directory, isolated / directory)
            for filename in ("flight.ics", "crew_calendar_main.py"):
                shutil.copy2(repo / filename, isolated / filename)
            for target in dates:
                captures.clear()
                sys.argv = ["flight_prep_agent.py", "--repo", str(isolated),
                            "--target-date", target, "--days-ahead", "1"]
                code = agent.main()
                meta = json.loads((isolated / "flight_preparation" / f"{target}_meta.json").read_text(encoding="utf-8"))
                results[target] = {"exit_code": code, "status": meta["status"],
                                   "all_errors": meta.get("errors", []),
                                   "groups": list(captures)}
    finally:
        agent.airport_risks = original_risks
        agent.render_chinese_briefing = original_render
        agent.validate_bilingual_facts = original_validate
    # Keep original complete pages as review evidence; no output contains ICS
    # people, credentials, browser state, or generated official briefing text.
    chinese_pages = sorted({p for result in results.values() for g in result["groups"]
                            for row in g["fact_errors"] for p in row["chinese_source_pages"]})
    cross_references = {term: {str(p): value for p, value in pages.items()
                              if term in compact(value).upper()}
                        for term in ("OLPAB", "OBLAP")}
    return {"manual": manual.name, "manual_sha256": digest,
            "results": results, "english_chapters": chapters,
            "all_source_records": records, "waypoint_cross_references": cross_references,
            "chinese_source_pages": {str(p): pages[p] for p in chinese_pages}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-cache", type=Path)
    parser.add_argument("--agent-revision", help="Read-only git revision for before/after evidence")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--before-report", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    if args.agent_revision:
        source = subprocess.run(["git", "show", f"{args.agent_revision}:crew_agents/flight_prep_agent.py"],
                                cwd=args.repo, capture_output=True, check=True).stdout.decode("utf-8")
        baseline = types.ModuleType("crew_agents.flight_prep_evidence_baseline")
        baseline.__file__ = str(args.repo.resolve() / "crew_agents" / "flight_prep_agent.py")
        sys.modules[baseline.__name__] = baseline
        exec(compile(source, baseline.__file__, "exec"), baseline.__dict__)
        agent = baseline
    evidence = diagnose(args.repo.resolve(), args.dates, args.page_cache)
    if args.review:
        expand_review(evidence, json.loads(args.review.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        if not (args.before_report and args.review):
            parser.error("--markdown requires --before-report and --review")
        write_review_markdown(json.loads(args.before_report.read_text(encoding="utf-8")), evidence,
                              json.loads(args.review.read_text(encoding="utf-8")), args.markdown)
    for target, result in evidence["results"].items():
        print(target, result["status"], "ERRORS", len(result["all_errors"]))
