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

VERSION = "flight-prep-free-v6-professional-template-20260616"
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


# Curated wording is intentionally written from the operating crew's point of view.
# Source provenance is kept in code comments/metadata and is not printed into the group-ready text.
CURATED_TYPICAL_INCIDENTS: dict[str, list[str]] = {
    "上海浦东": [
        "浦东鸟类活动较为频繁，曾发生低高度鸟击并造成雷达罩损伤的事件。",
        "曾发生低高度失去目视参考后继续进近的情况；目视参考不足或飞机状态不满足稳定进近标准时，应及时复飞。",
        "浦东空域繁忙，进近阶段前后机间隔紧凑，曾发生TA/RA事件。",
        "地面滑行路线复杂、热点较多，部分滑行道及道口可能受施工、临时关闭或运行调整影响，存在滑错路线和跑道侵入风险。",
        "雷达引导、直飞及临时更改进近方式较多，容易造成下降剖面偏高、速度偏大或构型建立偏晚。",
    ],
    "丽江三义": [
        "曾发生SINK RATE警告事件，应重点监控下降率、能量状态和稳定进近条件。",
        "曾发生风切变事件，高原地形和局地气流可能造成风向风速及顺风分量快速变化。",
        "曾发生重着陆事件，应加强低高度下降率、拉平时机和接地姿态控制。",
        "曾发生形态超过高度限制事件，应提前规划下降和减速，避免因剖面偏高导致高高度提前放形态。",
        "丽江GPS信号存在工作不稳定的可能，应加强导航位置、航迹和机载导航性能的交叉检查。",
    ],
}

PUDONG_2606_EFFECTIVE = date(2026, 6, 11)


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


def strip_terminal_punct(value: str) -> str:
    return (value or "").strip().rstrip("。；;，, .")


def feedback_text(profile: dict) -> str:
    feedback = profile.get("recent_feedback") or {}
    pf = strip_terminal_punct(feedback.get("PF", ""))
    pm = strip_terminal_punct(feedback.get("PM", ""))
    rnp = strip_terminal_punct(feedback.get("RNP", ""))
    if not pf and not pm and not rnp:
        return ""
    parts = []
    if pf:
        parts.append(f"上一次作为PF教员评价{pf}")
    if pm:
        parts.append(f"作为PM教员评价{pm}")
    text = "上一次飞行中教员/机长对我优缺点的评价（作为PF/PM各取最近一次）：" + "；".join(parts) + "。"
    if rnp:
        text += f"补充讲评：{rnp}。"
    return text


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


AIRPORT_SHORT_NAMES = {
    "上海浦东": "浦东",
    "上海虹桥": "虹桥",
    "丽江三义": "丽江",
    "揭阳潮汕": "揭阳",
    "扬州泰州": "扬州",
    "长春龙嘉": "长春",
    "深圳宝安": "深圳",
    "济南遥墙": "济南",
    "大连周水子": "大连",
    "沈阳桃仙": "沈阳",
    "兰州中川": "兰州",
    "威海大水泊": "威海",
    "乌兰巴托成吉思汗": "乌兰巴托",
    "釜山金海": "釜山",
    "成都双流": "成都双流",
    "名古屋中部": "名古屋",
}


def short_airport_name(airport: str) -> str:
    if airport in AIRPORT_SHORT_NAMES:
        return AIRPORT_SHORT_NAMES[airport]
    return airport.replace("国际机场", "").replace("机场", "").strip()


def airport_with_suffix(airport: str) -> str:
    return short_airport_name(airport) + "机场"


def personal_intro(profile: dict, records: list[dict], aircraft_types: list[str]) -> str:
    name = profile.get("name", "")
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    parts = [f"我是{unit}{role}{name}" if name else f"{unit}{role}".strip()]
    if profile.get("technical_level"):
        parts.append(f"目前技术级别{profile['technical_level']}")
    if profile.get("promotion_date"):
        parts.append(f"晋级日期{profile['promotion_date']}")
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

    operated = [r for r in records if r.get("within")]
    not_operated = [r for r in records if not r.get("within")]
    if not_operated:
        parts.append("近3个月未运行过" + "、".join(airport_with_suffix(r['airport']) for r in not_operated))
    if operated:
        for rec in operated:
            if rec.get("last"):
                parts.append(f"{airport_with_suffix(rec['airport'])}上次运行时间为{format_date_cn(rec['last'])}")
            else:
                parts.append(f"近3个月已运行过{airport_with_suffix(rec['airport'])}")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        last_text = f"上次操纵落地机场为{last['airport']}"
        if last.get("date"):
            last_text += format_date_cn(last["date"])
        parts.append(last_text)
    return "，".join(p for p in parts if p) + "。"


