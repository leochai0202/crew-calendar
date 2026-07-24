from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

VERSION = "maintenance-detector-free-v5-session-auth"
REQUIRED_PYTHON = (
    "crew_calendar_main.py",
    "crew_auth_session.py",
    "clean_ics_people.py",
)
ICS_FILES = (
    "crew_schedule.ics",
    "flight.ics",
    "positioning.ics",
    "training.ics",
    "ferry.ics",
    "other.ics",
)


@dataclass
class Event:
    uid: str
    summary: str
    dtstart: str
    dtend: str


def is_positioning_summary(summary: str) -> bool:
    """Return True for the project's accepted positioning title formats."""
    value = (summary or "").strip()
    return bool(
        re.search(r"置位|POSITIONING", value, re.I)
        or value.startswith("📍")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Free deterministic crew-calendar detector. It only reports and never modifies production files."
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output-dir", default="agent_output/maintenance")
    parser.add_argument("--upstream-conclusion", default="")
    return parser.parse_args()


def unfold_ics(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def field_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        return line.upper(), ""
    left, value = line.split(":", 1)
    name = left.split(";", 1)[0].upper()
    return name, value.strip()


def parse_events(text: str) -> list[Event]:
    events: list[Event] = []
    current: dict[str, str] | None = None
    for line in unfold_ics(text):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT":
            if current is not None:
                events.append(
                    Event(
                        uid=current.get("UID", ""),
                        summary=current.get("SUMMARY", ""),
                        dtstart=current.get("DTSTART", ""),
                        dtend=current.get("DTEND", ""),
                    )
                )
            current = None
            continue
        if current is not None:
            name, value = field_value(line)
            if name in {"UID", "SUMMARY", "DTSTART", "DTEND"} and name not in current:
                current[name] = value
    return events


def parse_ics_datetime(value: str) -> datetime | None:
    cleaned = value.strip().rstrip("Z")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def check_python(repo: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    for filename in REQUIRED_PYTHON:
        path = repo / filename
        if not path.exists():
            errors.append(f"缺少正式文件：{filename}")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{filename} 语法检查失败：{exc.msg}")
            continue
        notes.append(f"{filename} 语法检查通过")

    main_path = repo / "crew_calendar_main.py"
    if main_path.exists():
        text = main_path.read_text(encoding="utf-8", errors="replace")
        if len(text) < 20_000:
            errors.append("crew_calendar_main.py 文件体积异常偏小，可能被截断")
        for required_marker in (
            "CREW_STORAGE_STATE_B64",
            "crew_auth_session",
            "decode_auth_bundle",
        ):
            if required_marker not in text:
                errors.append(
                    "crew_calendar_main.py 未发现正式认证接入："
                    f"{required_marker}"
                )
        if "segment_people_lists[i]" in text and not re.search(r"for\s+i\s*(?:,|in)", text):
            errors.append("crew_calendar_main.py 疑似存在未定义索引 i")

    cleaner_path = repo / "clean_ics_people.py"
    if cleaner_path.exists():
        text = cleaner_path.read_text(encoding="utf-8", errors="replace")
        if len(text) < 2_000:
            errors.append("clean_ics_people.py 文件体积异常偏小，可能被截断")
        if "BEGIN:VEVENT" not in text and "VEVENT" not in text:
            notes.append("清洗脚本未直接出现 VEVENT 字样，请人工确认其读取方式")
    return errors, notes


def check_ics(repo: Path) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    notes: list[str] = []
    stats: dict[str, int] = {}

    for filename in ICS_FILES:
        path = repo / filename
        if not path.exists():
            notes.append(f"未找到 {filename}，本次跳过")
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        begin_event = raw.count("BEGIN:VEVENT")
        end_event = raw.count("END:VEVENT")
        begin_alarm = raw.count("BEGIN:VALARM")
        end_alarm = raw.count("END:VALARM")
        if begin_event != end_event:
            errors.append(f"{filename}：VEVENT 数量不平衡（{begin_event}/{end_event}）")
        if begin_alarm != end_alarm:
            errors.append(f"{filename}：VALARM 数量不平衡（{begin_alarm}/{end_alarm}）")
        for bad in ("ACTION:DISPLAYEND:VALARM", "END:VALARMEND:VEVENT", "DESCRIPTION:DESCRIPTION:"):
            if bad in raw:
                errors.append(f"{filename}：发现坏格式 {bad}")

        events = parse_events(raw)
        stats[filename] = len(events)
        uids = [event.uid for event in events if event.uid]
        if len(uids) != len(set(uids)):
            errors.append(f"{filename}：存在重复 UID")
        for event in events:
            start = parse_ics_datetime(event.dtstart) if event.dtstart else None
            end = parse_ics_datetime(event.dtend) if event.dtend else None
            if start and end and end < start:
                errors.append(f"{filename}：事件“{event.summary or event.uid}”结束时间早于开始时间")

        if filename == "flight.ics":
            mixed = [e.summary for e in events if is_positioning_summary(e.summary)]
            if mixed:
                errors.append(f"flight.ics 混入置位事件：{mixed[:5]}")
        elif filename == "positioning.ics":
            suspicious = [
                e.summary
                for e in events
                if e.summary and not is_positioning_summary(e.summary)
            ]
            if suspicious:
                errors.append(f"positioning.ics 包含疑似非置位事件：{suspicious[:5]}")

    backup = repo / "backup_flight.ics"
    current = repo / "flight.ics"
    if backup.exists() and current.exists():
        old_count = len(parse_events(backup.read_text(encoding="utf-8", errors="replace")))
        new_count = len(parse_events(current.read_text(encoding="utf-8", errors="replace")))
        if old_count >= 10 and new_count < int(old_count * 0.75):
            errors.append(f"flight.ics 历史事件疑似大量丢失：当前 {new_count}，备份 {old_count}")
    return errors, notes, stats


def write_outputs(output: Path, result: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "Crew Calendar 免费自动检查报告",
        f"状态：{result['status']}",
        f"版本：{result['version']}",
        f"检查时间：{result['checked_at_beijing']}",
    ]
    if result.get("upstream_conclusion"):
        lines.append(f"上游日历工作流状态：{result['upstream_conclusion']}")
    lines.extend(["", "ICS事件数量："])
    if result["ics_stats"]:
        lines.extend(f"- {name}: {count}" for name, count in result["ics_stats"].items())
    else:
        lines.append("- 未发现可检查的ICS文件")

    if result["issues"]:
        lines.extend(["", "发现的问题："])
        lines.extend(f"- {item}" for item in result["issues"])
        lines.extend(
            [
                "",
                "处理方式：下载本次Artifact中的report.json和report.txt，再交给ChatGPT分析。",
                "检测器不会自动修改主程序、清洗脚本、workflow或ICS。",
            ]
        )
    else:
        lines.extend(["", "检查通过：未发现明显的语法、ICS结构、置位混入或历史大量丢失问题。"])

    if result["notes"]:
        lines.extend(["", "补充说明："])
        lines.extend(f"- {item}" for item in result["notes"])

    report = "\n".join(lines).strip() + "\n"
    (output / "report.txt").write_text(report, encoding="utf-8")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Crew Calendar 免费自动检查\n\n```text\n" + report + "```\n")
    print(report)


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    output = (repo / args.output_dir).resolve()

    python_errors, python_notes = check_python(repo)
    ics_errors, ics_notes, stats = check_ics(repo)

    issues = [*python_errors, *ics_errors]
    notes = [*python_notes, *ics_notes]
    if args.upstream_conclusion and args.upstream_conclusion != "success":
        issues.insert(0, f"上游 Update Crew Calendar 工作流状态为 {args.upstream_conclusion}")

    result: dict[str, Any] = {
        "status": "PASS" if not issues else "ATTENTION",
        "version": VERSION,
        "checked_at_beijing": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "upstream_conclusion": args.upstream_conclusion,
        "issues": issues,
        "notes": notes,
        "ics_stats": stats,
        "safe_mode": "只检测和生成报告，不自动修改任何正式文件",
    }
    write_outputs(output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
