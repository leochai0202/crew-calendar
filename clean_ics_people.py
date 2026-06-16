import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VERSION = "clean-ics-final-v12-authoritative-scraped-dates"

ICS_FILES = [
    "crew_schedule.ics",
    "flight.ics",
    "positioning.ics",
    "training.ics",
    "ferry.ics",
    "other.ics",
    os.path.join("debug_output", "crew_schedule.ics"),
    os.path.join("debug_output", "flight.ics"),
    os.path.join("debug_output", "positioning.ics"),
    os.path.join("debug_output", "training.ics"),
    os.path.join("debug_output", "ferry.ics"),
    os.path.join("debug_output", "other.ics"),
]

KNOWN_FULL_NAME = "段洋硕"
KNOWN_NAME_FRAGMENTS = {"段", "段洋", "洋硕", "硕"}
ROLE_RE = re.compile(r"\([A-Z0-9,，、\s\*]+\)")
VEVENT_RE = re.compile(r"BEGIN:VEVENT\s.*?END:VEVENT", re.S)
ICS_PROP_RE = re.compile(
    r"^(BEGIN|END|VERSION|PRODID|UID|SUMMARY|DTSTART|DTEND|DESCRIPTION|LOCATION|TRIGGER|ACTION|X-CONTENT-SIGNATURE)(?:[;:]|$)"
)

# 已确认的历史多航段数据修复。
# 这些日期已经不在未来抓取范围内，必须在后处理阶段一次性纠正。
HISTORICAL_EVENT_FIXES = {
    ("20260611", "9C7355X"): {
        "reg": "B326R",
        "people": ["朱嘉(R)", "牛立强(R)", "段洋硕", "李扬1"],
    },
    ("20260611", "9C7004"): {
        "reg": "B8700",
        "people": ["张制(R)", "齐林一(R)", "唐进涛(R)", "许晓君", "邵康", "段洋硕", "张昊"],
    },
    ("20260614", "9C8677"): {
        "reg": "B8871",
        "people": ["钱超(T2,R)", "邹文松(R)", "黄亚林", "李林", "王健林", "段洋硕", "张亚辉"],
    },
    ("20260614", "9C7603X"): {
        "reg": "B8436",
        "people": ["王健林", "官亮", "段洋硕", "王兵"],
    },
    ("20260614", "9C7603Y"): {
        "reg": "B8436",
        "people": ["王健林", "官亮", "段洋硕", "沈烨"],
    },
    ("20260614", "9C7604X"): {
        "reg": "B8436",
        "people": ["王健林", "段洋硕", "官亮", "沈烨"],
    },
    ("20260615", "9C7603Y"): {
        "reg": "B306P",
        "people": ["王健林", "段伟(R)", "段洋硕(R)", "王兵"],
    },
    ("20260615", "9C7604X"): {
        "reg": "B306P",
        "people": ["王健林", "段伟(R)", "段洋硕(R)", "王兵"],
    },
    ("20260615", "9C7604Y"): {
        "reg": "B306P",
        "people": ["王健林", "段伟(R)", "段洋硕(R)", "王兵"],
    },
}


def norm(s: str) -> str:
    return (s or "").replace("\\,", ",").replace("\\;", ";").strip()


def escape_ics_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\n", r"\n")
    return text


def unescape_ics_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(r"\n", "\n")
    text = text.replace(r"\,", ",")
    text = text.replace(r"\;", ";")
    text = text.replace(r"\\", "\\")
    return text


