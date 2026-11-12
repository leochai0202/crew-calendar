"""Real-ICS/manual acceptance in one disposable workspace, never publication."""
import argparse
from dataclasses import fields
from datetime import date
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crew_agents import flight_prep_agent as agent
from scripts.check_flight_prep_schedule import evaluate_preparation


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_locked_format(body: str, language: str):
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    assert body.startswith("我是来自飞行十五中队的副驾驶" if language == "zh" else "I am ")
    heading = ("上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）："
               if language == "zh" else "Latest PF/PM feedback:")
    assert paragraphs[1] == heading
    assert paragraphs[2].startswith("上一次作为PF教员评价：" if language == "zh" else "As PF,")
    assert paragraphs[3].startswith("作为PM机长评价：" if language == "zh" else "As PM,")
    assert paragraphs[4] == ("典型不安全事件：" if language == "zh" else "Typical unsafe events:")
    assert ("核心威胁：" if language == "zh" else "Core threats:") in paragraphs
    assert not re.search(r"(?m)^\s*(?:\d+[、)]|\d+\.(?!\d)|[•●▪])\s*\S", body)
    assert not any(title in body for title in ("本次航班整体风险", "航路及通用风险", "个人对本次航班中识别的风险",
                                             "Overall flight risk", "Enroute and general risks"))


def verify_copy_buttons(path: Path) -> int:
    from playwright.sync_api import sync_playwright
    # Disposable, non-persistent browser; no production profile/session, no site
    # navigation and no writes to the user's actual clipboard.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True,
            args=["--disable-background-networking", "--no-first-run"])
        try:
            page = browser.new_page()
            page.set_content(path.read_text(encoding="utf-8"))
            page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => {window.testCopy = text;}}});")
            buttons = page.locator("button[data-copy]")
            for index in range(buttons.count()):
                button = buttons.nth(index)
                expected = page.locator("#" + button.get_attribute("data-copy")).input_value()
                page.evaluate("window.testCopy = null")
                button.click()
                page.wait_for_function("window.testCopy !== null")
                copied = page.evaluate("window.testCopy")
                assert copied == expected
                verify_locked_format(copied, button.get_attribute("data-copy").rsplit("-", 1)[1])
                assert not any(label in copied for label in (
                    "PREVIEW", "FAILED_SAFE", "UNVERIFIED", "NOT FOR RELEASE", "INCOMPLETE ENGLISH"))
                assert page.locator("#copy-status").inner_text() == "已复制 / Copied"
            return buttons.count()
        finally:
            browser.close()