WX_CODES = {
    "-RA": "小雨", "RA": "降雨", "+RA": "大雨", "SHRA": "阵雨",
    "BR": "轻雾", "FG": "雾", "HZ": "霾", "TS": "雷暴", "TSRA": "雷雨",
    "DZ": "毛毛雨", "SN": "降雪", "-SN": "小雪", "FZFG": "冻雾",
}


def decode_weather_report(raw: str) -> list[str]:
    raw = normalize_text(raw).upper()
    if not raw:
        return []
    out: list[str] = []
    vis_values = [int(x) for x in re.findall(r"(?<!\\d)([0-8]\\d{3}|9999)(?!\\d)", raw)]
    if vis_values:
        vis = min(vis_values)
        out.append("能见度10公里以上" if vis == 9999 else f"能见度{vis}米")
    for code, cn in WX_CODES.items():
        if re.search(rf"(?<![A-Z]){re.escape(code)}(?![A-Z])", raw) and cn not in out:
            out.append(cn)
    cloud_matches = re.findall(r"\\b(FEW|SCT|BKN|OVC)(\\d{3})\\b", raw)
    if cloud_matches:
        order = {"OVC": 4, "BKN": 3, "SCT": 2, "FEW": 1}
        cover, height = sorted(cloud_matches, key=lambda x: (int(x[1]), -order[x[0]]))[0]
        cloud_cn = {"FEW": "少云", "SCT": "疏云", "BKN": "多云", "OVC": "阴天"}[cover]
        out.append(f"{cloud_cn}，云底约{int(height) * 100}英尺")
    if "WS" in raw or "WIND SHEAR" in raw:
        out.append("存在风切变提示")
    return unique(out)


def weather_risk_sentence(airports: list[str], icao_map: dict[str, str], timeout: int) -> tuple[str, list[str]]:
    sentences: list[str] = []
    warnings: list[str] = []
    for airport in airports:
        icao = icao_map.get(airport, "")
        result = fetch_airport_weather(icao, timeout=timeout)
        metar_items = decode_weather_report(result.metar)
        taf_items = decode_weather_report(result.taf)
        short = airport_with_suffix(airport)
        if metar_items or taf_items:
            parts = []
            if metar_items:
                parts.append("当前METAR显示" + "、".join(metar_items[:4]))
            if taf_items:
                parts.append("TAF提示" + "、".join(taf_items[:4]))
            sentences.append(short + "".join(parts) + "，最终以航前最新报文、放行资料及ATIS为准")
        else:
            sentences.append(short + "暂未获取到有效METAR/TAF，最终以航前最新报文、放行资料及ATIS为准")
        if result.error:
            warnings.append(f"{airport}天气获取提示：{result.error}")
    return "；".join(sentences) + "。", warnings


