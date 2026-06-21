from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
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

VERSION = "flight-prep-free-v10-all-airports-manual-index-20260617"
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
        "曾发生低高度鸟击并造成雷达罩损伤事件。",
        "曾发生低高度失去目视参考后继续进近事件。",
        "曾发生进近阶段TA/RA事件。",
        "地面滑行路线复杂、热点较多，存在滑错路线和跑道侵入风险。",
    ],
    "丽江三义": [
        "曾发生SINK RATE警告事件。",
        "曾发生风切变事件。",
        "曾发生重着陆事件。",
        "曾发生形态超过高度限制事件。",
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
    "济州": "济州",
    "济州国际": "济州",
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

    tokens = re.findall(r"[A-Z+\-]{2,8}|\d{4}|(?:FEW|SCT|BKN|OVC)\d{3}", raw)
    token_set = set(tokens)
    out: list[str] = []

    vis_values = [int(token) for token in tokens if re.fullmatch(r"(?:[0-8]\d{3}|9999)", token)]
    if vis_values:
        vis = min(vis_values)
        if vis < 5000:
            out.append(f"能见度{vis}米")
        elif vis == 9999:
            out.append("能见度10公里以上")

    phenomena = [
        ("+TSRA", "强雷雨"), ("TSRA", "雷雨"), ("TS", "雷暴"),
        ("+SHRA", "强阵雨"), ("SHRA", "阵雨"),
        ("+RA", "大雨"), ("-RA", "小雨"), ("RA", "降雨"),
        ("FZFG", "冻雾"), ("FG", "雾"), ("BR", "轻雾"),
        ("HZ", "霾"), ("DZ", "毛毛雨"), ("-SN", "小雪"), ("SN", "降雪"),
    ]
    for code, label in phenomena:
        if code in token_set and label not in out:
            out.append(label)

    # Avoid broad duplicates when a more specific precipitation description exists.
    if any(x in out for x in ("小雨", "大雨", "阵雨", "强阵雨", "雷雨", "强雷雨")):
        out = [x for x in out if x != "降雨"]
    if any(x in out for x in ("雷雨", "强雷雨")):
        out = [x for x in out if x != "雷暴"]

    cloud_matches = re.findall(r"\b(FEW|SCT|BKN|OVC)(\d{3})\b", raw)
    if cloud_matches:
        order = {"OVC": 4, "BKN": 3, "SCT": 2, "FEW": 1}
        cover, height = sorted(cloud_matches, key=lambda x: (int(x[1]), -order[x[0]]))[0]
        feet = int(height) * 100
        if cover in ("BKN", "OVC") and feet <= 2000:
            cloud_cn = {"BKN": "多云", "OVC": "阴天"}[cover]
            out.append(f"{cloud_cn}，云底约{feet}英尺")

    if re.search(r"\bWS(?:\s+RWY\d{2}[LRC]?)?\b|WIND\s+SHEAR", raw):
        out.append("存在风切变提示")
    return unique(out)


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _day_hour_candidates(day: int, hour: int, reference: datetime) -> list[datetime]:
    ref = reference.astimezone(timezone.utc)
    candidates: list[datetime] = []
    for offset in (-1, 0, 1):
        year, month = _shift_month(ref.year, ref.month, offset)
        try:
            candidates.append(datetime(year, month, day, hour, tzinfo=timezone.utc))
        except ValueError:
            continue
    return candidates


def _nearest_day_hour(day: int, hour: int, reference: datetime) -> datetime | None:
    candidates = _day_hour_candidates(day, hour, reference)
    if not candidates:
        return None
    ref = reference.astimezone(timezone.utc)
    return min(candidates, key=lambda value: abs((value - ref).total_seconds()))


def parse_taf_validity(raw: str, reference: datetime) -> tuple[datetime, datetime] | None:
    match = re.search(r"\b(\d{2})(\d{2})/(\d{2})(\d{2})\b", (raw or "").upper())
    if not match:
        return None
    start_day, start_hour, end_day, end_hour = map(int, match.groups())
    start = _nearest_day_hour(start_day, start_hour, reference)
    if start is None:
        return None
    end_candidates = _day_hour_candidates(end_day, end_hour, start)
    end_candidates.extend(_day_hour_candidates(end_day, end_hour, start + timedelta(days=20)))
    end_candidates = [value for value in end_candidates if value > start]
    if not end_candidates:
        return None
    end = min(end_candidates)
    return start, end


def parse_metar_observation(raw: str, reference: datetime) -> datetime | None:
    match = re.search(r"\b(\d{2})(\d{2})(\d{2})Z\b", (raw or "").upper())
    if not match:
        return None
    day, hour, minute = map(int, match.groups())
    candidates: list[datetime] = []
    ref = reference.astimezone(timezone.utc)
    for offset in (-1, 0, 1):
        year, month = _shift_month(ref.year, ref.month, offset)
        try:
            candidates.append(datetime(year, month, day, hour, minute, tzinfo=timezone.utc))
        except ValueError:
            continue
    return min(candidates, key=lambda value: abs((value - ref).total_seconds())) if candidates else None


def relevant_airport_times(flights: list[CalendarEvent]) -> dict[str, list[datetime]]:
    result: dict[str, list[datetime]] = {}
    for event in flights:
        dep, arr = event.route
        if dep:
            result.setdefault(dep, []).append(event.start)
        if arr:
            result.setdefault(arr, []).append(event.end)
    return result


def weather_risk_sentence(
    airports: list[str],
    icao_map: dict[str, str],
    timeout: int,
    target: date | None = None,
    flights: list[CalendarEvent] | None = None,
) -> tuple[str, list[str], dict[str, dict]]:
    sentences: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, dict] = {}
    now = now_beijing()
    relevant_map = relevant_airport_times(flights or [])

    for airport in airports:
        icao = icao_map.get(airport, "")
        result = fetch_airport_weather(icao, timeout=timeout)
        relevant = relevant_map.get(airport, [])
        reference = relevant[0] if relevant else datetime.combine(target or now.date(), datetime.min.time(), tzinfo=now.tzinfo)
        relevant_utc = [value.astimezone(timezone.utc) for value in relevant]
        short = airport_with_suffix(airport)

        taf_period = parse_taf_validity(result.taf, reference)
        taf_covers = bool(
            taf_period
            and relevant_utc
            and any(taf_period[0] <= value <= taf_period[1] for value in relevant_utc)
        )

        metar_time = parse_metar_observation(result.metar, now)
        metar_relevant = bool(
            result.metar
            and metar_time
            and relevant_utc
            and min(abs((value - now.astimezone(timezone.utc)).total_seconds()) for value in relevant_utc) <= 6 * 3600
            and abs((now.astimezone(timezone.utc) - metar_time).total_seconds()) <= 3 * 3600
        )

        source = "OUTSIDE_VALID_WINDOW"
        decoded: list[str] = []
        if taf_covers:
            source = "TAF"
            decoded = decode_weather_report(result.taf)
            if decoded:
                sentences.append(short + "有效TAF提示" + "、".join(decoded[:4]) + "，最终以航前最新报文、放行资料及ATIS为准")
            else:
                sentences.append(short + "已取得覆盖航班时段的TAF，未识别出需特别提示的天气现象，最终以航前最新报文、放行资料及ATIS为准")
        elif metar_relevant:
            source = "METAR"
            decoded = decode_weather_report(result.metar)
            if decoded:
                sentences.append(short + "当前METAR显示" + "、".join(decoded[:4]) + "，最终以航前最新报文、放行资料及ATIS为准")
            else:
                sentences.append(short + "当前METAR未识别出需特别提示的天气现象，最终以航前最新报文、放行资料及ATIS为准")
        else:
            sentences.append(short + "尚未进入覆盖本次航班的有效预报时段，后续结合最新METAR、TAF、放行资料及ATIS持续更新")

        if result.error:
            warnings.append(f"{airport}天气获取提示：{result.error}")
        metadata[airport] = {
            "icao": icao,
            "source_used": source,
            "taf_validity_utc": [x.isoformat() for x in taf_period] if taf_period else [],
            "relevant_times": [x.isoformat() for x in relevant],
            "decoded": decoded,
            "fetch_error": result.error,
        }

    if metadata and all(item.get("source_used") == "OUTSIDE_VALID_WINDOW" for item in metadata.values()):
        names = "、".join(short_airport_name(airport) for airport in airports)
        combined = (
            f"本次航班尚未进入有效天气预报时段，后续结合{names}最新METAR、TAF、"
            "放行资料及ATIS持续更新。"
        )
        return combined, warnings, metadata

    return "；".join(sentences) + ("。" if sentences else ""), warnings, metadata

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
    """Return True for every airport chapter title in the airport manual.

    The manual uses many title shapes, for example:
    - 上海 / 浦东 机场运行特点
    - 济州机场运行特点 JIZHOU(CJU/RKPC)
    - 廊曼机场运行特点 BANGKOK（VTBD/DMK）
    - 仰光机场运行特点运行特点 YANGON

    Detection is therefore based on the Chinese chapter marker, not on a
    hard-coded airport list or one particular IATA/ICAO layout.
    """
    raw = normalize_text(line)
    key = compact_key(raw)
    suffix = compact_key(MANUAL_HEADER_SUFFIX)
    pos = key.find(suffix)
    if pos < 2 or pos > 40:
        return False
    if not 6 <= len(key) <= 120:
        return False
    if any(word in key for word in ("汇总", "威胁识别", "目录", "有效性完善", "安全问题的意识", "请机组积极")):
        return False
    # Real chapter titles are standalone labels. This excludes prose such as
    # “推进机场运行特点有效性完善性的建设，请机组……”.
    if any(mark in raw for mark in ("。", "，", "；", "：")):
        return False
    prefix = key[:pos]
    if not prefix or len(prefix) > 30:
        return False
    return True


