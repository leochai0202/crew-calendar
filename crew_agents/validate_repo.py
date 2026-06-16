from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.common import run_command
from crew_agents.ics_utils import parse_ics

REQUIRED_PY = ["crew_calendar_main.py", "clean_ics_people.py"]
ICS_FILES = [
    "crew_schedule.ics",
    "flight.ics",
    "positioning.ics",
    "training.ics",
    "ferry.ics",
    "other.ics",
]


def check_python(candidate_dir: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_PY:
        path = candidate_dir / name
        if not path.exists():
            errors.append(f"缺少候选文件: {name}")
            continue
        code, out = run_command([sys.executable, "-m", "py_compile", str(path)], timeout=120)
        if code != 0:
            errors.append(f"{name} 语法检查失败:\n{out[-4000:]}")
    return errors


def check_source_safety(candidate_dir: Path) -> list[str]:
    errors: list[str] = []
    main_path = candidate_dir / "crew_calendar_main.py"
    clean_path = candidate_dir / "clean_ics_people.py"
    if main_path.exists():
        text = main_path.read_text(encoding="utf-8", errors="replace")
        if "segment_people_lists[i]" in text and not re.search(r"for\s+i\s*,", text):
            errors.append("主程序疑似存在未定义索引 i 的 segment_people_lists[i]")
        if "CREW_USERNAME" not in text or "CREW_PASSWORD" not in text:
            errors.append("主程序缺少凭证环境变量读取逻辑")
        if len(text.splitlines()) < 1000:
            errors.append("主程序行数异常偏少，疑似被截断")
    if clean_path.exists():
        text = clean_path.read_text(encoding="utf-8", errors="replace")
        if "VERSION" not in text:
            errors.append("清洗脚本缺少版本标识")
        if len(text.splitlines()) < 100:
            errors.append("清洗脚本行数异常偏少，疑似被截断")
    return errors


def check_ics(repo: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats: dict[str, int] = {}
    for name in ICS_FILES:
        path = repo / name
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if raw.count("BEGIN:VEVENT") != raw.count("END:VEVENT"):
            errors.append(f"{name}: VEVENT 数量不平衡")
        if raw.count("BEGIN:VALARM") != raw.count("END:VALARM"):
            errors.append(f"{name}: VALARM 数量不平衡")
        bad_patterns = [
            "ACTION:DISPLAYEND:VALARM",
            "END:VALARMEND:VEVENT",
            "DESCRIPTION:DESCRIPTION:",
        ]
        for pattern in bad_patterns:
            if pattern in raw:
                errors.append(f"{name}: 包含坏格式 {pattern}")
        events = parse_ics(path)
        stats[name] = len(events)
        uids = [e.uid for e in events if e.uid]
        if len(uids) != len(set(uids)):
            errors.append(f"{name}: 存在重复 UID")
        for event in events:
            if event.end < event.start:
                errors.append(f"{name}: {event.summary} 结束时间早于开始时间")
        if name == "flight.ics":
            bad = [e.summary for e in events if e.is_positioning]
            if bad:
                errors.append(f"flight.ics 混入置位事件: {bad[:5]}")
        if name == "positioning.ics":
            non_positioning = [e.summary for e in events if not e.is_positioning]
            if non_positioning:
                errors.append(f"positioning.ics 包含非置位事件: {non_positioning[:5]}")

    backup = repo / "backup_flight.ics"
    flight = repo / "flight.ics"
    if backup.exists() and flight.exists():
        old_count = len(parse_ics(backup))
        new_count = len(parse_ics(flight))
        if old_count >= 10 and new_count < int(old_count * 0.75):
            errors.append(f"flight.ics 历史事件疑似大量丢失: 当前{new_count}, 备份{old_count}")
    return errors, stats


def run_validation(candidate_dir: Path, repo: Path) -> dict:
    errors = []
    errors.extend(check_python(candidate_dir))
    errors.extend(check_source_safety(candidate_dir))
    ics_errors, stats = check_ics(repo)
    errors.extend(ics_errors)
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "ics_stats": stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    result = run_validation(Path(args.candidate_dir).resolve(), Path(args.repo).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