def expand_incident_items(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        raw = strip_terminal_punct(item)
        if "曾发生" in raw and any(k in raw for k in ("SINK RATE", "风切变", "重着陆", "形态超高度")):
            for token in ("SINK RATE", "风切变", "重着陆", "形态超高度限制"):
                if token in raw:
                    suffix = "警告事件" if token == "SINK RATE" else "事件"
                    out.append(f"该机场曾发生{token}{suffix}。")
        else:
            out.append(item)
    return unique(out)


def seasonal_clean(item: str, month: int) -> str:
    text = strip_terminal_punct(item)
    if 5 <= month <= 9:
        text = re.sub(r"1\s*-\s*4\s*月[^；。]*[；。]?", "", text).strip("；。 ")
    elif month in (10, 11, 12, 1, 2, 3):
        text = re.sub(r"5\s*-\s*9\s*月[^；。]*[；。]?", "", text).strip("；。 ")
    return text + ("。" if text else "")


def build_typical_items(risks: list[str], threats: list[str], month: int, max_items: int = 5) -> list[str]:
    items = expand_incident_items(risks)
    excluded_prefixes = ("机场分类", "高原机场", "指挥特点", "地形", "气象特点", "特殊复杂程序")
    items = [x for x in items if not strip_terminal_punct(x).startswith(excluded_prefixes)]
    if len(items) < 2:
        for item in threats:
            if strip_terminal_punct(item).startswith(excluded_prefixes[:3]):
                continue
            if any(word in item for word in ("风切变", "SINK RATE", "重着陆", "下降梯度", "顺风", "双截获", "高截获", "GPS", "鸟击", "滑错", "跑道")):
                items.append(seasonal_clean(item, month))
    return unique([x for x in items if x])[:max_items]


def natural_core_item(item: str, month: int) -> str:
    text = strip_terminal_punct(seasonal_clean(item, month))
    text = re.sub(r"[（(][^）)]*(?:参考|详见|EFB|航图汇总)[^）)]*[）)]", "", text)
    text = re.sub(r"(?:请)?参考\s*(?:EFB|航图|机场特点)[^；。]*", "", text)
    text = re.sub(r"详见[^；。]*", "", text)
    replacements = [
        (r"^机场分类[:：]", "该机场为"),
        (r"^高原机场[:：]", "属于"),
        (r"^指挥特点[:：]", "管制指挥方面，"),
        (r"^地形[:：]", "地形方面，"),
        (r"^气象特点[:：]", "气象方面，"),
        (r"^道面特点[:：]", "道面方面，"),
        (r"^其他威胁[:：]", ""),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    text = text.replace("建议机组", "我们应").replace("请机组", "我们应").replace("机组注意", "我们应注意")
    text = re.sub(r"\s+", " ", text).strip("；。 ")
    return text


def core_paragraph(airport: str, items: list[str], month: int) -> str:
    cleaned = unique([natural_core_item(x, month) for x in items if natural_core_item(x, month)])[:5]
    return f"{short_airport_name(airport)}：" + "；".join(cleaned) + "。"


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



def canonical_airport_name(airport: str) -> str:
    short = short_airport_name(airport)
    if short == "浦东":
        return "上海浦东"
    if short == "丽江":
        return "丽江三义"
    return airport


def is_airport(airport: str, target_name: str) -> bool:
    return canonical_airport_name(airport) == target_name


def compact_flight_numbers(flights: list[CalendarEvent]) -> str:
    numbers = [e.flight_number for e in flights if e.flight_number]
    if not numbers:
        return ""
    first = numbers[0]
    parts = [first]
    prefix_match = re.match(r"^([A-Z0-9]*[A-Z])(\d.*)$", first)
    prefix = prefix_match.group(1) if prefix_match else ""
    for number in numbers[1:]:
        if prefix and number.startswith(prefix):
            parts.append(number[len(prefix):])
        else:
            parts.append(number)
    return "/".join(parts)


def route_chain_text(flights: list[CalendarEvent]) -> str:
    chain: list[str] = []
    for event in flights:
        dep, arr = event.route
        if dep and (not chain or chain[-1] != dep):
            chain.append(dep)
        if arr and (not chain or chain[-1] != arr):
            chain.append(arr)
    return "—".join(short_airport_name(x) for x in chain)


def flight_overview_text(flights: list[CalendarEvent], target: date) -> str:
    number_text = compact_flight_numbers(flights)
    route_text = route_chain_text(flights)
    tomorrow = (now_beijing() + timedelta(days=1)).date()
    if target == tomorrow:
        prefix = "明日航班为"
    else:
        prefix = f"{target.month}月{target.day}日航班为"
    details = "，".join(x for x in (number_text, route_text) if x)
    return prefix + details + "。" if details else ""


def professionalize_incident(item: str) -> str:
    text = strip_terminal_punct(item)
    text = re.sub(r"[（(][^）)]*(?:参考|详见|EFB|机场特点汇总)[^）)]*[）)]", "", text)
    text = text.replace("请机组识别相关风险", "应提前识别并做好相应预案")
    text = text.replace("请机组注意识别该风险", "应提前识别并做好相应预案")
    text = text.replace("请机组注意", "我们应注意")
    text = re.sub(r"\s+", " ", text).strip("；。 ")
    return text + "。" if text else ""


def selected_typical_items(
    airport: str,
    risks: list[str],
    threats: list[str],
    month: int,
    max_items: int,
) -> list[str]:
    curated = CURATED_TYPICAL_INCIDENTS.get(canonical_airport_name(airport), [])
    if curated:
        return curated[:max_items]
    return [professionalize_incident(x) for x in build_typical_items(risks, threats, month, max_items=max_items) if professionalize_incident(x)]


def overall_risk_items(
    airports: list[str],
    target: date,
    weather_sentence: str,
) -> list[str]:
    items: list[str] = []
    if any(is_airport(a, "上海浦东") for a in airports):
        if target >= PUDONG_2606_EFFECTIVE:
            items.append(
                "浦东机场运行流量大，多跑道运行，地面滑行路线和空中进离场程序较为复杂；"
                "2606期飞行程序已经调整，应重点防范新旧程序混淆、跑道过渡选择错误和FMS数据输入错误。"
            )
        else:
            items.append("浦东机场运行流量大，多跑道运行，地面滑行路线和空中进离场程序较为复杂。")
    if any(is_airport(a, "丽江三义") for a in airports):
        items.append(
            "丽江为一般高原复杂机场，机场标高7358英尺，周围地形复杂，进近剖面较陡；"
            "管制指挥可能造成下降偏晚、剖面偏高和构型建立偏晚。"
        )
        if 5 <= target.month <= 9:
            items.append(
                "丽江处于雨季，应重点关注降水、低云、风切变、湿跑道、顺风及着陆距离变化，"
                "提前完成性能评估并明确复飞、等待和备降预案。"
            )
    if 4 <= target.month <= 10:
        items.append(
            "航路及终端区可能涉及雷雨绕飞、直飞、雷达引导和高度变化，"
            "我们应加强频率守听、指令复诵和交叉证实，持续监控油量、航迹和最低安全高度。"
        )
    if weather_sentence:
        items.append(weather_sentence)
    return unique(items)


def pudong_core_items(target: date) -> list[str]:
    items: list[str] = []
    if target >= PUDONG_2606_EFFECTIVE:
        items.extend([
            "浦东2606期飞行程序已经调整。航前应确认导航数据库处于当前有效周期，并结合最新航图、航图勘误、NOTAM和放行资料核对所用进离场程序；如航路涉及相关点位，应注意BEKOK替代原PINOT、NUPLA替代原TOSAS，防止使用旧名称或旧程序。",
            "浦东离场程序应重点检查“跑道过渡＋离场公共段”是否与ATC指令一致。多条跑道可能共用相似离场代码，PF和PM应分别核对跑道、程序名称、第一航路点及高度限制；如使用PIKAS相关离场，应重点区分PIKAS-3与PIKAS-5，避免选错跑道过渡。",
            "浦东16L、17R、34R、35L跑道部分VNAV、GP INOP及LNAV进近最低标准已经调整，航前应使用最新有效标准，不能沿用旧数据；如执行VOR 17L或VOR 35R进近，应重点核对航图、导航数据库修正内容及相关高度限制。",
        ])
    items.extend([
        "如执行34R盲降进近，在特定位置和高度可能因地面建筑物造成无线电高度跳变并触发TERRAIN警戒。我们应结合实际位置、高度、导航精度和飞机状态准确判断，严格按照当前有效操作通告处置并按要求报告，避免形成惯性判断。",
        "浦东空域内进离港航空器数量多，且可能受到虹桥进离港航流影响。我们应严格执行高度、速度和航向指令，接近目标高度最后2000英尺时关注邻近航空器并合理控制升降率；收到直飞或雷达引导后，应重新评估剩余距离、下降剖面和减速需求，飞机未准备好时不应急于接受过度内切或转向五边。",
        "浦东地面运行环境复杂。收到滑行指令后，应完整复诵，结合航图、地面标识、跑道状态灯和外部目视交叉检查；滑行期间避免两名飞行员同时低头操作。若ATC指挥FOLLOW GREEN，接近交叉道口应减速确认；绿灯中断、出现多个方向或与ATC指令不一致时，应停止滑行并向管制证实。",
    ])
    if 5 <= target.month <= 9:
        items.append(
            "浦东夏季雷雨活动频繁，同时可能伴随低云、低能见、湿跑道、风切变和鸟击风险。"
            "起飞前应综合天气雷达、放行资料、航路天气和备降条件，提前评估绕飞方向、等待能力及剩余油量；"
            "目的地天气不满足着陆标准或趋势持续恶化时，应尽早与AOC沟通。"
        )
    return items


def lijiang_core_items(target: date) -> list[str]:
    items = [
        "丽江机场标高7358英尺，属于一般高原机场，机场周围四面环山，东西两侧地形限制明显。我们应严格按照公布程序飞行，持续监控航迹、高度、最低安全高度和导航精度；雷达引导、直飞或天气绕飞时，应特别防范偏离程序后接近复杂地形。",
        "丽江进近经常存在下降偏晚和剖面偏高的情况。我们应提前制定下降、减速和构型计划，结合剩余距离、顺风、地速和下降率及时向管制申请下降或减速，避免为追赶剖面使用过大下降率；兼顾高高度放形态限制，尽量在低于5700米、进近阶段已经启用且速度满足限制后再选择形态一。",
        "20号跑道相关进近下降梯度较大，且五边可能存在顺风。我们应提前建立形态和着陆构型，持续监控下降率、速度趋势、推力状态和垂直偏差，防止因下降梯度大、顺风或构型建立过晚造成SINK RATE、不稳定进近或重着陆；未在规定高度达到稳定进近标准时，应果断复飞。",
    ]
    if 5 <= target.month <= 9:
        items.append(
            "丽江5月至9月处于雨季，应重点关注降水、低云、风切变、湿跑道和着陆距离。"
            "航前应根据实际跑道状况、风向风速、飞机重量和制动效应完成着陆性能评估，必要时考虑使用中档自动刹车，并明确复飞、等待或备降预案。"
        )
    items.extend([
        "丽江进近区域实施ADS-B管制，且GPS存在工作不稳定的可能。飞行中应监控GPS状态、导航精度、飞机位置及航迹变化；如出现GPS PRIMARY LOST、FM/GPS位置不一致或导航性能下降，应及时向ATC报告，并做好使用传统导航设施、非GPS进近方式及公司共同决策的准备。",
        "如航前NOTAM或ATIS显示丽江盲降或盲降下滑道不可用，应按照当前有效操作通告重新准备进近方式。执行RNP 20或RNP 02进近时使用FINAL APP制导，转向五边前建立形态二并选择不小于160节的速度；许可RNP进近后，按所用跑道设置FDP点限制高度并检查APPR及FMA水平、垂直方式正确待命或接通。执行RNP 20时，还应按要求设置DDA。盲降设备正常时，不固定套用该特殊程序。",
    ])
    return items


def generic_core_items(items: list[str], month: int, max_items: int = 6) -> list[str]:
    result: list[str] = []
    for item in items:
        text = natural_core_item(item, month)
        text = text.replace("建议", "我们应").replace("需要", "应")
        text = re.sub(r"\s+", " ", text).strip("；。 ")
        if not text:
            continue
        if not any(token in text for token in ("我们", "应", "注意", "防止", "避免", "严格", "提前", "确认", "监控")):
            text = "我们应结合实际运行条件重点关注" + text
        result.append(text + "。")
    return unique(result)[:max_items]


def airport_core_items(airport: str, source_items: list[str], target: date) -> list[str]:
    canonical = canonical_airport_name(airport)
    if canonical == "上海浦东":
        return pudong_core_items(target)
    if canonical == "丽江三义":
        return lijiang_core_items(target)
    return generic_core_items(source_items, target.month)


def general_control_items(target: date) -> list[str]:
    items = [
        "飞行中不得关闭气象雷达。应根据雷达型号和天气情况合理使用自动及人工模式；使用RDR-4B时不能仅依赖自动识别，应结合增益、倾斜角和人工扫描判断天气。",
        "云中绕飞时，与雷暴主体或强回波保持至少20海里；云外绕飞时，与积雨云保持至少6海里，并与雷暴主体或强回波保持至少20海里；从云上飞越时，与云顶保持至少1500米垂直间隔，否则不得飞越。低高度绕飞时，PM应重点监控地形显示、MSA和地形间隔。",
        "在光洁形态下放出形态前，PF应确认当前高度低于FL200、进近阶段已经启用、速度处于管理方式且低于VFE NEXT；PM复核后喊话“高度检查，速度检查”，再操作襟翼手柄。",
        "严格遵守IAF点速度和高度限制，飞机未准备好时不能转向五边；最迟7海里放轮，并在1500英尺AAL前建立稳定状态。使用减速板后，如无超速风险应及时收回，防止影响后续能量管理。",
        "复飞决策一旦作出，应立即执行标准复飞动作，不得再次收油门尝试继续着陆。低高度复飞以内部仪表为主，严格监控姿态、速度、形态和正上升率，避免复飞过程中出现超速、穿越高度或擦机尾风险；任何情况下使用反推后必须完成着陆全停。",
        "接近目标高度最后2000英尺时，如有邻近航空器，应合理限制升降率以降低TCAS告警风险；发生TA时应及时检查和控制升降率，并严格按照现行程序处置。",
    ]
    if not (4 <= target.month <= 10):
        # Keep the operational rules but avoid presenting summer thunderstorm risk as a seasonal forecast.
        items[0] = "飞行中应根据实际天气合理使用气象雷达，并结合雷达型号按要求使用自动及人工模式。"
    return items

def validate_content(content: str, flights: list[CalendarEvent], profile: dict, airports: list[str]) -> list[str]:
    errors = []
    if profile.get("name") and profile["name"] not in content:
        errors.append("正文缺少姓名")
    if "个人对本次航班中识别的风险：" not in content:
        errors.append("正文缺少个人风险识别标题")
    if "核心威胁：" not in content:
        errors.append("正文缺少核心威胁标题")
    if "航路及通用风险控制：" not in content:
        errors.append("正文缺少航路及通用风险控制")
    if flights and not any(e.flight_number and e.flight_number in content for e in flights):
        errors.append("正文缺少航班号")
    for airport in airports:
        short = short_airport_name(airport)
        if f"{short}机场典型不安全事件：" not in content:
            errors.append(f"正文漏掉{short}机场典型不安全事件")
        if f"{short}机场：" not in content:
            errors.append(f"正文漏掉{short}机场核心威胁")
    if "参考 EFB" in content or "参考EFB" in content or "机场特点汇总-" in content:
        errors.append("正文仍包含资料出处式表述")
    if len(content.strip()) < 900:
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

        weather_sentence = ""
        warnings: list[str] = []
        if settings.get("include_weather_section", True):
            weather_sentence, weather_warnings = weather_risk_sentence(
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
        intro = personal_intro(profile, exp_records, aircraft_types)
        sections.append((greeting + intro) if greeting else intro)

        feedback = feedback_text(profile)
        if feedback:
            sections.append(feedback)

        overview = flight_overview_text(flights, target)
        if overview:
            sections.append(overview)

        risk_items = overall_risk_items(airports, target, weather_sentence)
        risk_lines = ["个人对本次航班中识别的风险："]
        risk_lines.extend(f"{idx}. {strip_terminal_punct(item)}。" for idx, item in enumerate(risk_items, start=1))
        sections.append("\n".join(risk_lines))

        for airport in airports:
            typical_items = selected_typical_items(
                airport,
                risks.get(airport, []),
                airport_threat_map.get(airport, []),
                target.month,
                max_items=max_items,
            )
            risk_text = "\n".join(
                f"{i}. {strip_terminal_punct(item)}。" for i, item in enumerate(typical_items, start=1)
            )
            sections.append(f"{short_airport_name(airport)}机场典型不安全事件：\n{risk_text}")

        core_lines = ["核心威胁："]
        for airport in airports:
            items = airport_core_items(airport, airport_threat_map.get(airport, []), target)
            numbered = "\n".join(f"{idx}. {strip_terminal_punct(item)}。" for idx, item in enumerate(items, start=1))
            core_lines.append(f"{short_airport_name(airport)}机场：\n{numbered}")
        sections.append("\n\n".join(core_lines))

        general_lines = ["航路及通用风险控制："]
        general_lines.extend(
            f"{idx}. {strip_terminal_punct(item)}。"
            for idx, item in enumerate(general_control_items(target), start=1)
        )
        sections.append("\n".join(general_lines))

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
        summary = f"## {target.isoformat()} 航前准备\n\n```text\n{content}```"
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