def clean_header_airport_name(line: str) -> str:
    key = compact_key(line)
    suffix = compact_key(MANUAL_HEADER_SUFFIX)
    pos = key.find(suffix)
    if pos >= 0:
        key = key[:pos]
    key = key.replace("/", "")
    return key.removesuffix("国际机场").removesuffix("机场")


def _header_name_aliases(header: str) -> tuple[str, list[str], list[str]]:
    """Build generic strong/weak Chinese aliases from a chapter header."""
    key = compact_key(header)
    suffix = compact_key(MANUAL_HEADER_SUFFIX)
    pos = key.find(suffix)
    prefix = key[:pos] if pos >= 0 else key
    prefix = prefix.strip("/")

    parts = [p for p in prefix.split("/") if p]
    combined = "".join(parts) or prefix.replace("/", "")

    strong: set[str] = {combined}
    weak: set[str] = set()
    for value in list(strong):
        for ending in ("国际机场", "机场", "国际"):
            if value.endswith(ending) and len(value) > len(ending) + 1:
                strong.add(value[: -len(ending)])

    # Individual slash components are useful for schedules that show only the
    # city or only the airport name, but are treated as weak aliases so that
    # “成都” cannot silently choose between 双流 and 天府.
    for part in parts:
        cleaned = part.removesuffix("国际机场").removesuffix("机场").removesuffix("国际")
        if len(cleaned) >= 2 and cleaned not in strong:
            weak.add(cleaned)

    name_key = max(strong, key=len) if strong else combined
    return name_key, sorted(strong, key=len, reverse=True), sorted(weak, key=len, reverse=True)


