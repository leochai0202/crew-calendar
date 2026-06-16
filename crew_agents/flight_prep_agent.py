from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import Agent, Runner  # type: ignore  # OpenAI Agents SDK package
from crew_agents.common import (
    BEIJING_TZ,
    append_github_summary,
    atomic_write_json,
    atomic_write_text,
    load_json,
    now_beijing,
)
from crew_agents.ics_utils import (
    CalendarEvent,
    events_for_date,
    extract_airport_mapping,
    parse_ics,
    resolve_icao,
    update_airport_experience,
)
from crew_agents.knowledge import collect_airport_knowledge
from crew_agents.weather import fetch_airport_weather


class FlightPrepResult(BaseModel):
    status: Literal["SUCCESS", "NO_TASK", "FAILED_SAFE"]
    target_date: str
    title: str
    content: str
    warnings: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    source_summary: list[str] = Field(default_factory=list)


SYSTEM_INSTRUCTIONS = r"""
你是A320副驾驶航前准备/运行风险简报 Agent。请根据用户提供的结构化资料，生成可直接发送到机组群的中文准备文字。

必须遵守：
1. 只使用输入资料，不得编造机场特点、天气、NOTAM、人员身份或个人经历。
2. 不确定或TAF未覆盖航班时段时，明确写“以航前最新TAF/METAR及放行资料为准”。
3. 总经历、本阶段经历、起落、近90天/近一月、最近操纵落地和PF/PM评价均按输入原样使用，不自行推断或更新。
4. 使用“我们”描述团队运行要求；不要写酒店、接送、无关频率或行政信息。
5. 内容结构：
   - 个人信息与值勤情况
   - 近3个月涉及机场运行情况
   - 最近PF/PM讲评
   - 航班与天气
   - 各机场典型不安全事件/风险识别
   - 核心威胁与控制措施
   - 必要的补充运行提醒
6. 每个涉及机场选择2-5条最相关风险；不要机械堆砌手册。
7. 往返可合并，不连续、跨夜或性质不同的航段应分开写。
8. 夏季优先雷雨、强对流、低云低能见、湿跑道、风切变、鸟击、绕飞和能量管理；冬季才重点写积冰、除防冰和低温修正。
9. 所有航班号都必须在正文中出现；不得漏段。
10. 输出为纯文本，不使用Markdown代码围栏。若greeting为空，不添加额外问候。
11. status通常为SUCCESS。若关键排班信息不完整到无法生成，则返回FAILED_SAFE，并在missing_items说明原因，不要输出伪造正文。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate flight preparation text from ICS schedule.")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--target-date", default="", help="YYYY-MM-DD; overrides days-ahead")
    parser.add_argument("--days-ahead", type=int, default=1)
    parser.add_argument("--model", default=os.getenv("FLIGHT_PREP_MODEL", "gpt-5-mini"))
    return parser.parse_args()


def determine_target_date(target_date: str, days_ahead: int) -> date:
    if target_date:
        return date.fromisoformat(target_date)
    return (now_beijing() + timedelta(days=days_ahead)).date()


def _event_payload(event: CalendarEvent) -> dict:
    data = event.to_dict()
    # Crew names are not needed in the preparation text unless user later enables it.
    return data


def validate_generated(result: FlightPrepResult, flights: list[CalendarEvent], profile: dict) -> list[str]:
    errors: list[str] = []
    content = result.content or ""
    for event in flights:
        if event.flight_number and event.flight_number not in content:
            errors.append(f"正文漏掉航班号 {event.flight_number}")
    if profile.get("name") and profile["name"] not in content:
        errors.append("正文缺少姓名")
    if "【" in content or "】" in content or "TODO" in content:
        errors.append("正文包含未填写占位符")
    if len(content.strip()) < 300:
        errors.append("正文过短，可能生成不完整")
    if result.status != "SUCCESS":
        errors.append(f"Agent返回状态 {result.status}")
    return errors


def build_experience_summary(experience: dict, airports: list[str], target: date) -> list[dict]:
    result: list[dict] = []
    airport_map = experience.get("airports") or {}
    cutoff = target - timedelta(days=int(experience.get("rolling_days", 90)))
    for airport in airports:
        record = airport_map.get(airport)
        if not record:
            # fuzzy match
            for known, value in airport_map.items():
                if known in airport or airport in known:
                    record = value
                    break
        last_operated = record.get("last_operated") if isinstance(record, dict) else None
        within = False
        if last_operated:
            try:
                within = date.fromisoformat(last_operated) >= cutoff
            except Exception:
                within = False
        result.append(
            {
                "airport": airport,
                "operated_within_90_days": within,
                "last_operated": last_operated or "",
            }
        )
    return result


def write_status(repo: Path, data: dict) -> None:
    out_dir = repo / "agent_output" / "flight_prep"
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "status.json", data)


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    target = determine_target_date(args.target_date, args.days_ahead)
    output_dir = repo / "flight_preparation"
    output_dir.mkdir(parents=True, exist_ok=True)
    success_marker = output_dir / ".success"
    if success_marker.exists():
        success_marker.unlink()

    try:
        settings = load_json(repo / "config" / "prep_settings.json", {}) or {}
        profile = load_json(repo / "config" / "pilot_profile.json", {}) or {}
        experience = load_json(repo / "config" / "airport_experience.json", {}) or {}
        operational_focus = load_json(repo / "config" / "operational_focus.json", {}) or {}

        all_events = parse_ics(repo / "flight.ics")
        flights = [e for e in events_for_date(all_events, target) if e.is_flight and not e.is_positioning]
        if not flights:
            status = {
                "status": "NO_TASK",
                "target_date": target.isoformat(),
                "message": "目标日期未发现航班任务；未覆盖已有航前准备文件。",
            }
            write_status(repo, status)
            append_github_summary(
                f"## 航前准备 Agent\n\n**NO_TASK**：{target.isoformat()} 未发现航班任务，未覆盖已有文件。"
            )
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0

        if settings.get("auto_update_airport_experience", True):
            updated, changes = update_airport_experience(
                all_events,
                experience,
                as_of=now_beijing(),
                rolling_days=int(settings.get("airport_experience_rolling_days", 90)),
            )
            experience = updated
            atomic_write_json(repo / "config" / "airport_experience.json", experience)
        else:
            changes = []

        routes = [e.route for e in flights]
        airports = list(dict.fromkeys([a for route in routes for a in route if a]))
        mapping = extract_airport_mapping(repo / "crew_calendar_main.py")
        airport_icaos = {airport: resolve_icao(airport, mapping) for airport in airports}

        weather: dict[str, dict] = {}
        if settings.get("include_weather_section", True):
            for airport in airports:
                weather[airport] = fetch_airport_weather(
                    airport_icaos.get(airport, ""),
                    timeout=int(settings.get("weather_timeout_seconds", 20)),
                ).to_dict()

        knowledge = collect_airport_knowledge(
            repo / "knowledge",
            repo / "config" / "airport_supplements.json",
            airports,
            airport_icaos.values(),
        )
        max_manual_chars = int(settings.get("max_airport_manual_chars", 24000))
        knowledge["manual_chunks"] = knowledge.get("manual_chunks", "")[:max_manual_chars]

        rules_path = repo / "knowledge" / "prep_rules.txt"
        rules = rules_path.read_text(encoding="utf-8", errors="replace") if rules_path.exists() else ""

        payload = {
            "target_date": target.isoformat(),
            "generated_at_beijing": now_beijing().isoformat(),
            "greeting": settings.get("greeting", ""),
            "profile": profile,
            "flights": [_event_payload(e) for e in flights],
            "airport_experience": build_experience_summary(experience, airports, target),
            "airport_icao": airport_icaos,
            "weather": weather,
            "airport_knowledge": knowledge,
            "operational_focus": operational_focus,
            "rules": rules,
            "experience_auto_update_log": changes,
            "manual_profile_warning": "经历时间、起落数、最近操纵落地和PF/PM评价只使用pilot_profile.json中的手动值。",
        }
        payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
        max_input_chars = int(settings.get("max_agent_input_chars", 90000))
        if len(payload_text) > max_input_chars:
            # First trim the long manual chunk; keep schedule/profile/weather intact.
            excess = len(payload_text) - max_input_chars
            manual = payload["airport_knowledge"].get("manual_chunks", "")
            payload["airport_knowledge"]["manual_chunks"] = manual[: max(0, len(manual) - excess - 1000)]
            payload_text = json.dumps(payload, ensure_ascii=False, indent=2)

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY 未设置")

        agent = Agent(
            name="A320航前准备Agent",
            instructions=SYSTEM_INSTRUCTIONS,
            model=args.model,
            output_type=FlightPrepResult,
        )
        run = Runner.run_sync(
            agent,
            "请根据以下资料生成航前准备：\n" + payload_text,
            max_turns=4,
        )
        result = run.final_output
        if not isinstance(result, FlightPrepResult):
            result = FlightPrepResult.model_validate(result)

        errors = validate_generated(result, flights, profile)
        if errors:
            failed = {
                "status": "FAILED_SAFE",
                "target_date": target.isoformat(),
                "message": "生成结果未通过本地校验，未覆盖正式文件。",
                "errors": errors,
                "agent_warnings": result.warnings,
                "agent_missing_items": result.missing_items,
            }
            write_status(repo, failed)
            append_github_summary(
                "## 航前准备 Agent\n\n**FAILED_SAFE**：生成结果未通过校验，正式文件未改变。\n\n"
                + "\n".join(f"- {e}" for e in errors)
            )
            print(json.dumps(failed, ensure_ascii=False, indent=2))
            return 2

        content = result.content.strip() + "\n"
        dated_name = f"{target.isoformat()}_航前准备.txt"
        atomic_write_text(output_dir / dated_name, content)
        atomic_write_text(output_dir / "latest.txt", content)
        atomic_write_json(
            output_dir / "latest_meta.json",
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "generated_at_beijing": now_beijing().isoformat(),
                "model": args.model,
                "flight_numbers": [e.flight_number for e in flights],
                "airports": airports,
                "warnings": result.warnings,
                "missing_items": result.missing_items,
                "airport_information_file": knowledge.get("source_file", ""),
            },
        )
        atomic_write_text(success_marker, "SUCCESS\n")
        write_status(
            repo,
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "output": str(output_dir / dated_name),
            },
        )
        summary = f"## {result.title or target.isoformat() + ' 航前准备'}\n\n```text\n{content}```"
        if result.warnings:
            summary += "\n\n### 提醒\n" + "\n".join(f"- {w}" for w in result.warnings)
        append_github_summary(summary)
        print(f"SUCCESS: {output_dir / dated_name}")
        return 0

    except Exception as exc:
        failed = {
            "status": "FAILED_SAFE",
            "target_date": target.isoformat(),
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=12),
            "note": "正式航前准备文件未覆盖。",
        }
        write_status(repo, failed)
        append_github_summary(
            f"## 航前准备 Agent\n\n**FAILED_SAFE**：{type(exc).__name__}: {exc}\n\n正式文件未覆盖。"
        )
        print(json.dumps(failed, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
