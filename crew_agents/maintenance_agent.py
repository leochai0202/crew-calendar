from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import Agent, Runner, function_tool  # type: ignore
from crew_agents.common import append_github_summary, atomic_write_json, atomic_write_text, now_beijing, run_command, safe_resolve
from crew_agents.validate_repo import run_validation

TARGET_FILES = ["crew_calendar_main.py", "clean_ics_people.py"]


@dataclass
class WorkspaceState:
    repo: Path
    candidate: Path
    debug: Path
    output: Path
    last_check: dict | None = None


STATE: WorkspaceState | None = None


class MaintenanceResult(BaseModel):
    status: Literal["SUCCESS", "NO_CHANGE", "FAILED_SAFE"]
    diagnosis: str
    changed_files: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    user_instruction: str = ""


def _state() -> WorkspaceState:
    if STATE is None:
        raise RuntimeError("Workspace state not initialized")
    return STATE


def _scope_root(scope: str) -> Path:
    state = _state()
    roots = {
        "repo": state.repo,
        "candidate": state.candidate,
        "debug": state.debug,
        "output": state.output,
    }
    if scope not in roots:
        raise ValueError("scope must be repo, candidate, debug, or output")
    return roots[scope]


@function_tool
def list_files(scope: str = "debug", max_files: int = 200) -> str:
    """List files in one workspace scope. Use debug for logs/artifacts, repo for current files, candidate for editable copies."""
    root = _scope_root(scope)
    if not root.exists():
        return f"{scope}: directory does not exist"
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(f"{path.relative_to(root)} ({path.stat().st_size} bytes)")
            if len(files) >= max_files:
                files.append("... truncated ...")
                break
    return "\n".join(files) or "(no files)"


@function_tool
def read_text(scope: str, path: str, start_line: int = 1, end_line: int = 250) -> str:
    """Read a bounded line range from a UTF-8 text file. Never request more than about 400 lines at once."""
    root = _scope_root(scope)
    p = safe_resolve(root, path)
    if not p.exists() or not p.is_file():
        return f"File not found: {scope}/{path}"
    if p.stat().st_size > 15_000_000:
        return "File too large; use search_text first"
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = max(1, start_line)
    end = min(len(lines), max(start, end_line))
    selected = [f"{idx:05d}: {lines[idx - 1]}" for idx in range(start, end + 1)]
    return f"{scope}/{path} lines {start}-{end} of {len(lines)}\n" + "\n".join(selected)


@function_tool
def search_text(scope: str, path: str, pattern: str, max_results: int = 30, context_lines: int = 3) -> str:
    """Search a text file with a regular expression and return matching line numbers plus nearby context."""
    root = _scope_root(scope)
    p = safe_resolve(root, path)
    if not p.exists() or not p.is_file():
        return f"File not found: {scope}/{path}"
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"Invalid regex: {exc}"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    matches: list[str] = []
    used_ranges: set[tuple[int, int]] = set()
    for idx, line in enumerate(lines, start=1):
        if not regex.search(line):
            continue
        begin = max(1, idx - context_lines)
        end = min(len(lines), idx + context_lines)
        key = (begin, end)
        if key in used_ranges:
            continue
        used_ranges.add(key)
        block = "\n".join(f"{j:05d}: {lines[j - 1]}" for j in range(begin, end + 1))
        matches.append(block)
        if len(matches) >= max_results:
            break
    return "\n\n---\n\n".join(matches) if matches else "No matches"


@function_tool
def apply_patch(patch: str) -> str:
    """Apply a unified diff to candidate files only. Patch paths must be crew_calendar_main.py or clean_ics_people.py."""
    state = _state()
    forbidden = [".github/", "schedule.yml", "flight.ics", "crew_schedule.ics", "../"]
    if any(token in patch for token in forbidden):
        return "REJECTED: patch touches forbidden paths"
    if not any(name in patch for name in TARGET_FILES):
        return "REJECTED: patch does not target an allowed file"
    code, output = run_command(
        ["git", "apply", "--whitespace=fix", "-"],
        cwd=state.candidate,
        timeout=120,
        input_text=patch,
    )
    return ("APPLIED\n" if code == 0 else "FAILED\n") + output[-8000:]


