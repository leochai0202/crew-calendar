"""Real-ICS/manual acceptance in one disposable workspace, never publication."""
import argparse
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accept(repo: Path, output: Path, dates: list[str], input_ref: str):
    sha = subprocess.check_output(["git", "rev-parse", input_ref], cwd=repo, text=True).strip()
    result = dict(input_sha=sha, dates={})
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flight-prep-review-") as temporary:
        isolated = Path(temporary)
        for directory in ("config", "knowledge"):
            shutil.copytree(repo / directory, isolated / directory)
        shutil.copy2(repo / "crew_calendar_main.py", isolated / "crew_calendar_main.py")
        for name in ("flight.ics", "crew_schedule.ics"):
            (isolated / name).write_bytes(subprocess.check_output(["git", "show", f"{sha}:{name}"], cwd=repo))
        manual = agent.find_latest_airport_manual(isolated / "knowledge")
        result.update(manual=manual.name, manual_sha256=digest(manual), ics_sha256=digest(isolated / "flight.ics"))
        formal = isolated / "flight_preparation"
        formal.mkdir()
        for day in dates:
            names = ["latest.txt", "latest_en.txt", "latest_meta.json", ".success",
                     f"{day}_航前准备.txt", f"{day}_航前准备_EN.txt", f"{day}_meta.json"]
            for name in names:
                (formal / name).write_text(json.dumps({"status": "SUCCESS", "target_date": day})
                    if name.endswith(".json") else "LAST_GOOD_SENTINEL\n", encoding="utf-8")
            before = {p.name: digest(p) for p in formal.iterdir() if p.is_file()}
            config_before = {p.name: digest(p) for p in (isolated / "config").iterdir() if p.is_file()}
            argv = ["flight_prep_agent.py", "--repo", str(isolated), "--target-date", day, "--days-ahead", "1"]
            with patch.object(sys, "argv", argv + ["--mode", "preview"]), patch.object(agent, "append_github_summary"):
                code = agent.main()
            preview = isolated / "agent_output/flight_prep/previews" / day
            meta = json.loads((preview / "preview_meta.json").read_text(encoding="utf-8"))
            assert code == 3 and meta["status"] == "PREVIEW" and not meta["publishable"]
            assert before == {p.name: digest(p) for p in formal.iterdir() if p.is_file()}
            assert config_before == {p.name: digest(p) for p in (isolated / "config").iterdir() if p.is_file()}
            assert not (preview / ".success").exists()
            fact_fields = {item.name for item in fields(agent.BilingualFact)}
            for group in meta["groups"]:
                for language, key in (("zh", "airport_fact_sources"), ("en", "english_fact_sources")):
                    body = (preview / group["preview_files"][language]).read_text(encoding="utf-8")
                    assert body.startswith("PREVIEW /")
                    for records in group[key].values():
                        for raw in records:
                            fact = agent.BilingualFact(**{key: value for key, value in raw.items() if key in fact_fields})
                            paragraph = agent.chinese_fact_output(fact) if language == "zh" else agent.english_paragraph_output(fact)
                            assert paragraph and paragraph in body, (day, language, fact.fact_id)
            shutil.copytree(preview, output / day, dirs_exist_ok=True)
            with patch.object(sys, "argv", argv), patch.object(agent, "append_github_summary"):
                release_code = agent.main()
            release_meta = json.loads((formal / f"{day}_meta.json").read_text(encoding="utf-8"))
            old_text_preserved = all(digest(formal / name) == value for name, value in before.items() if name.endswith(".txt"))
            if release_code:
                assert not (formal / ".success").exists() and old_text_preserved
            result["dates"][day] = dict(preview_status=meta["status"], release_status=release_meta["status"],
                release_exit_code=release_code, errors=meta["errors"],
                preview_preserves_formal_and_config=True, failed_release_preserves_last_good=old_text_preserved if release_code else None,
                all_selected_body_facts_present=True, complete_bilingual_groups=True,
                release_success_marker=(formal / ".success").exists(),
                groups=[dict(flights=g["flight_numbers"], foreign_crew=g["foreign_crew_detected"],
                    chinese_fact_count=sum(len(x) for x in g["airport_fact_sources"].values()),
                    english_fact_count=sum(len(x) for x in g["english_fact_sources"].values()),
                    chinese_preview=g["preview_files"]["zh"], english_preview=g["preview_files"]["en"])
                    for g in meta["groups"]])
            shutil.copy2(repo / "config/airport_experience.json", isolated / "config/airport_experience.json")
            print(day, "PREVIEW", "RELEASE", release_meta["status"], "ERRORS", len(meta["errors"]), flush=True)
    (output / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--input-ref", default="origin/main")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dates", nargs="+", required=True)
    args = parser.parse_args()
    accept(args.repo.resolve(), args.output.resolve(), args.dates, args.input_ref)