def accept(repo: Path, output: Path, dates: list[str], input_ref: str, verify_copy_ui: bool = False):
    sha = subprocess.check_output(["git", "rev-parse", input_ref], cwd=repo, text=True).strip()
    result = dict(input_sha=sha, dates={})
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flight-prep-review-") as temporary:
        isolated = Path(temporary)
        for directory in ("config", "knowledge"):
            shutil.copytree(repo / directory, isolated / directory)
        shutil.copy2(repo / "crew_calendar_main.py", isolated / "crew_calendar_main.py")
        for name in ("flight.ics", "crew_schedule.ics", "config/airport_experience.json"):
            (isolated / name).write_bytes(subprocess.check_output(["git", "show", f"{sha}:{name}"], cwd=repo))
        experience_snapshot = (isolated / "config/airport_experience.json").read_bytes()
        manual = agent.find_latest_airport_manual(isolated / "knowledge")
        result.update(manual=manual.name, manual_sha256=digest(manual), ics_sha256=digest(isolated / "flight.ics"))
        formal = isolated / "flight_preparation"
        formal.mkdir()
        for day in dates:
            names = ["latest.txt", "latest_en.txt", "latest_meta.json", ".success",
                     f"{day}_航前准备.txt", f"{day}_航前准备_EN.txt", f"{day}_meta.json"]
            flights = agent.select_continuous_flight_group(agent.parse_ics(isolated / "flight.ics"), date.fromisoformat(day))
            flight_groups = agent.split_flight_prep_groups_by_flight_number(flights)
            for index, items in enumerate(flight_groups, 1):
                names += [agent.prep_group_output_name(date.fromisoformat(day), index, len(flight_groups), items, english=en)
                          for en in (False, True)]
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
                for language, filename in group["source_copy_files"].items():
                    copied = (preview / filename).read_text(encoding="utf-8")
                    verify_locked_format(copied, language)
                    assert not any(label in copied for label in (
                        "PREVIEW", "FAILED_SAFE", "UNVERIFIED", "NOT FOR RELEASE", "INCOMPLETE ENGLISH"))
                    for raw in group["source_copy_fact_sources"][language]:
                        fact = agent.BilingualFact(**{key: value for key, value in raw.items() if key in fact_fields})
                        paragraph = agent.chinese_fact_output(fact) if language == "zh" else agent.english_paragraph_output(fact)
                        assert paragraph and paragraph in copied, (day, language, fact.fact_id)
                        if language == "en":
                            assert not fact.translation_provenance and fact.english_source == "source_backed"
                for language, key in (("zh", "airport_fact_sources"), ("en", "english_fact_sources")):
                    body = (preview / group["preview_files"][language]).read_text(encoding="utf-8")
                    verify_locked_format(body, language)
                    assert body.rstrip().endswith("PREVIEW / 审核预览 — NOT FOR RELEASE / 不得作为正式运行资料发布")
                    feedback = agent.feedback_text if language == "zh" else agent.feedback_text_en
                    profile = json.loads((isolated / "config/pilot_profile.json").read_text(encoding="utf-8"))
                    assert "\n\n" + feedback(profile) + "\n\n" in body
                    assert not re.search(r"(?m)^\s*(?:\d+[、)]|\d+\.(?!\d)|[•●▪])\s*\S", body)
                    assert not any(title in body for title in ("本次航班整体风险", "航路及通用风险", "个人对本次航班中识别的风险"))
                    heading = "核心威胁：" if language == "zh" else "Core threats:"
                    assert heading + "\n\n" in body
                    for records in group[key].values():
                        for raw in records:
                            fact = agent.BilingualFact(**{key: value for key, value in raw.items() if key in fact_fields})
                            paragraph = agent.chinese_fact_output(fact) if language == "zh" else agent.english_paragraph_output(fact)
                            assert paragraph and paragraph in body, (day, language, fact.fact_id)
            # Preserve the explicit bilingual review even when automatic release
            # only requires a Chinese version for this duty.
            shutil.copytree(preview, output / day, dirs_exist_ok=True)
            preview_copy_count = verify_copy_buttons(preview / "copy.html") if verify_copy_ui else None
            summaries = []
            with patch.object(sys, "argv", argv), patch.object(agent, "append_github_summary", summaries.append):
                release_code = agent.main()
            release_meta = json.loads((formal / f"{day}_meta.json").read_text(encoding="utf-8"))
            released_groups = [group for group in release_meta.get("prep_groups", []) if group.get("release_eligible")]
            reviewed_by_index = {group["group_index"]: group for group in meta["groups"]}
            assert all(not reviewed_by_index[g["group_index"]]["foreign_crew_detected"] or g["english_output"]
                       for g in released_groups)
            changed_allowed = {name for group in released_groups for name in (group["output"], group["english_output"]) if name}
            if release_meta["status"] == "SUCCESS":
                changed_allowed.update({"latest.txt", f"{day}_航前准备.txt"})
                if release_meta.get("english_output"):
                    changed_allowed.update({"latest_en.txt", f"{day}_航前准备_EN.txt"})
                else:
                    assert not (formal / "latest_en.txt").exists()
                    before.pop("latest_en.txt")  # the existing all-success Chinese-only behavior
            old_text_preserved = all(digest(formal / name) == value for name, value in before.items()
                                     if name.endswith(".txt") and name not in changed_allowed)
            assert old_text_preserved
            if release_code:
                assert not (formal / ".success").exists() and old_text_preserved
            else:
                assert released_groups and (formal / ".success").is_file()
                assert all((formal / name).is_file() and digest(formal / name) != before.get(name)
                           for name in changed_allowed)
            scheduling = evaluate_preparation(isolated, date.fromisoformat(day))
            if released_groups:
                assert not scheduling.should_dispatch
            shutil.copy2(preview / "copy.html", output / day / "release-copy.html")
            (output / day / "actions_summary.md").write_text("\n\n".join(summaries), encoding="utf-8")
            release_folder = output / day / "release"
            release_folder.mkdir(exist_ok=True)
            for name in changed_allowed:
                if (formal / name).is_file():
                    shutil.copy2(formal / name, release_folder / name)
            copied = verify_copy_buttons(preview / "copy.html") if verify_copy_ui else None
            result["dates"][day] = dict(preview_status=meta["status"], release_status=release_meta["status"],
                release_exit_code=release_code, errors=meta["errors"],
                preview_preserves_formal_and_config=True, failed_release_preserves_last_good=old_text_preserved if release_code else None,
                all_selected_body_facts_present=True,
                required_bilingual_content_complete=all(
                    not group["foreign_crew_detected"] or all(
                        any(item["category"] == "core" for item in group["english_fact_sources"].get(airport, []))
                        for airport in group["airports"])
                    for group in meta["groups"]),
                incomplete_bilingual_release_prevented=True,
                rendered_template_checks_passed=True,
                protected_last_good_preserved=old_text_preserved,
                copy_ui_buttons_verified=copied, preview_copy_buttons_verified=preview_copy_count,
                scheduler_status=scheduling.status,
                release_success_marker=(formal / ".success").exists(),
                groups=[dict(flights=g["flight_numbers"], foreign_crew=g["foreign_crew_detected"],
                    chinese_fact_count=sum(len(x) for x in g["airport_fact_sources"].values()),
                    english_fact_count=sum(len(x) for x in g["english_fact_sources"].values()),
                    release_eligible=g["release_eligible"], release_errors=g["errors"],
                    chinese_preview=g["preview_files"]["zh"], english_preview=g["preview_files"]["en"])
                    for g in meta["groups"]])
            (isolated / "config/airport_experience.json").write_bytes(experience_snapshot)
            print(day, "PREVIEW", "RELEASE", release_meta["status"], "ERRORS", len(meta["errors"]), flush=True)
    (output / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--input-ref", default="origin/main")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--verify-copy-ui", action="store_true")
    args = parser.parse_args()
    accept(args.repo.resolve(), args.output.resolve(), args.dates, args.input_ref, args.verify_copy_ui)