def _extract_airport_codes(probe: str) -> tuple[str, str]:
    """Extract IATA/ICAO regardless of order or bracket width."""
    normalized = probe.upper().replace("（", "(").replace("）", ")").replace("／", "/")
    pairs = re.findall(r"(?<![A-Z0-9])([A-Z0-9]{3,4})\s*/\s*([A-Z0-9]{3,4})(?![A-Z0-9])", normalized)
    for left, right in pairs:
        if len(left) == 3 and len(right) == 4:
            return left, right
        if len(left) == 4 and len(right) == 3:
            return right, left
    # Fallback for OCR output where codes are separated rather than paired.
    tokens = re.findall(r"(?<![A-Z0-9])([A-Z]{3,4})(?![A-Z0-9])", normalized)
    iata = next((x for x in tokens if len(x) == 3), "")
    icao = next((x for x in tokens if len(x) == 4 and x not in {"ONLY", "WITH"}), "")
    return iata, icao


def build_manual_index(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headers = [i for i, line in enumerate(lines) if is_manual_airport_header(line)]
    sections: list[dict] = []
    for pos, start_idx in enumerate(headers):
        end_idx = headers[pos + 1] if pos + 1 < len(headers) else len(lines)
        header = lines[start_idx].strip()
        body_lines = lines[start_idx:end_idx]
        # Some international chapters put IATA/ICAO after the Chinese title;
        # others put it in the following few lines. Scan a wider but bounded
        # header area and infer code type by length, not by order.
        probe = "\n".join(body_lines[:24])
        iata, icao = _extract_airport_codes(probe)
        name_key, strong_aliases, weak_aliases = _header_name_aliases(header)
        sections.append(
            {
                "header": header,
                "name_key": name_key,
                "aliases": strong_aliases + weak_aliases,
                "strong_aliases": strong_aliases,
                "weak_aliases": weak_aliases,
                "iata": iata,
                "icao": icao,
                "lines": body_lines,
            }
        )
    return sections


def match_manual_section(index: list[dict], airport: str, icao: str) -> dict | None:
    """Match any airport generically; never special-case 济州 or another airport."""
    airport_key = compact_key(airport).replace("/", "")
    for ending in ("国际机场", "机场"):
        if airport_key.endswith(ending):
            airport_key = airport_key[: -len(ending)]
            break

    requested_icao = (icao or "").upper().strip()
    weak_frequency: dict[str, int] = {}
    for section in index:
        for alias in section.get("weak_aliases", []):
            weak_frequency[alias] = weak_frequency.get(alias, 0) + 1

    best: tuple[int, dict] | None = None
    for section in index:
        score = 0
        section_icao = str(section.get("icao", "")).upper()
        if requested_icao and section_icao == requested_icao:
            score += 2000

        name_key = str(section.get("name_key", ""))
        if airport_key == name_key:
            score += 1000
        elif airport_key and name_key and (airport_key in name_key or name_key in airport_key):
            score += 600 + min(len(airport_key), len(name_key))

        for alias in section.get("strong_aliases", []):
            if airport_key == alias:
                score += 800
            elif len(alias) >= 3 and (alias in airport_key or airport_key in alias):
                score += 350 + min(len(alias), len(airport_key))

        for alias in section.get("weak_aliases", []):
            # A weak city-only alias is accepted only when it uniquely identifies
            # one manual chapter. This prevents silent 成都/北京/上海 ambiguity.
            if weak_frequency.get(alias, 0) != 1:
                continue
            if airport_key == alias:
                score += 220
            elif len(alias) >= 3 and (alias in airport_key or airport_key in alias):
                score += 80 + min(len(alias), len(airport_key))

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



def flight_context_text(flights: list[CalendarEvent]) -> str:
    return "\n".join(
        normalize_text(f"{event.summary}\n{event.description}\n{event.location}").upper()
        for event in flights
    )


def context_has(context: str, *tokens: str) -> bool:
    upper = (context or "").upper()
    return any(token.upper() in upper for token in tokens)


def weather_has_operational_risk(weather_sentence: str) -> bool:
    return any(
        token in (weather_sentence or "")
        for token in ("雷暴", "雷雨", "阵雨", "大雨", "低云", "云底", "能见度", "雾", "风切变", "湿跑道")
    )


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
    *,
    detail: bool = False,
) -> list[str]:
    curated = CURATED_TYPICAL_INCIDENTS.get(canonical_airport_name(airport), [])
    limit = max_items if detail else min(max_items, 4)
    if curated:
        return curated[:limit]
    items = [
        professionalize_incident(x)
        for x in build_typical_items(risks, threats, month, max_items=max_items)
        if professionalize_incident(x)
    ]
    return items[:limit]