@function_tool
def run_checks() -> str:
    """Run syntax, source-safety, ICS-format, classification and history-preservation checks. Must pass before declaring success."""
    state = _state()
    result = run_validation(state.candidate, state.repo)
    state.last_check = result
    return json.dumps(result, ensure_ascii=False, indent=2)


@function_tool
def show_diff(max_chars: int = 30000) -> str:
    """Show unified diffs between current official files and candidate files."""
    state = _state()
    chunks: list[str] = []
    for name in TARGET_FILES:
        original = (state.repo / name).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        candidate = (state.candidate / name).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(original, candidate, fromfile=f"a/{name}", tofile=f"b/{name}")
        )
        if diff:
            chunks.append(diff)
    output = "\n".join(chunks) or "NO DIFF"
    return output[:max_chars]


SYSTEM_INSTRUCTIONS = r"""
你是 crew-calendar 项目的安全维护 Agent。你的任务是根据当前源码、运行日志、debug_output 和最终 ICS 定位问题，并在候选副本中生成高置信度修复。

硬性规则：
1. 只能修改 candidate 范围内的 crew_calendar_main.py 和 clean_ics_people.py；不得修改正式仓库、workflow、ICS或凭证。
2. 先查看运行日志、execution.log、classification_log、items_summary、cards/block文本以及最终ICS，不能凭猜测修改。
3. 修复必须是通用逻辑，不得仅按某个航班号写死。重点保护：多航段顺序、每段签到/人员/注册号绑定、航班/置位/训练分类、历史保留、Apple ICS格式。
4. 修改尽量小，保留已有稳定功能；不要重写整个5000行主程序。
5. 必须使用apply_patch修改候选文件；修改后必须调用run_checks。
6. 只有run_checks返回PASS且show_diff非空，才能返回SUCCESS。
7. 若证据不足、API中断、补丁失败或检查失败，返回FAILED_SAFE；正式文件绝不改变。
8. 若当前代码与输出均正常，返回NO_CHANGE。
9. 用户最终需要完整候选文件，不需要只给补丁；系统会在全部检查通过后自动打包候选文件。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transactional crew-calendar maintenance agent")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--debug-dir", default="debug_output")
    parser.add_argument("--output-dir", default="agent_output/maintenance")
    parser.add_argument("--model", default=os.getenv("MAINTENANCE_MODEL", "gpt-5.1"))
    parser.add_argument("--max-turns", type=int, default=18)
    return parser.parse_args()


def initial_diagnostics(repo: Path, candidate: Path, debug: Path) -> dict:
    validation = run_validation(candidate, repo)
    logs: dict[str, str] = {}
    for relative in [
        "agent_run/scraper.log",
        "debug_output/execution.log",
        "debug_output/clean_ics_people.log",
        "debug_output/classification_log.txt",
        "debug_output/items_summary.txt",
    ]:
        path = repo / relative
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            logs[relative] = text[-12000:]
    if debug.exists():
        for name in ("execution.log", "clean_ics_people.log", "classification_log.txt", "items_summary.txt"):
            path = debug / name
            if path.exists() and str(path.relative_to(repo)) not in logs:
                logs[str(path.relative_to(repo))] = path.read_text(encoding="utf-8", errors="replace")[-12000:]
    return {"validation": validation, "logs": logs}


def copy_candidates(repo: Path, candidate: Path) -> None:
    candidate.mkdir(parents=True, exist_ok=True)
    for name in TARGET_FILES:
        source = repo / name
        if not source.exists():
            raise FileNotFoundError(f"正式文件不存在: {name}")
        shutil.copy2(source, candidate / name)


def collect_diff(repo: Path, candidate: Path) -> tuple[str, list[str]]:
    chunks: list[str] = []
    changed: list[str] = []
    for name in TARGET_FILES:
        old = (repo / name).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        new = (candidate / name).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old, new, fromfile=f"a/{name}", tofile=f"b/{name}"))
        if diff:
            changed.append(name)
            chunks.append(diff)
    return "\n".join(chunks), changed


def main() -> int:
    global STATE
    args = parse_args()
    repo = Path(args.repo).resolve()
    debug = (repo / args.debug_dir).resolve()
    output = (repo / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidate = output / "candidate_workspace"
    if candidate.exists():
        shutil.rmtree(candidate)

    try:
        copy_candidates(repo, candidate)
        STATE = WorkspaceState(repo=repo, candidate=candidate, debug=debug, output=output)
        diagnostics = initial_diagnostics(repo, candidate, debug)
        atomic_write_json(output / "initial_diagnostics.json", diagnostics)

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY 未设置")

        prompt = {
            "request": "检查当前crew-calendar运行是否存在失败、错分、漏段、串段、历史丢失或ICS格式问题；有充分证据时修复候选文件。",
            "initial_diagnostics": diagnostics,
            "available_tools": [
                "list_files",
                "read_text",
                "search_text",
                "apply_patch",
                "run_checks",
                "show_diff",
            ],
            "important_files": TARGET_FILES,
        }

        agent = Agent(
            name="Crew Calendar安全维护Agent",
            instructions=SYSTEM_INSTRUCTIONS,
            model=args.model,
            tools=[list_files, read_text, search_text, apply_patch, run_checks, show_diff],
            output_type=MaintenanceResult,
        )
        run = Runner.run_sync(agent, json.dumps(prompt, ensure_ascii=False, indent=2), max_turns=args.max_turns)
        result = run.final_output
        if not isinstance(result, MaintenanceResult):
            result = MaintenanceResult.model_validate(result)

        final_check = run_validation(candidate, repo)
        diff_text, changed_files = collect_diff(repo, candidate)
        atomic_write_text(output / "candidate.diff", diff_text or "NO DIFF\n")
        atomic_write_json(output / "final_validation.json", final_check)

        if result.status == "SUCCESS" and final_check["status"] == "PASS" and changed_files:
            stamp = now_beijing().strftime("%Y%m%d_%H%M%S")
            delivery = output / "candidates"
            delivery.mkdir(parents=True, exist_ok=True)
            delivered: list[str] = []
            for name in changed_files:
                stem = Path(name).stem
                dest_name = f"{stem}_agent_fix_{stamp}.py"
                shutil.copy2(candidate / name, delivery / dest_name)
                delivered.append(dest_name)
            final = {
                "status": "SUCCESS",
                "diagnosis": result.diagnosis,
                "changed_files": changed_files,
                "delivered_files": delivered,
                "checks": result.checks,
                "remaining_risks": result.remaining_risks,
                "user_instruction": "下载候选文件，人工改回正式文件名后覆盖；正式仓库未被Agent自动修改。",
                "validation": final_check,
            }
            atomic_write_json(output / "result.json", final)
            append_github_summary(
                "## Crew Calendar维护Agent\n\n**SUCCESS**：候选修复已生成，正式文件未自动覆盖。\n\n"
                + f"**诊断：** {result.diagnosis}\n\n"
                + "**候选文件：**\n"
                + "\n".join(f"- `{name}`" for name in delivered)
            )
            print(json.dumps(final, ensure_ascii=False, indent=2))
            return 0

        status = "NO_CHANGE" if result.status == "NO_CHANGE" and not changed_files and final_check["status"] == "PASS" else "FAILED_SAFE"
        final = {
            "status": status,
            "diagnosis": result.diagnosis,
            "changed_files": changed_files,
            "checks": result.checks,
            "remaining_risks": result.remaining_risks,
            "validation": final_check,
            "note": "没有可交付候选文件；正式文件未改变。",
        }
        atomic_write_json(output / "result.json", final)
        append_github_summary(
            f"## Crew Calendar维护Agent\n\n**{status}**：正式文件未改变。\n\n{result.diagnosis}"
        )
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return 0 if status == "NO_CHANGE" else 2

    except Exception as exc:
        failed = {
            "status": "FAILED_SAFE",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=15),
            "note": "API、工具或检查中断；正式文件完全未修改。",
        }
        atomic_write_json(output / "result.json", failed)
        append_github_summary(
            f"## Crew Calendar维护Agent\n\n**FAILED_SAFE**：{type(exc).__name__}: {exc}\n\n正式文件未修改。"
        )
        print(json.dumps(failed, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
