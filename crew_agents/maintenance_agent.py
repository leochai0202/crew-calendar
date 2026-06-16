from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.common import append_github_summary, atomic_write_json, atomic_write_text, now_beijing
from crew_agents.validate_repo import run_validation

VERSION = "maintenance-detector-free-v1-20260616"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Free deterministic repository detector; never modifies production files.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--debug-dir", default="debug_output")
    parser.add_argument("--output-dir", default="agent_output/maintenance")
    return parser.parse_args()


def read_tail(path: Path, max_chars: int = 12000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]


def detect_log_issues(repo: Path, debug: Path) -> list[str]:
    issues: list[str] = []
    paths = [
        repo / "agent_run" / "scraper.log",
        repo / "agent_run" / "cleaner.log",
        debug / "execution.log",
        debug / "clean_ics_people.log",
        debug / "classification_log.txt",
    ]
    fatal_patterns = [
        (r"Traceback \(most recent call last\)", "发现Python异常堆栈"),
        (r"NameError:", "发现NameError"),
        (r"SyntaxError:", "发现SyntaxError"),
        (r"Process completed with exit code [1-9]", "工作流步骤非零退出"),
        (r"登录失败|login failed", "登录失败"),
        (r"No such file|FileNotFoundError", "缺少文件"),
    ]
    combined = "\n".join(read_tail(p) for p in paths)
    for pattern, label in fatal_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            issues.append(label)
    return issues


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    debug = (repo / args.debug_dir).resolve()
    output = (repo / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    validation = run_validation(repo, repo)
    log_issues = detect_log_issues(repo, debug)
    all_errors = [*validation.get("errors", []), *log_issues]
    status = "PASS" if not all_errors else "ATTENTION"

    result = {
        "status": status,
        "version": VERSION,
        "checked_at_beijing": now_beijing().isoformat(),
        "validation": validation,
        "log_issues": log_issues,
        "note": "免费检测器只生成报告，不会自动修改或覆盖主程序、清洗脚本、workflow和ICS。",
    }
    atomic_write_json(output / "report.json", result)

    lines = [
        f"Crew Calendar 免费维护检测报告",
        f"状态：{status}",
        f"版本：{VERSION}",
        f"检查时间：{result['checked_at_beijing']}",
        "",
        "ICS事件数量：",
    ]
    for name, count in (validation.get("ics_stats") or {}).items():
        lines.append(f"- {name}: {count}")
    lines.append("")
    if all_errors:
        lines.append("发现的问题：")
        lines.extend(f"- {item}" for item in all_errors)
        lines.append("")
        lines.append("处理方式：下载本次Artifact中的debug_output和report.json，再发给ChatGPT处理；正式文件未修改。")
    else:
        lines.append("检查通过：未发现语法、明显源码安全、ICS结构、置位混入或历史大量丢失问题。")
    report_text = "\n".join(lines).strip() + "\n"
    atomic_write_text(output / "report.txt", report_text)
    append_github_summary("## Crew Calendar 免费维护检测\n\n```text\n" + report_text + "```")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
