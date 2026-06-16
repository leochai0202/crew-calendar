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
from crew_agents.weather import fetch_airport_weather

VERSION = "flight-prep-free-v3-manual-20260615-all-airports"
RISK_KEYWORDS = (
    "跑道", "滑行", "进近", "离场", "复飞", "盲降", "双截获", "高截获", "风切变",
    "乱流", "雷雨", "鸟击", "GPS", "地形", "气压", "灯光", "军航", "高度", "速度",
    "PAPI", "ILS", "下滑", "能量", "脱离", "机坪", "等待线", "强回波", "湿跑道",
    "高原", "标高", "下降率", "顺风", "侧风", "爬升梯度", "减速", "构型", "形态",
)
EXCLUDE_KEYWORDS = (
    "酒店", "住宿", "接送", "餐食", "电话", "地址", "联系人", "前台", "供应商",
    "车程", "车辆提供方", "业务联系", "接机地点", "送机地点",
)
MANUAL_HEADER_SUFFIX = "机场运行特点"


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



def compact_key(value: str) -> str:
    value = (value or "").upper()
    value = re.sub(r"\s+", "", value)
    value = value.replace("／", "/").replace("（", "(").replace("）", ")")
    value = re.sub(r"[·•，。；、:：_\-—()（）\[\]【】]", "", value)
    return value


def manual_version(path: Path) -> int:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:12000]
    except Exception:
        return 0
    versions = [int(x) for x in re.findall(r"版本号\s*[:：]?\s*(20\d{6})", head)]
    if versions:
        return max(versions)
    match = re.search(r"(20\d{6})", path.name)
    return int(match.group(1)) if match else 0


def find_latest_airport_manual(knowledge_dir: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in ("airport_information*.txt", "*机场特点*.txt", "AirDropManual*.txt", "*.txt"):
        candidates.extend(knowledge_dir.glob(pattern))
    unique_paths = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file()))
    relevant: list[Path] = []
    for path in unique_paths:
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:200000]
        except Exception:
            continue
        if "机场运行特点" not in compact_key(sample) and "机场特点" not in path.name:
            continue
        relevant.append(path)
    if not relevant:
        return None
    relevant.sort(key=lambda p: (manual_version(p), p.stat().st_mtime), reverse=True)
    return relevant[0]


def is_manual_airport_header(line: str) -> bool:
    key = compact_key(line)
    return (
        key.endswith(compact_key(MANUAL_HEADER_SUFFIX))
        and "汇总" not in key
        and "威胁识别" not in key
        and 6 <= len(key) <= 80
    )


def clean_header_airport_name(line: str) -> str:
    key = compact_key(line)
    suffix = compact_key(MANUAL_HEADER_SUFFIX)
    if key.endswith(suffix):
        key = key[:-len(suffix)]
    return key.replace("/", "")