def overall_risk_items(
    airports: list[str],
    target: date,
    weather_sentence: str,
    *,
    detail: bool = False,
) -> list[str]:
    items: list[str] = []
    if any(is_airport(a, "上海浦东") for a in airports):
        if target >= PUDONG_2606_EFFECTIVE:
            if detail:
                items.append(
                    "浦东机场运行流量大，多跑道运行，地面滑行和空中进离场程序较为复杂；"
                    "2606期程序已经调整，应重点防范新旧程序混淆、跑道过渡选择错误和FMS数据输入错误。"
                )
            else:
                items.append(
                    "浦东2606期程序刚完成调整，应防范新旧程序混淆、跑道过渡选择错误及FMS输入错误。"
                )
        else:
            items.append("浦东机场运行流量大，多跑道运行，地面滑行和空中进离场程序较为复杂。")
    if any(is_airport(a, "丽江三义") for a in airports):
        items.append(
            "丽江为一般高原机场、复杂机场，周围地形复杂、进近剖面较陡，管制指挥可能造成下降偏晚、"
            "剖面偏高和构型建立偏晚。"
        )
        if 5 <= target.month <= 9:
            items.append(
                "丽江处于雨季，应重点关注降水、低云、风切变、湿跑道、顺风和着陆距离变化，"
                "提前完成性能评估并明确复飞、等待和备降预案。"
            )
    if 4 <= target.month <= 10:
        items.append(
            "航路及终端区可能涉及雷雨绕飞、直飞、雷达引导和高度变化，我们应加强频率守听、"
            "指令复诵和交叉证实，持续监控油量、航迹和最低安全高度。"
        )
    if weather_sentence:
        items.append(weather_sentence)
    return unique(items)[: (6 if detail else 5)]


