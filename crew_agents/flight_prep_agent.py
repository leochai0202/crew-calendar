from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.common import (
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
from crew_agents.knowledge import find_airport_information_file
from crew_agents.weather import fetch_airport_weather

VERSION = "flight-prep-free-v1-20260616"
RISK_KEYWORDS = (
    "跑道", "滑行", "进近", "离场", "复飞", "盲降", "双截获", "高截获", "风切变",
    "乱流", "雷雨", "鸟击", "GPS", "地形", "气压", "灯光", "军航", "高度", "速度",
    "PAPI", "ILS", "下滑", "能量", "脱离", "机坪", "等待线", "强回波", "湿跑道",
)
EXCLUDE_KEYWORDS = ("酒店", "住宿", "接送", "餐食", "电话", "地址", "联系人")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate rule-based flight preparation text without API.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--days-ahead", type=int, default=1)
    return parser.parse_args()


def determine_target_date(target_date: str, days_ahead: int) -> date:
    if target_date:
        return date.fromisoformat(target_date)
    return (now_beijing() + timedelta(days=days_ahead)).date()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = normalize_text(item)
        key = re.sub(r"[\s，。；、:：()（）]", "", item)
        if item and key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def format_date_cn(value: str) -> str:
    try:
        d = date.fromisoformat(value)
        return f"{d.month}月{d.day}日"
    except Exception:
        return value


def profile_intro(profile: dict, aircraft_types: list[str]) -> str:
    name = profile.get("name", "")
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    level = profile.get("technical_level", "")
    promotion = profile.get("promotion_date", "")
    parts = [f"我是{unit}{role}{name}" if name else f"{unit}{role}".strip()]
    if level:
        parts.append(f"目前技术级别为{level}")
    if promotion:
        parts.append(f"晋级日期{promotion}")

    if profile.get("stage_hours") is not None:
        parts.append(f"本阶段经历时间{profile['stage_hours']}小时")
    if profile.get("stage_landings") is not None:
        parts.append(f"起落{profile['stage_landings']}个")
    sim_suffix = "（含模拟机）" if profile.get("simulation_included") else ""
    if profile.get("landings_90_days") is not None:
        parts.append(f"近90天起落数{profile['landings_90_days']}个{sim_suffix}")
    if profile.get("landings_30_days") is not None:
        parts.append(f"近一个月起落{profile['landings_30_days']}个{sim_suffix}")
    if profile.get("duty_day"):
        parts.append(f"明日为本人本次值勤期第{profile['duty_day']}天")
    if aircraft_types:
        parts.append(f"本次执飞机型{'/'.join(aircraft_types)}")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        text = f"上次操纵落地机场为{last['airport']}"
        if last.get("date"):
            text += format_date_cn(last["date"])
        parts.append(text)
    return "，".join(p for p in parts if p) + "。"


def experience_records(experience: dict, airports: list[str], target: date) -> list[dict]:
    records: list[dict] = []
    airport_map = experience.get("airports") or {}
    rolling_days = int(experience.get("rolling_days") or 90)
    cutoff = target - timedelta(days=rolling_days)
    for airport in airports:
        record = airport_map.get(airport)
        if not record:
            for known, value in airport_map.items():
                if known in airport or airport in known:
                    record = value
                    break
        last = record.get("last_operated", "") if isinstance(record, dict) else ""
        within = False
        if last:
            try:
                within = date.fromisoformat(last) >= cutoff
            except Exception:
                within = False
        records.append({"airport": airport, "last": last, "within": within})
    return records


def experience_text(records: list[dict]) -> str:
    operated = []
    not_operated = []
    for rec in records:
        if rec["within"]:
            suffix = f"（最近{format_date_cn(rec['last'])}）" if rec["last"] else ""
            operated.append(f"{rec['airport']}{suffix}")
        else:
            not_operated.append(rec["airport"])
    lines = []
    if operated:
        lines.append("近3个月内已运行过本次航线涉及的：" + "、".join(operated) + "。")
    if not_operated:
        lines.append("近3个月内未记录运行过本次航线涉及的：" + "、".join(not_operated) + "。")
    return "\n".join(lines)


def feedback_text(profile: dict) -> str:
    feedback = profile.get("recent_feedback") or {}
    parts = []
    if feedback.get("PF"):
        parts.append(f"作为PF最近一次评价：{feedback['PF']}")
    if feedback.get("PM"):
        parts.append(f"作为PM最近一次评价：{feedback['PM']}")
    if feedback.get("RNP"):
        parts.append(f"补充讲评：{feedback['RNP']}")
    if not parts:
        return ""
    return "上一次飞行中教员/机长对我优缺点的评价（PF/PM各取最近一次）：" + "；".join(parts) + "。"


def flight_lines(flights: list[CalendarEvent]) -> list[str]:
    lines = []
    for idx, event in enumerate(flights, start=1):
        dep, arr = event.route
        time_text = f"{event.start:%H:%M}-{event.end:%H:%M}"
        cross = "（跨日）" if event.end.date() > event.start.date() else ""
        extra = []
        if event.checkin:
            extra.append(f"签到{event.checkin}")
        if event.aircraft_type:
            extra.append(f"机型{event.aircraft_type}")
        if event.registration:
            extra.append(f"注册号{event.registration}")
        tail = "；" + "，".join(extra) if extra else ""
        lines.append(f"{idx}. {event.flight_number} {dep}→{arr}，{time_text}{cross}{tail}。")
    return lines


def compact_weather(value: str, max_len: int = 420) -> str:
    value = normalize_text(value)
    return value if len(value) <= max_len else value[:max_len].rstrip() + "……"


def weather_section(airports: list[str], icao_map: dict[str, str], timeout: int) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []
    for airport in airports:
        icao = icao_map.get(airport, "")
        result = fetch_airport_weather(icao, timeout=timeout)
        parts = []
        if result.metar:
            parts.append("METAR：" + compact_weather(result.metar))
        if result.taf:
            parts.append("TAF：" + compact_weather(result.taf))
        if parts:
            lines.append(f"{airport}（{icao or 'ICAO待确认'}）：" + "；".join(parts) + "。")
        else:
            lines.append(f"{airport}：暂未获取到有效METAR/TAF，以航前最新报文、放行资料及ATIS为准。")
        if result.error:
            warnings.append(f"{airport}天气获取提示：{result.error}")
    return lines, warnings


def read_manual_lines(knowledge_dir: Path, airport: str, aliases: list[str], max_lines: int = 5) -> list[str]:
    source = find_airport_information_file(knowledge_dir)
    if not source:
        return []
    text = source.read_text(encoding="utf-8", errors="replace")
    search_terms = unique([airport, *aliases])
    positions = [text.find(term) for term in search_terms if term and text.find(term) >= 0]
    if not positions:
        return []
    idx = min(positions)
    chunk = text[max(0, idx - 500): min(len(text), idx + 6500)]
    candidates: list[str] = []
    for raw in chunk.splitlines():
        line = normalize_text(re.sub(r"^[\s•·（(]?\d+[）).、:：\s-]*", "", raw))
        if not (12 <= len(line) <= 220):
            continue
        if any(word in line for word in EXCLUDE_KEYWORDS):
            continue
        if not any(word in line for word in RISK_KEYWORDS):
            continue
        candidates.append(line.rstrip("。") + "。")
    return unique(candidates)[:max_lines]


def supplements_for_airport(supplements: dict, airport: str) -> tuple[dict, str]:
    airport_data = supplements.get("airports", supplements)
    for name, value in airport_data.items():
        aliases = value.get("aliases", []) if isinstance(value, dict) else []
        if name == airport or name in airport or airport in name or any(a and (a in airport or airport in a) for a in aliases):
            return value if isinstance(value, dict) else {}, name
    return {}, ""


def airport_risks(repo: Path, airports: list[str], max_items: int) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    supplements = load_json(repo / "config" / "airport_supplements.json", {}) or {}
    risks: dict[str, list[str]] = {}
    threats: dict[str, list[str]] = {}
    warnings: list[str] = []
    for airport in airports:
        data, matched_name = supplements_for_airport(supplements, airport)
        aliases = list(data.get("aliases") or [])
        structured = list(data.get("typical_incidents") or [])
        manual = read_manual_lines(repo / "knowledge", airport, aliases, max_lines=max_items)
        merged = unique([*structured, *manual])[:max_items]
        if not merged:
            merged = ["当前知识库未找到该机场的结构化风险条目，需结合最新机场特点、航图、NOTAM和放行资料补充确认。"]
            warnings.append(f"{airport}缺少结构化机场风险资料")
        risks[airport] = merged
        threats[airport] = unique(list(data.get("core_threats") or []))[:max_items]
        if matched_name and matched_name != airport:
            warnings.append(f"{airport}使用知识库条目：{matched_name}")
    return risks, threats, warnings


def global_threats(operational_focus: dict, month: int) -> list[str]:
    items: list[str] = []
    if 4 <= month <= 10:
        items.extend((operational_focus.get("thunderstorm_avoidance") or [])[:4])
    items.extend((operational_focus.get("stabilized_approach") or [])[:3])
    items.extend((operational_focus.get("energy_and_configuration") or [])[:2])
    items.extend((operational_focus.get("ground_operations") or [])[:2])
    items.extend((operational_focus.get("crm_and_fatigue") or [])[:2])
    return unique(items)


def validate_content(content: str, flights: list[CalendarEvent], profile: dict) -> list[str]:
    errors = []
    for event in flights:
        if event.flight_number and event.flight_number not in content:
            errors.append(f"正文漏掉航班号{event.flight_number}")
    if profile.get("name") and profile["name"] not in content:
        errors.append("正文缺少姓名")
    if len(content.strip()) < 500:
        errors.append("正文过短，疑似生成不完整")
    return errors


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
            status = {"status": "NO_TASK", "target_date": target.isoformat(), "message": "目标日期未发现航班任务，未覆盖已有准备稿。", "version": VERSION}
            write_status(repo, status)
            append_github_summary(f"## 免费航前准备\n\n**NO_TASK**：{target.isoformat()} 未发现航班任务。")
            return 0

        changes: list[str] = []
        if settings.get("auto_update_airport_experience", True):
            experience, changes = update_airport_experience(
                all_events,
                experience,
                as_of=now_beijing(),
                rolling_days=int(settings.get("airport_experience_rolling_days", 90)),
            )
            atomic_write_json(repo / "config" / "airport_experience.json", experience)

        airports = unique([a for e in flights for a in e.route if a])
        mapping = extract_airport_mapping(repo / "crew_calendar_main.py")
        icao_map = {airport: resolve_icao(airport, mapping) for airport in airports}
        aircraft_types = unique([e.aircraft_type or settings.get("default_aircraft_type", "A320") for e in flights])

        weather_lines: list[str] = []
        warnings: list[str] = []
        if settings.get("include_weather_section", True):
            weather_lines, weather_warnings = weather_section(
                airports, icao_map, int(settings.get("weather_timeout_seconds", 20))
            )
            warnings.extend(weather_warnings)

        max_items = int((settings.get("typical_incidents_per_airport") or {}).get("max", 5))
        risks, airport_threat_map, risk_warnings = airport_risks(repo, airports, max_items=max_items)
        warnings.extend(risk_warnings)
        exp_records = experience_records(experience, airports, target)

        sections: list[str] = []
        greeting = normalize_text(settings.get("greeting", ""))
        if greeting:
            sections.append(greeting)
        sections.append(profile_intro(profile, aircraft_types))
        exp_text = experience_text(exp_records)
        if exp_text:
            sections.append(exp_text)
        feedback = feedback_text(profile)
        if feedback:
            sections.append(feedback)

        sections.append("本次航班信息：\n" + "\n".join(flight_lines(flights)))
        if weather_lines:
            sections.append(
                "航空天气（自动获取的原始METAR/TAF，仅用于提前准备，最终以航前最新报文、放行资料及ATIS为准）：\n"
                + "\n".join(f"{i}. {line}" for i, line in enumerate(weather_lines, start=1))
            )

        for airport in airports:
            risk_text = "\n".join(f"{i}. {item}" for i, item in enumerate(risks[airport], start=1))
            sections.append(f"{airport}典型不安全事件/风险识别：\n{risk_text}")

        threat_lines: list[str] = []
        for airport in airports:
            for item in airport_threat_map.get(airport, []):
                threat_lines.append(f"{airport}：{item}")
        threat_lines.extend(global_threats(operational_focus, target.month))
        threat_lines = unique(threat_lines)
        sections.append(
            "核心威胁与控制措施：\n"
            + "\n".join(f"{i}. {item}" for i, item in enumerate(threat_lines, start=1))
        )

        content = "\n\n".join(s.strip() for s in sections if s.strip()).strip() + "\n"
        errors = validate_content(content, flights, profile)
        if errors:
            status = {"status": "FAILED_SAFE", "target_date": target.isoformat(), "errors": errors, "version": VERSION, "note": "正式准备稿未覆盖。"}
            write_status(repo, status)
            append_github_summary("## 免费航前准备\n\n**FAILED_SAFE**：\n" + "\n".join(f"- {e}" for e in errors))
            return 2

        dated_name = f"{target.isoformat()}_航前准备.txt"
        atomic_write_text(output_dir / dated_name, content)
        atomic_write_text(output_dir / "latest.txt", content)
        atomic_write_json(
            output_dir / "latest_meta.json",
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "generated_at_beijing": now_beijing().isoformat(),
                "generator": VERSION,
                "flight_numbers": [e.flight_number for e in flights],
                "airports": airports,
                "warnings": unique(warnings),
                "airport_experience_changes": changes,
            },
        )
        atomic_write_text(success_marker, "SUCCESS\n")
        write_status(repo, {"status": "SUCCESS", "target_date": target.isoformat(), "output": str(output_dir / dated_name), "version": VERSION})
        summary = f"## {target.isoformat()} 航前准备（免费规则版）\n\n```text\n{content}```"
        if warnings:
            summary += "\n\n### 系统提示\n" + "\n".join(f"- {w}" for w in unique(warnings))
        append_github_summary(summary)
        print(f"SUCCESS: {output_dir / dated_name}")
        return 0

    except Exception as exc:
        status = {
            "status": "FAILED_SAFE",
            "target_date": target.isoformat(),
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=12),
            "version": VERSION,
            "note": "正式准备稿未覆盖。",
        }
        write_status(repo, status)
        append_github_summary(f"## 免费航前准备\n\n**FAILED_SAFE**：{type(exc).__name__}: {exc}\n\n原准备稿未覆盖。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