def get_prop_value(block: str, key: str) -> str:
    m = re.search(rf"^{key}(?:;[^:]+)?:([^\n\r]*)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def get_prop_line(block: str, key: str) -> str:
    m = re.search(rf"^({key}(?:;[^:]+)?:[^\n\r]*)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def parse_dt_line(block: str, key: str):
    m = re.search(rf"^{key}(?:;[^:]+)?:([0-9]{{8}})T([0-9]{{6}})$", block, flags=re.M)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except Exception:
        return None


def set_dtend(block: str, new_dt: datetime) -> str:
    value = new_dt.strftime("%Y%m%dT%H%M%S")
    pattern = r"^(DTEND(?:;[^:]+)?):[0-9]{8}T[0-9]{6}$"
    return re.sub(pattern, lambda m: f"{m.group(1)}:{value}", block, flags=re.M)


def is_fake_cross_day(block: str) -> bool:
    start = parse_dt_line(block, "DTSTART")
    end = parse_dt_line(block, "DTEND")
    if not start or not end:
        return False
    if end.date() <= start.date():
        return False
    return (end - start) > timedelta(hours=12)


def event_is_real_cross_day(block: str) -> bool:
    start = parse_dt_line(block, "DTSTART")
    end = parse_dt_line(block, "DTEND")
    if not start or not end:
        return False
    if is_fake_cross_day(block):
        return False
    return end.date() > start.date()


def remove_false_nextday_marks(text: str, is_real_cross_day: bool) -> str:
    if is_real_cross_day:
        return text
    text = text.replace("(+1)", "").replace("（+1）", "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def base_name(name: str) -> str:
    name = norm(name)
    if name.startswith("•"):
        name = name[1:].strip()
    return ROLE_RE.sub("", name).strip()


def has_role(name: str) -> bool:
    return bool(ROLE_RE.search(norm(name)))


def looks_like_person_token(token: str) -> bool:
    token = norm(token)
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{1,8}[0-9A-Za-z]?(?:\([A-Z0-9,，、\s\*]+\))?", token))


def split_or_fix_person_token(token: str) -> list[str]:
    token = norm(token)
    if not token:
        return []

    if token.startswith("待调整"):
        rest = token[len("待调整"):].strip()
        if rest in KNOWN_NAME_FRAGMENTS or rest == KNOWN_FULL_NAME:
            return [KNOWN_FULL_NAME]
        return []

    b = base_name(token)
    if b == KNOWN_FULL_NAME:
        return [KNOWN_FULL_NAME]
    if b in KNOWN_NAME_FRAGMENTS:
        return [KNOWN_FULL_NAME]

    if token.startswith(KNOWN_FULL_NAME) and token != KNOWN_FULL_NAME:
        rest = token[len(KNOWN_FULL_NAME):].strip()
        out = [KNOWN_FULL_NAME]
        if rest and looks_like_person_token(rest):
            out.append(rest)
        return out

    for frag in sorted(KNOWN_NAME_FRAGMENTS, key=len, reverse=True):
        if token.startswith(frag) and len(token) > len(frag):
            rest = token[len(frag):].strip()
            rest_base = base_name(rest)
            if rest and rest_base not in KNOWN_NAME_FRAGMENTS and len(rest_base) >= 2 and looks_like_person_token(rest):
                return [rest]

    if KNOWN_FULL_NAME in token and token != KNOWN_FULL_NAME:
        left, right = token.split(KNOWN_FULL_NAME, 1)
        out = []
        if left and looks_like_person_token(left):
            out.append(left)
        out.append(KNOWN_FULL_NAME)
        if right and looks_like_person_token(right):
            out.append(right)
        return out

    if looks_like_person_token(token):
        return [token]

    return []


def should_drop_person(token: str) -> bool:
    b = base_name(token)
    if not b:
        return True
    if b in KNOWN_NAME_FRAGMENTS:
        return True
    if b.startswith("待调整"):
        return True
    if b in {"A319", "A320", "A321", "航班动态"}:
        return True
    if re.fullmatch(r"B[0-9A-Z]{3,6}", b):
        return True
    if re.fullmatch(r"9C\d{3,4}[A-Z]?", b):
        return True
    if "→" in b:
        return True
    return False


def clean_people_list(people: list[str]) -> list[str]:
    expanded = []
    for p in people:
        expanded.extend(split_or_fix_person_token(p))

    role_bases = {base_name(p) for p in expanded if has_role(p)}
    final = []
    seen = set()

    for p in expanded:
        p = norm(p)
        b = base_name(p)
        if should_drop_person(p):
            continue
        if not has_role(p) and b in role_bases:
            continue
        if p not in seen:
            final.append(p)
            seen.add(p)
    return final


def strip_embedded_ics_props(desc: str) -> str:
    """去掉早期坏清洗产生的嵌入式 LOCATION/BEGIN/VALARM/ACTION 等内容。"""
    lines = unescape_ics_text(desc).splitlines()
    kept = []
    for line in lines:
        s = line.strip()
        if ICS_PROP_RE.match(s):
            break
        if s.startswith("ACTION:DISPLAY"):
            break
        if s.startswith("END:VALARM") or s.startswith("BEGIN:VALARM"):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def normalize_description(desc: str) -> str:
    desc = strip_embedded_ics_props(desc)
    desc = re.sub(r"X-CONTENT-SIGNATURE:[0-9a-fA-F]+", "", desc)
    desc = re.sub(r"\s*人员名单：\s*", "\n\n人员名单：\n", desc)
    desc = re.sub(r"\s*版本：", "\n\n版本：", desc)
    desc = re.sub(r"\n{3,}", "\n\n", desc)
    return desc.strip()


def clean_description(desc: str, is_real_cross_day: bool) -> str:
    desc = normalize_description(desc)
    desc = remove_false_nextday_marks(desc, is_real_cross_day)

    lines = desc.splitlines()
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped != "人员名单：":
            out.append(line)
            i += 1
            continue

        out.append("人员名单：")
        i += 1
        people = []

        while i < len(lines):
            s = lines[i].strip()
            if not s:
                break
            if s.startswith("版本："):
                break
            if s.endswith("：") and s != "人员名单：":
                break
            if ICS_PROP_RE.match(s):
                break
            if s.startswith("•"):
                s = s[1:].strip()
            s = re.sub(r"\s*版本：.*$", "", s).strip()
            if s:
                people.append(s)
            i += 1

        for p in clean_people_list(people):
            out.append(f"• {p}")
        continue

    return "\n".join(out).strip()


def first_description_value(block: str) -> str:
    vals = re.findall(r"^DESCRIPTION(?:;[^:]+)?:([^\n\r]*)$", block, flags=re.M)
    if not vals:
        return ""
    # 第一个 DESCRIPTION 是事件描述；VALARM 里的 DESCRIPTION 不要拿来当事件描述。
    return vals[0].strip()


def alarm_description(summary: str) -> str:
    m = re.search(r"\b(9C\d{3,4}[A-Z]?)\b", summary or "")
    if m:
        return f"{m.group(1)} 签到提醒"
    s = re.sub(r"^[^\w\u4e00-\u9fff]+", "", summary or "").strip()
    return (s + " 签到提醒").strip() if s else "签到提醒"



def event_flight_no(summary: str) -> str:
    m = re.search(r"\b(9C\d{3,4}[A-Z]?)\b", summary or "")
    return m.group(1) if m else ""


def replace_description_reg(desc: str, reg: str) -> str:
    if not reg:
        return desc
    return re.sub(
        r"(机型：[^｜\n]+｜注册号：)\s*B[0-9A-Z]{3,6}",
        lambda m: m.group(1) + reg,
        desc,
        count=1,
    )


def replace_description_people(desc: str, people: list[str]) -> str:
    if not people or "人员名单：" not in desc:
        return desc

    lines = desc.splitlines()
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]
        out.append(line)

        if line.strip() != "人员名单：":
            i += 1
            continue

        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("•"):
                i += 1
                continue
            break

        out.extend([f"• {p}" for p in people])

    return "\n".join(out)


def apply_historical_event_fix(desc: str, start_dt, summary: str) -> str:
    if not start_dt:
        return desc

    key = (start_dt.strftime("%Y%m%d"), event_flight_no(summary))
    fix = HISTORICAL_EVENT_FIXES.get(key)
    if not fix:
        return desc

    desc = replace_description_reg(desc, fix.get("reg", ""))
    desc = replace_description_people(desc, fix.get("people", []))
    return desc


def rebuild_event(block: str) -> str:
    block = block.replace("\r\n", "\n").replace("\r", "\n")

    if is_fake_cross_day(block):
        end = parse_dt_line(block, "DTEND")
        if end:
            block = set_dtend(block, end - timedelta(days=1))

    real_cross_day = event_is_real_cross_day(block)

    uid = get_prop_value(block, "UID")
    summary = get_prop_value(block, "SUMMARY")
    summary = remove_false_nextday_marks(summary, real_cross_day)
    dtstart = get_prop_line(block, "DTSTART")
    dtend = get_prop_line(block, "DTEND")
    location = get_prop_value(block, "LOCATION")
    signature = get_prop_value(block, "X-CONTENT-SIGNATURE")

    desc_raw = first_description_value(block)
    desc = clean_description(desc_raw, real_cross_day)
    desc = apply_historical_event_fix(desc, parse_dt_line(block, "DTSTART"), summary)

    lines = ["BEGIN:VEVENT"]
    if uid:
        lines.append("UID:" + uid)
    if summary:
        lines.append("SUMMARY:" + summary)
    if dtstart:
        lines.append(dtstart)
    if dtend:
        lines.append(dtend)
    if desc:
        lines.append("DESCRIPTION:" + escape_ics_text(desc))
    if signature:
        lines.append("X-CONTENT-SIGNATURE:" + signature)
    if location:
        lines.append("LOCATION:" + escape_ics_text(unescape_ics_text(location)))
    lines.extend([
        "BEGIN:VALARM",
        "TRIGGER:-PT90M",
        "DESCRIPTION:" + escape_ics_text(alarm_description(summary)),
        "ACTION:DISPLAY",
        "END:VALARM",
        "END:VEVENT",
    ])
    return "\n".join(lines)


def split_calendar(text: str):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(VEVENT_RE.finditer(text))
    if not matches:
        return text, [], ""
    header = text[:matches[0].start()]
    events = [m.group(0) for m in matches]
    footer = text[matches[-1].end():]
    return header, events, footer


def event_start_dt(block: str):
    return parse_dt_line(block, "DTSTART")


def event_date_key(block: str):
    dt = event_start_dt(block)
    return dt.strftime("%Y%m%d") if dt else None


def event_uid(block: str) -> str:
    return get_prop_value(block, "UID")


def backup_path_for(path: str) -> str | None:
    p = Path(path)
    candidates = [str(p.with_name("backup_" + p.name))]
    if p.parent == Path(".") or str(p.parent) == "":
        candidates.append(str(Path("debug_output") / ("backup_" + p.name)))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def merge_history_text(path: str, current_text: str) -> tuple[str, int, int]:
    bpath = backup_path_for(path)
    if not bpath:
        return current_text, 0, 0
    try:
        backup_text = Path(bpath).read_text(encoding="utf-8")
    except Exception:
        return current_text, 0, 0

    current_text = current_text.replace("\r\n", "\n").replace("\r", "\n")
    backup_text = backup_text.replace("\r\n", "\n").replace("\r", "\n")

    cur_header, cur_events, cur_footer = split_calendar(current_text)
    bak_header, bak_events, bak_footer = split_calendar(backup_text)
    if not cur_events and not bak_events:
        return current_text, 0, 0

    current_dates = {event_date_key(e) for e in cur_events if event_date_key(e)}
    if not current_dates and bak_events:
        return backup_text, len(bak_events), 0

    kept_backup_events = []
    for e in bak_events:
        d = event_date_key(e)
        if d and d in current_dates:
            continue
        kept_backup_events.append(e)

    combined = kept_backup_events + cur_events

    dedup_reversed = []
    seen_uid = set()
    for e in reversed(combined):
        uid = event_uid(e)
        if uid and uid in seen_uid:
            continue
        if uid:
            seen_uid.add(uid)
        dedup_reversed.append(e)
    combined = list(reversed(dedup_reversed))
    combined.sort(key=lambda e: event_start_dt(e) or datetime.max)

    header = cur_header or bak_header or "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Crew Calendar//CN\n"
    footer = cur_footer if "END:VCALENDAR" in cur_footer else bak_footer
    if not footer.strip().endswith("END:VCALENDAR"):
        footer = "\nEND:VCALENDAR\n"

    merged = header.rstrip("\n") + "\n" + "\n".join(combined) + "\n" + footer.lstrip("\n")
    return merged, max(0, len(combined) - len(cur_events)), len(current_dates)



def load_scraped_dates() -> set[str]:
    candidates = [
        Path("debug_output/scraped_dates.txt"),
        Path("scraped_dates.txt"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        dates = {
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if re.fullmatch(r"\d{8}", line.strip())
        }
        if dates:
            return dates
    return set()


def build_calendar_text(header: str, events: list[str], footer: str) -> str:
    if not header.strip():
        header = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Crew Calendar//CN\n"
    if not footer.strip().endswith("END:VCALENDAR"):
        footer = "\nEND:VCALENDAR\n"
    body = "\n".join(events)
    return header.rstrip("\n") + "\n" + body + "\n" + footer.lstrip("\n")


def dedup_and_sort_events(events: list[str]) -> list[str]:
    # 后出现的事件优先，确保本次抓取覆盖历史同 UID 事件。
    kept_reversed = []
    seen_uid = set()
    for event in reversed(events):
        uid = event_uid(event)
        if uid and uid in seen_uid:
            continue
        if uid:
            seen_uid.add(uid)
        kept_reversed.append(event)
    result = list(reversed(kept_reversed))
    result.sort(key=lambda e: event_start_dt(e) or datetime.max)
    return result


def sync_root_from_current_debug(path: str, scraped_dates: set[str]) -> tuple[bool, int, int]:
    """
    以主程序本次写入 debug_output/<日历文件> 的事件为权威数据：
    - 根目录日历中，本次抓到日期的旧事件全部删除；
    - 再加入本次对应分类的新事件；
    - 其他历史日期保持不动。

    这样任务从“航班”改为“置位”时，不会被 backup 历史重新塞回 flight.ics。
    """
    if not scraped_dates or Path(path).parent != Path("."):
        return False, 0, 0

    root_path = Path(path)
    debug_path = Path("debug_output") / root_path.name
    if not root_path.exists() or not debug_path.exists():
        return False, 0, 0

    root_text = root_path.read_text(encoding="utf-8", errors="replace")
    debug_text = debug_path.read_text(encoding="utf-8", errors="replace")
    root_header, root_events, root_footer = split_calendar(root_text)
    _, debug_events, _ = split_calendar(debug_text)

    kept_history = [
        event for event in root_events
        if event_date_key(event) not in scraped_dates
    ]
    current_events = [
        event for event in debug_events
        if event_date_key(event) in scraped_dates
    ]

    removed = len(root_events) - len(kept_history)
    combined = dedup_and_sort_events(kept_history + current_events)
    new_text = normalize_ics_newlines(
        build_calendar_text(root_header, combined, root_footer)
    )
    old_text = normalize_ics_newlines(root_text)

    if new_text != old_text:
        root_path.write_text(new_text, encoding="utf-8", newline="")
        return True, removed, len(current_events)
    return False, removed, len(current_events)

def normalize_ics_newlines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r\n")


def clean_file(path: str) -> tuple[bool, int]:
    if not os.path.exists(path):
        return False, 0

    text = Path(path).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 主程序已负责保留历史；清洗器不再从 backup 合并，避免把本次已改分类/删除的任务重新引入。
    header, blocks, footer = split_calendar(text)
    if not blocks:
        return False, 0

    rebuilt_blocks = []
    changed_count = 0
    for block in blocks:
        rebuilt = rebuild_event(block)
        if rebuilt != block:
            changed_count += 1
        rebuilt_blocks.append(rebuilt)

    new_text = header.rstrip("\n") + "\n" + "\n".join(rebuilt_blocks) + "\n" + footer.lstrip("\n")
    new_text = normalize_ics_newlines(new_text)
    old_text_for_compare = normalize_ics_newlines(text)

    if new_text != old_text_for_compare:
        Path(path).write_text(new_text, encoding="utf-8", newline="")
        return True, changed_count
    return False, changed_count


def main():
    os.makedirs("debug_output", exist_ok=True)
    log_lines = [f"代码版本: {VERSION}"]

    scraped_dates = load_scraped_dates()
    if scraped_dates:
        log_lines.append("本次权威日期: " + ",".join(sorted(scraped_dates)))
        for name in ["crew_schedule.ics", "flight.ics", "positioning.ics", "training.ics", "ferry.ics", "other.ics"]:
            changed, removed, added = sync_root_from_current_debug(name, scraped_dates)
            log_lines.append(
                f"分类同步 {name}: changed={changed} removed={removed} added={added}"
            )
    else:
        log_lines.append("未找到 scraped_dates.txt，跳过分类同步")

    total_changed_files = 0
    total_changed_events = 0
    for path in ICS_FILES:
        changed, count = clean_file(path)
        if changed:
            total_changed_files += 1
            total_changed_events += count
            log_lines.append(f"已清理 {path}: {count} 个事件")
        else:
            log_lines.append(f"无需清理 {path}")
    log_lines.append(f"清理完成: files={total_changed_files}, events={total_changed_events}")
    Path("debug_output/clean_ics_people.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