def pudong_core_items(target: date, context: str = "", *, detail: bool = False) -> list[str]:
    items: list[str] = []
    if target >= PUDONG_2606_EFFECTIVE:
        base = (
            "浦东2606期飞行程序已经调整。航前应确认导航数据库处于有效周期，结合最新航图、"
            "航图勘误、NOTAM和放行资料核对进离场程序；PF和PM应交叉检查跑道过渡、离场公共段、"
            "第一航路点及高度速度限制，防止新旧程序或跑道选择混淆。"
        )
        if context_has(context, "PIKAS"):
            base += "本次资料涉及PIKAS时，应重点区分PIKAS-3与PIKAS-5。"
        if context_has(context, "BEKOK", "PINOT", "NUPLA", "TOSAS"):
            base += "本次航路涉及相关点位时，应确认BEKOK替代PINOT、NUPLA替代TOSAS。"
        items.append(base)

    items.append(
        "浦东空域内进离港航空器数量多，且可能受到虹桥航流影响。我们应严格执行高度、速度和航向指令，"
        "收到直飞、雷达引导或进近方式变化后重新评估剩余距离、下降剖面和减速需求；飞机未准备好时，"
        "不应急于接受过度内切或转向五边。"
    )
    items.append(
        "浦东地面运行环境复杂。收到滑行指令后应完整复诵，结合航图、地面标识、跑道状态灯和外部目视交叉检查；"
        "滑行期间避免两名飞行员同时低头。如使用FOLLOW GREEN，接近交叉道口应减速确认，绿灯中断、多方向亮起"
        "或与ATC指令不一致时，应停止滑行并向管制证实。"
    )
    if 5 <= target.month <= 9:
        items.append(
            "浦东夏季雷雨活动频繁，可能伴随低云低能见、湿跑道、风切变和鸟击风险。起飞前应结合天气雷达、"
            "放行资料、备降条件和剩余油量提前制定绕飞、等待或备降预案；天气趋势持续恶化时应尽早与AOC沟通。"
        )

    if detail:
        if target >= PUDONG_2606_EFFECTIVE:
            items.insert(
                1,
                "浦东16L、17R、34R、35L跑道部分VNAV、GP INOP及LNAV进近最低标准已调整，航前应使用最新有效标准；"
                "如执行VOR 17L或VOR 35R进近，应重点核对航图、导航数据库修正内容及相关高度限制。",
            )
        if context_has(context, "34R"):
            items.append(
                "本次资料涉及34R。执行34R盲降进近时，特定位置和高度可能因地面建筑物造成无线电高度跳变并触发TERRAIN警戒；"
                "我们应结合实际位置、高度、导航精度和飞机状态，严格按照当前有效操作通告处置并按要求报告。"
            )
        else:
            items.append(
                "条件性提示：如实际执行34R盲降进近，应在航前查阅当前有效操作通告，关注特定位置和高度可能发生的"
                "无线电高度跳变及TERRAIN警戒；未使用34R时不套用该特殊处置。"
            )
    return unique(items)


