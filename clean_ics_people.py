import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VERSION = "clean-ics-final-v9-merge-history-and-apple-valid"

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

# 只抓 DESCRIPTION 到下一个 ICS 属性前，不吃掉下一个属性。
DESC_SECTION_RE = re.compile(
    r"(^DESCRIPTION:)(.*?)(?=\r?\n(?:X-CONTENT-SIGNATURE:|LOCATION:|BEGIN:VALARM|ACTION:|TRIGGER:|END:VALARM|END:VEVENT))",
    re.S | re.M,
)

ICS_PROP_RE = re.compile(
    r"^(BEGIN|END|VERSION|PRODID|UID|SUMMARY|DTSTART|DTEND|DESCRIPTION|LOCATION|TRIGGER|ACTION|X-CONTENT-SIGNATURE)(?:[;:]|$)",
    re.M,
)


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


def get_line(block: str, key: str) -> str:
    m = re.search(rf"^{key}(?:;[^:]+)?:([^\n\r]*)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def set_line(block: str, key: str, value: str) -> str:
    pattern = rf"^{key}(?:;[^:]+)?:[^\n\r]*$"
    repl = f"{key}:{value}"
    if re.search(pattern, block, flags=re.M):
        return re.sub(pattern, repl, block, flags=re.M)
    return block


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
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{1,8}[0-9]?(?:\([A-Z0-9,，、\s\*]+\))?", token))


def split_or_fix_person_token(token: str) -> list[str]:
    token = norm(token)
    if not token:
        return []

    # 处理“待调整段”这种原始页面把自己位置写成待调整+姓名碎片的情况。
    if token.startswith("待调整"):
        rest = token[len("待调整"):].strip()
        if rest in KNOWN_NAME_FRAGMENTS or rest == KNOWN_FULL_NAME:
            return [KNOWN_FULL_NAME]
        return []

    b = base_name(token)
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
            if rest and looks_like_person_token(rest):
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


def normalize_description(desc: str) -> str:
    desc = unescape_ics_text(desc)
    # 修复 v7 产生的“版本：...X-CONTENT-SIGNATURE”黏连，先把签名属性剥离掉，后面事件块里已有真正属性。
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

        cleaned_people = clean_people_list(people)
        for p in cleaned_people:
            out.append(f"• {p}")
        continue

    return "\n".join(out).strip()


def clean_description_sections(block: str, is_real_cross_day: bool) -> str:
    def repl(m):
        prefix = m.group(1)
        desc = m.group(2)
        cleaned = clean_description(desc, is_real_cross_day)
        return prefix + escape_ics_text(cleaned)
    return DESC_SECTION_RE.sub(repl, block)


def clean_event(block: str) -> str:
    if is_fake_cross_day(block):
        end = parse_dt_line(block, "DTEND")
        if end:
            block = set_dtend(block, end - timedelta(days=1))

    real_cross_day = event_is_real_cross_day(block)

    summary = get_line(block, "SUMMARY")
    if summary:
        block = set_line(block, "SUMMARY", remove_false_nextday_marks(summary, real_cross_day))

    block = clean_description_sections(block, real_cross_day)
    return block



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
    if not dt:
        return None
    return dt.strftime("%Y%m%d")


def event_uid(block: str) -> str:
    m = re.search(r"^UID:([^\n\r]*)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def backup_path_for(path: str) -> str | None:
    p = Path(path)
    candidates = []

    # debug_output/flight.ics -> debug_output/backup_flight.ics
    candidates.append(str(p.with_name("backup_" + p.name)))

    # root flight.ics -> debug_output/backup_flight.ics
    if p.parent == Path(".") or str(p.parent) == "":
        candidates.append(str(Path("debug_output") / ("backup_" + p.name)))

    for c in candidates:
        if os.path.exists(c):
            return c

    return None


def merge_history_text(path: str, current_text: str) -> tuple[str, int, int]:
    """
    主程序有时只输出本次网页抓到的日期，导致旧月份/旧日期从订阅日历消失。
    这里用 main 运行前自动备份的 backup_*.ics 做历史合并：
    - 当前文件里出现的日期：以当前文件为准，替换旧历史
    - 当前文件里没出现的日期：从 backup 保留
    """
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

    # 当前没有任何有效日期时，保守使用 backup，避免清空日历。
    if not current_dates and bak_events:
        return backup_text, len(bak_events), 0

    kept_backup_events = []
    for e in bak_events:
        d = event_date_key(e)
        if d and d in current_dates:
            continue
        kept_backup_events.append(e)

    combined = kept_backup_events + cur_events

    # 去重：如果 UID 重复，优先保留靠后的 current 版本。
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

    def sort_key(e: str):
        dt = event_start_dt(e)
        return dt or datetime.max

    combined.sort(key=sort_key)

    header = cur_header or bak_header or "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Crew Calendar//CN\n"
    footer = cur_footer if "END:VCALENDAR" in cur_footer else bak_footer
    if not footer.strip().endswith("END:VCALENDAR"):
        footer = "\nEND:VCALENDAR\n"

    merged = header.rstrip("\n") + "\n" + "\n".join(combined) + "\n" + footer.lstrip("\n")
    added = max(0, len(combined) - len(cur_events))
    replaced_dates = len(current_dates)
    return merged, added, replaced_dates


def normalize_ics_newlines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r\n")


def clean_file(path: str) -> tuple[bool, int]:
    if not os.path.exists(path):
        return False, 0

    text = Path(path).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 先合并历史，防止本次只抓到未来几天时把旧任务清空。
    text_after_merge, history_added, replaced_dates = merge_history_text(path, text)
    text_after_merge = text_after_merge.replace("\r\n", "\n").replace("\r", "\n")

    blocks = VEVENT_RE.findall(text_after_merge)
    if not blocks:
        return False, 0

    new_text = text_after_merge
    changed_count = history_added

    for block in blocks:
        cleaned = clean_event(block)
        if cleaned != block:
            changed_count += 1
            new_text = new_text.replace(block, cleaned, 1)

    new_text = normalize_ics_newlines(new_text)
    old_text_for_compare = normalize_ics_newlines(text)

    if new_text != old_text_for_compare:
        Path(path).write_text(new_text, encoding="utf-8", newline="")
        return True, changed_count

    return False, changed_count


def main():
    os.makedirs("debug_output", exist_ok=True)
    log_lines = [f"代码版本: {VERSION}"]
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