def build_manual_index(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headers = [i for i, line in enumerate(lines) if is_manual_airport_header(line)]
    sections: list[dict] = []
    for pos, start_idx in enumerate(headers):
        end_idx = headers[pos + 1] if pos + 1 < len(headers) else len(lines)
        header = lines[start_idx].strip()
        body_lines = lines[start_idx:end_idx]
        probe = "\n".join(body_lines[:8])
        code_match = re.search(r"\(([A-Z0-9]{3})\s*/\s*([A-Z0-9]{4})\)", probe, re.I)
        iata = code_match.group(1).upper() if code_match else ""
        icao = code_match.group(2).upper() if code_match else ""
        name_key = clean_header_airport_name(header)
        aliases = {name_key}
        raw_name = compact_key(header)
        raw_name = raw_name[:-len(compact_key(MANUAL_HEADER_SUFFIX))]
        for part in re.split(r"[/／]", raw_name):
            part = compact_key(part)
            if len(part) >= 2:
                aliases.add(part)
        if name_key.endswith("国际"):
            aliases.add(name_key[:-2])
        sections.append(
            {
                "header": header,
                "name_key": name_key,
                "aliases": sorted(aliases, key=len, reverse=True),
                "iata": iata,
                "icao": icao,
                "lines": body_lines,
            }
        )
    return sections


def match_manual_section(index: list[dict], airport: str, icao: str) -> dict | None:
    airport_key = compact_key(airport).replace("机场", "")
    best: tuple[int, dict] | None = None
    for section in index:
        score = 0
        if icao and section.get("icao") == icao.upper():
            score += 1000
        name_key = str(section.get("name_key", "")).replace("机场", "")
        if airport_key == name_key:
            score += 500
        elif airport_key and name_key and (airport_key in name_key or name_key in airport_key):
            score += 300 + min(len(airport_key), len(name_key))
        for alias in section.get("aliases", []):
            alias_key = str(alias).replace("机场", "")
            if not alias_key:
                continue
            if airport_key == alias_key:
                score += 250
            elif len(alias_key) >= 2 and (alias_key in airport_key or airport_key in alias_key):
                score += 120 + min(len(alias_key), len(airport_key))
        if score and (best is None or score > best[0]):
            best = (score, section)
    return best[1] if best else None


def is_boilerplate_line(line: str) -> bool:
    compact = compact_key(line)
    if not compact:
        return True
    if compact.startswith("非受控文件") or "FORREFERENCEONLY" in compact:
        return True
    if compact.startswith("版本号") or compact.startswith("修改日期"):
        return True
    if re.fullmatch(r"\d+/\d+", compact):
        return True
    if compact.startswith("更新日期") or compact.startswith("责任中队"):
        return True
    if compact.endswith("机场运行特点"):
        return True
    if re.fullmatch(r"[A-Z0-9/]+", compact):
        return True
    return False


def heading_kind(line: str) -> str:
    key = compact_key(line)
    if "典型不安全事件详述" in key:
        return "details"
    if "典型不安全事件" in key:
        return "typical"
    if "核心威胁" in key:
        return "core"
    if "运行特点" in key:
        return "operations"
    if "特殊运行要求" in key or "特殊要求" in key:
        return "special"
    return ""


def clean_manual_item(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(
        r"^(?:[一二三四五六七八九十]+[、.．，,:：]|[（(]?\d+[）).、，,:：]\s*)+",
        "",
        value,
    )
    value = value.strip("；;，,。 ")
    value = re.sub(r"\s+([，。；：、）])", r"\1", value)
    value = re.sub(r"([（])\s+", r"\1", value)
    if not value:
        return ""
    if len(value) > 360:
        cut = max(value.rfind("。", 0, 360), value.rfind("；", 0, 360))
        value = value[: cut + 1 if cut >= 100 else 360].rstrip("，； ") + "……"
    elif not value.endswith(("。", "！", "？", "……")):
        value += "。"
    return value


def lines_to_numbered_items(lines: list[str], max_items: int) -> list[str]:
    items: list[str] = []
    current = ""
    number_re = re.compile(r"^\s*(?:[（(]?\d+[）).、，,:：]|[一二三四五六七八九十]+[、.．，,:：])\s*")
    sub_re = re.compile(r"^\s*[（(]\d+[）)]\s*")
    for raw in lines:
        if is_boilerplate_line(raw):
            continue
        line = normalize_text(raw)
        if not line or heading_kind(line):
            continue
        if any(word in line for word in EXCLUDE_KEYWORDS):
            continue

        starts_number = bool(number_re.match(line))
        starts_sub = bool(sub_re.match(line))
        if starts_number and not starts_sub:
            if current:
                cleaned = clean_manual_item(current)
                if cleaned:
                    items.append(cleaned)
            current = number_re.sub("", line, count=1)
        else:
            if current:
                current += ("" if re.search(r"[\u4e00-\u9fff，、（(]$", current) else " ") + line
            else:
                current = sub_re.sub("", line, count=1)

        if len(items) >= max_items:
            break

    if current and len(items) < max_items:
        cleaned = clean_manual_item(current)
        if cleaned:
            items.append(cleaned)
    return unique(items)[:max_items]


def extract_manual_lists(section: dict, max_items: int) -> tuple[list[str], list[str]]:
    lines = list(section.get("lines") or [])
    typical_lines: list[str] = []
    core_lines: list[str] = []
    mode = ""
    for raw in lines:
        kind = heading_kind(raw)
        if kind == "typical":
            mode = "typical"
            continue
        if kind == "core":
            mode = "core"
            continue
        if kind in ("operations", "special", "details"):
            if mode in ("typical", "core"):
                mode = ""
            continue
        if mode == "typical":
            typical_lines.append(raw)
        elif mode == "core":
            core_lines.append(raw)

    typical = lines_to_numbered_items(typical_lines, max_items)
    core = lines_to_numbered_items(core_lines, max_items)

    if not typical:
        whole_candidates: list[str] = []
        for raw in lines:
            line = normalize_text(raw)
            if is_boilerplate_line(line) or heading_kind(line):
                continue
            if any(word in line for word in EXCLUDE_KEYWORDS):
                continue
            if any(word in line for word in RISK_KEYWORDS):
                item = clean_manual_item(line)
                if item:
                    whole_candidates.append(item)
        typical = unique(whole_candidates)[:max_items]
    return typical, core


def manual_airport_data(
    knowledge_dir: Path,
    airports: list[str],
    icao_map: dict[str, str],
    max_items: int,
) -> tuple[dict[str, dict], str, int]:
    source = find_latest_airport_manual(knowledge_dir)
    if not source:
        return {}, "", 0
    text = source.read_text(encoding="utf-8", errors="replace")
    index = build_manual_index(text)
    result: dict[str, dict] = {}
    for airport in airports:
        section = match_manual_section(index, airport, icao_map.get(airport, ""))
        if not section:
            continue
        typical, core = extract_manual_lists(section, max_items)
        result[airport] = {
            "typical_incidents": typical,
            "core_threats": core,
            "matched_header": section.get("header", ""),
            "matched_icao": section.get("icao", ""),
        }
    return result, str(source), manual_version(source)


def supplements_for_airport(supplements: dict, airport: str) -> tuple[dict, str]:
    airport_data = supplements.get("airports", supplements)
    for name, value in airport_data.items():
        aliases = value.get("aliases", []) if isinstance(value, dict) else []
        if name == airport or name in airport or airport in name or any(a and (a in airport or airport in a) for a in aliases):
            return value if isinstance(value, dict) else {}, name
    return {}, ""


def airport_risks(
    repo: Path,
    airports: list[str],
    icao_map: dict[str, str],
    max_items: int,
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], str, int]:
    supplements = load_json(repo / "config" / "airport_supplements.json", {}) or {}
    manual_data, manual_source, manual_ver = manual_airport_data(
        repo / "knowledge", airports, icao_map, max_items=max_items
    )

    risks: dict[str, list[str]] = {}
    threats: dict[str, list[str]] = {}
    warnings: list[str] = []

    for airport in airports:
        supplement, matched_name = supplements_for_airport(supplements, airport)
        manual = manual_data.get(airport, {})

        manual_risks = list(manual.get("typical_incidents") or [])
        manual_threats = list(manual.get("core_threats") or [])
        structured_risks = list(supplement.get("typical_incidents") or [])
        structured_threats = list(supplement.get("core_threats") or [])

        # Curated supplement wording is concise and already matches the user's established template.
        # The latest dated manual is used to fill any missing airport/section and to guarantee coverage.
        merged_risks = unique(structured_risks)
        if len(merged_risks) < 2:
            merged_risks = unique([*merged_risks, *manual_risks])
        if len(merged_risks) < 2:
            merged_risks = unique([*merged_risks, *manual_threats])
        merged_risks = merged_risks[:max_items]

        merged_threats = unique(structured_threats)
        if len(merged_threats) < 2:
            merged_threats = unique([*merged_threats, *manual_threats])
        merged_threats = merged_threats[:max_items]

        if not merged_risks:
            warnings.append(f"{airport}未在最新机场特点或补充知识库中找到典型风险")
        if not merged_threats:
            warnings.append(f"{airport}未在最新机场特点或补充知识库中找到核心威胁")

        risks[airport] = merged_risks
        threats[airport] = merged_threats

        if manual:
            warnings.append(
                f"{airport}匹配最新机场特点章节：{manual.get('matched_header', '')}"
                + (f"（{manual.get('matched_icao')}）" if manual.get("matched_icao") else "")
            )
        elif matched_name:
            warnings.append(f"{airport}未匹配手册章节，使用补充知识库：{matched_name}")

    return risks, threats, warnings, manual_source, manual_ver


def global_threats(operational_focus: dict, month: int) -> list[str]:
    items: list[str] = []
    if 4 <= month <= 10:
        items.extend((operational_focus.get("thunderstorm_avoidance") or [])[:4])
    items.extend((operational_focus.get("stabilized_approach") or [])[:3])
    items.extend((operational_focus.get("energy_and_configuration") or [])[:2])
    items.extend((operational_focus.get("ground_operations") or [])[:2])
    items.extend((operational_focus.get("crm_and_fatigue") or [])[:2])
    return unique(items)


def validate_content(content: str, flights: list[CalendarEvent], profile: dict, airports: list[str]) -> list[str]:
    errors = []
    for event in flights:
        if event.flight_number and event.flight_number not in content:
            errors.append(f"正文漏掉航班号{event.flight_number}")
    if profile.get("name") and profile["name"] not in content:
        errors.append("正文缺少姓名")

    for airport in airports:
        risk_header = f"{airport}典型不安全事件/风险识别："
        if risk_header not in content:
            errors.append(f"正文漏掉{airport}典型不安全事件/风险识别")
        if f"{airport}：" not in content:
            errors.append(f"正文漏掉{airport}核心威胁与控制措施")

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
        risks, airport_threat_map, risk_warnings, manual_source, manual_ver = airport_risks(
            repo, airports, icao_map, max_items=max_items
        )
        warnings.extend(risk_warnings)

        missing_airports = [
            airport for airport in airports
            if not risks.get(airport) or not airport_threat_map.get(airport)
        ]
        if missing_airports:
            status = {
                "status": "FAILED_SAFE",
                "target_date": target.isoformat(),
                "errors": [f"最新机场特点未完整匹配：{airport}" for airport in missing_airports],
                "version": VERSION,
                "airport_information_file": manual_source,
                "airport_information_version": manual_ver,
                "note": "任一涉及机场缺少典型风险或核心威胁，正式准备稿不覆盖。",
            }
            write_status(repo, status)
            append_github_summary(
                "## 免费航前准备\n\n**FAILED_SAFE**：机场资料不完整，未覆盖正式准备稿。\n"
                + "\n".join(f"- {airport}" for airport in missing_airports)
            )
            return 2
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
        errors = validate_content(content, flights, profile, airports)
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
                "airport_information_file": manual_source,
                "airport_information_version": manual_ver,
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