def lijiang_core_items(target: date, context: str = "", *, detail: bool = False) -> list[str]:
    items = [
        "丽江机场标高7358英尺，周围四面环山，东西两侧地形限制明显。我们应严格按照公布程序飞行，持续监控航迹、"
        "高度、最低安全高度和导航精度；雷达引导、直飞或天气绕飞时，应特别防范偏离程序后接近复杂地形。",
        "丽江进近可能出现下降偏晚和剖面偏高。我们应提前制定下降、减速和构型计划，结合剩余距离、顺风、地速和下降率"
        "及时向管制申请下降或减速，避免为追赶剖面使用过大下降率；结合下降剖面和速度条件，尽量在低于5700米后选择形态，"
        "如需在5700米以上放形态，严格按照当前运行要求执行信息报告。",
        "20号跑道相关进近下降梯度较大，五边还可能存在顺风。我们应提前建立着陆构型，持续监控下降率、速度趋势、推力状态"
        "和垂直偏差；未在规定高度达到稳定进近标准时，应果断复飞。",
    ]
    if 5 <= target.month <= 9:
        items.append(
            "丽江5月至9月处于雨季，应重点关注降水、低云、风切变、湿跑道和着陆距离。航前应根据跑道状况、风向风速、"
            "飞机重量和制动效应完成着陆性能评估，必要时考虑使用中档自动刹车，并明确复飞、等待或备降预案。"
        )
    if detail:
        items.append(
            "丽江进近区域实施ADS-B管制，GPS存在工作不稳定的可能。飞行中应监控GPS状态、导航精度、飞机位置和航迹变化；"
            "如出现GPS PRIMARY LOST、FM/GPS位置不一致或导航性能下降，应及时向ATC报告，并做好传统导航、非GPS进近及"
            "公司共同决策的准备。"
        )
        if context_has(context, "ILS INOP", "GS INOP", "盲降不工作", "盲降不可用", "下滑道不工作"):
            items.append(
                "本次资料提示盲降或下滑道不可用，应按照当前有效操作通告重新准备进近方式，核对FINAL APP、FDP限制高度、"
                "APPR及FMA方式；执行RNP 20时按要求设置DDA。"
            )
        else:
            items.append(
                "条件性提示：仅当NOTAM、放行资料或ATIS明确盲降/下滑道不可用时，才按当前有效丽江特殊操作通告准备RNP进近；"
                "设备正常时不固定套用该程序。"
            )
    return unique(items)


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


