import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VERSION = "clean-ics-final-v6-fix-description-people-block"

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

DESC_SECTION_RE = re.compile(
    r"(^DESCRIPTION:)(.*?)(?=^(?:X-CONTENT-SIGNATURE:|LOCATION:|BEGIN:VALARM|ACTION:|END:VALARM|END:VEVENT))",
    re.S | re.M,
)


def norm(s: str) -> str:
    return (s or "").replace("\\,", ",").replace("\\;", ";").strip()


def escape_ics_text(text: str) -> str:
    text = text or ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\n", r"\n")
    return text


def unescape_ics_text(text: str) -> str:
    text = text or ""
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

    def repl(m):
        return f"{m.group(1)}:{value}"

    return re.sub(pattern, repl, block, flags=re.M)


def is_fake_cross_day(block: str) -> bool:
    start = parse_dt_line(block, "DTSTART")
    end = parse_dt_line(block, "DTEND")

    if not start or not end:
        return False

    if end.date() <= start.date():
        return False

    duration = end - start

    # 正常跨日航段通常只有几小时。
    # 如果因为整天污染被写成 25 小时、26 小时，判定为假跨日。
    return duration > timedelta(hours=12)


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

    text = text.replace("(+1)", "")
    text = text.replace("（+1）", "")
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

    return bool(
        re.fullmatch(
            r"[\u4e00-\u9fff]{1,8}[0-9]?(?:\([A-Z0-9,，、\s\*]+\))?",
            token,
        )
    )


def split_or_fix_person_token(token: str) -> list[str]:
    token = norm(token)

    if not token:
        return []

    b = base_name(token)

    # “段 / 段洋 / 洋硕 / 硕”这类半截，恢复为完整姓名
    if b in KNOWN_NAME_FRAGMENTS:
        return [KNOWN_FULL_NAME]

    # “段洋硕朱天扬(R)”这类黏连
    if token.startswith(KNOWN_FULL_NAME) and token != KNOWN_FULL_NAME:
        rest = token[len(KNOWN_FULL_NAME):].strip()
        out = [KNOWN_FULL_NAME]

        if rest and looks_like_person_token(rest):
            out.append(rest)

        return out

    # “洋硕林峰(R)” / “硕朱天扬(R)”这类前面黏了姓名尾巴
    for frag in sorted(KNOWN_NAME_FRAGMENTS, key=len, reverse=True):
        if not token.startswith(frag):
            continue

        if len(token) <= len(frag):
            continue

        rest = token[len(frag):].strip()

        if rest and looks_like_person_token(rest):
            return [rest]

    # 中间包含完整姓名
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

        # 如果已有“朱天扬(R)”，则不要再保留无角色的“朱天扬”
        if not has_role(p) and b in role_bases:
            continue

        if p not in seen:
            final.append(p)
            seen.add(p)

    return final


def normalize_description(desc: str) -> str:
    desc = unescape_ics_text(desc)

    # 把“机型：A320｜注册号：B8581 人员名单：”拆开
    desc = re.sub(r"\s*人员名单：\s*", "\n\n人员名单：\n", desc)

    # 把“汤慧君 版本：2026...”拆开
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
            current = lines[i]
            s = current.strip()

            if not s:
                break

            if s.startswith("版本："):
                break

            if s.endswith("：") and s != "人员名单：":
                break

            if s.startswith("•"):
                s = s[1:].strip()

            # 防止“某某 版本：...”残留
            s = re.sub(r"\s*版本：.*$", "", s).strip()

            if s:
                people.append(s)

            i += 1

        cleaned_people = clean_people_list(people)

        for p in cleaned_people:
            out.append(f"• {p}")

        continue

    return "\n".join(out).strip() + "\n"


def clean_description_sections(block: str, is_real_cross_day: bool) -> str:
    def repl(m):
        prefix = m.group(1)
        desc = m.group(2)
        cleaned = clean_description(desc, is_real_cross_day)
        return prefix + escape_ics_text(cleaned)

    return DESC_SECTION_RE.sub(repl, block)


def clean_event(block: str) -> str:
    fake_cross_day = is_fake_cross_day(block)

    if fake_cross_day:
        end = parse_dt_line(block, "DTEND")

        if end:
            block = set_dtend(block, end - timedelta(days=1))

    real_cross_day = event_is_real_cross_day(block)

    summary = get_line(block, "SUMMARY")

    if summary:
        block = set_line(
            block,
            "SUMMARY",
            remove_false_nextday_marks(summary, real_cross_day),
        )

    block = clean_description_sections(block, real_cross_day)

    return block


def clean_file(path: str) -> tuple[bool, int]:
    if not os.path.exists(path):
        return False, 0

    text = Path(path).read_text(encoding="utf-8")
    blocks = VEVENT_RE.findall(text)

    if not blocks:
        return False, 0

    new_text = text
    changed_count = 0

    for block in blocks:
        cleaned = clean_event(block)

        if cleaned != block:
            changed_count += 1
            new_text = new_text.replace(block, cleaned, 1)

    if new_text != text:
        Path(path).write_text(new_text, encoding="utf-8")
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

    log_lines.append(
        f"清理完成: files={total_changed_files}, events={total_changed_events}"
    )

    Path("debug_output/clean_ics_people.log").write_text(
        "\n".join(log_lines),
        encoding="utf-8",
    )

    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