def airport_core_items(
    airport: str,
    source_items: list[str],
    target: date,
    context: str = "",
    *,
    detail: bool = False,
) -> list[str]:
    canonical = canonical_airport_name(airport)
    if canonical == "上海浦东":
        return pudong_core_items(target, context, detail=detail)
    if canonical == "丽江三义":
        return lijiang_core_items(target, context, detail=detail)
    return generic_core_items(source_items, target.month, max_items=6 if detail else 4)


def general_control_items(
    target: date,
    airports: list[str],
    weather_sentence: str,
    *,
    detail: bool = False,
) -> list[str]:
    thunderstorm_risk = 4 <= target.month <= 10 or weather_has_operational_risk(weather_sentence)
    items: list[str] = []
    if thunderstorm_risk:
        items.extend([
            "飞行中不得关闭气象雷达。应根据雷达型号和天气情况合理使用自动及人工模式；使用RDR-4B时不能仅依赖自动识别，"
            "应结合增益、倾斜角和人工扫描判断天气。",
            "云中绕飞与雷暴主体或强回波保持至少20海里；云外绕飞与积雨云保持至少6海里且与强回波保持至少20海里；"
            "云上飞越时与云顶保持至少1500米垂直间隔。低高度绕飞时，PM重点监控地形显示、MSA和地形间隔。",
        ])
    else:
        items.append("飞行中应根据实际天气合理使用气象雷达，并结合雷达型号按要求使用自动及人工模式。")

    items.append(
        "在光洁形态下放出形态前，PF确认当前高度低于FL200、进近阶段已经启用、速度处于管理方式且低于VFE NEXT；"
        "PM复核后喊话“高度检查，速度检查”，再操作襟翼手柄。严格遵守IAF点高度速度限制，最迟7海里放轮，"
        "并在1500英尺AAL前建立稳定状态。"
    )
    if any(is_airport(a, "上海浦东") for a in airports):
        items.append(
            "接近目标高度最后2000英尺时，如有邻近航空器，应合理限制升降率以降低TCAS告警风险；发生TA时及时检查和控制升降率，"
            "并严格按照现行程序处置。"
        )
    if weather_has_operational_risk(weather_sentence) or detail:
        items.append(
            "复飞决策一旦作出，应立即执行标准复飞动作，不得再次收油门尝试继续着陆。低高度复飞以内部仪表为主，"
            "严格监控姿态、速度、形态和正上升率；任何情况下使用反推后必须完成着陆全停。"
        )
    if detail:
        items.append("使用减速板后，如无超速风险应及时收回，防止影响后续能量管理；颠簸中避免与飞机对抗，优先恢复并保持自动驾驶。")
    return unique(items)[: (6 if detail else 5)]


def validate_content(
    content: str,
    flights: list[CalendarEvent],
    profile: dict,
    airports: list[str],
    *,
    detail: bool = False,
) -> list[str]:
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
    minimum = 1200 if detail else 700
    if len(content.strip()) < minimum:
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

        all_events = parse_ics(repo / "flight.ics")
        flights = [e for e in events_for_date(all_events, target) if e.is_flight and not e.is_positioning]
        if not flights:
            status = {
                "status": "NO_TASK",
                "target_date": target.isoformat(),
                "message": "目标日期未发现航班任务，未覆盖已有准备稿。",
                "version": VERSION,
            }
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
        context = flight_context_text(flights)

        weather_sentence = ""
        weather_meta: dict[str, dict] = {}
        warnings: list[str] = []
        if settings.get("include_weather_section", True):
            weather_sentence, weather_warnings, weather_meta = weather_risk_sentence(
                airports,
                icao_map,
                int(settings.get("weather_timeout_seconds", 20)),
                target=target,
                flights=flights,
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

        def build_content(*, detail: bool) -> str:
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

            risk_items = overall_risk_items(airports, target, weather_sentence, detail=detail)
            risk_lines = ["个人对本次航班中识别的风险："]
            risk_lines.extend(
                f"{idx}. {strip_terminal_punct(item)}。"
                for idx, item in enumerate(risk_items, start=1)
            )
            sections.append("\n".join(risk_lines))

            for airport in airports:
                typical_items = selected_typical_items(
                    airport,
                    risks.get(airport, []),
                    airport_threat_map.get(airport, []),
                    target.month,
                    max_items=max_items,
                    detail=detail,
                )
                risk_text = "\n".join(
                    f"{i}. {strip_terminal_punct(item)}。"
                    for i, item in enumerate(typical_items, start=1)
                )
                sections.append(f"{short_airport_name(airport)}机场典型不安全事件：\n{risk_text}")

            core_lines = ["核心威胁："]
            for airport in airports:
                items = airport_core_items(
                    airport,
                    airport_threat_map.get(airport, []),
                    target,
                    context,
                    detail=detail,
                )
                numbered = "\n".join(
                    f"{idx}. {strip_terminal_punct(item)}。"
                    for idx, item in enumerate(items, start=1)
                )
                core_lines.append(f"{short_airport_name(airport)}机场：\n{numbered}")
            sections.append("\n\n".join(core_lines))

            general_lines = ["航路及通用风险控制："]
            general_lines.extend(
                f"{idx}. {strip_terminal_punct(item)}。"
                for idx, item in enumerate(
                    general_control_items(target, airports, weather_sentence, detail=detail),
                    start=1,
                )
            )
            sections.append("\n".join(general_lines))
            return "\n\n".join(s.strip() for s in sections if s.strip()).strip() + "\n"

        group_content = build_content(detail=False)
        detail_content = build_content(detail=True)
        errors = [
            *validate_content(group_content, flights, profile, airports, detail=False),
            *["详细版：" + item for item in validate_content(detail_content, flights, profile, airports, detail=True)],
        ]
        if errors:
            status = {
                "status": "FAILED_SAFE",
                "target_date": target.isoformat(),
                "errors": errors,
                "version": VERSION,
                "note": "正式准备稿未覆盖。",
            }
            write_status(repo, status)
            append_github_summary("## 免费航前准备\n\n**FAILED_SAFE**：\n" + "\n".join(f"- {e}" for e in errors))
            return 2

        dated_group_name = f"{target.isoformat()}_航前准备.txt"
        dated_detail_name = f"{target.isoformat()}_航前准备_详细版.txt"
        atomic_write_text(output_dir / dated_group_name, group_content)
        atomic_write_text(output_dir / dated_detail_name, detail_content)
        atomic_write_text(output_dir / "latest.txt", group_content)
        atomic_write_text(output_dir / "latest_detail.txt", detail_content)
        atomic_write_json(
            output_dir / "latest_meta.json",
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "generated_at_beijing": now_beijing().isoformat(),
                "generator": VERSION,
                "flight_numbers": [e.flight_number for e in flights],
                "airports": airports,
                "group_output": dated_group_name,
                "detail_output": dated_detail_name,
                "warnings": unique(warnings),
                "weather": weather_meta,
                "airport_experience_changes": changes,
                "airport_information_file": manual_source,
                "airport_information_version": manual_ver,
            },
        )
        atomic_write_text(success_marker, "SUCCESS\n")
        write_status(
            repo,
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "group_output": str(output_dir / dated_group_name),
                "detail_output": str(output_dir / dated_detail_name),
                "version": VERSION,
            },
        )
        summary = (
            f"## {target.isoformat()} 航前准备（群发精简版）\n\n"
            f"```text\n{group_content}```\n\n"
            f"详细备查稿：`flight_preparation/{dated_detail_name}`"
        )
        if warnings:
            summary += "\n\n### 系统提示\n" + "\n".join(f"- {w}" for w in unique(warnings))
        append_github_summary(summary)
        print(f"SUCCESS: {output_dir / dated_group_name}")
        print(f"DETAIL: {output_dir / dated_detail_name}")
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
        append_github_summary(
            f"## 免费航前准备\n\n**FAILED_SAFE**：{type(exc).__name__}: {exc}\n\n原准备稿未覆盖。"
        )
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
