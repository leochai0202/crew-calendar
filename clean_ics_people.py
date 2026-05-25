import os
import re
from datetime import datetime, timedelta
from pathlib import Path

VERSION = "clean-ics-final-v5-fix-fake-cross-day-dtend"

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

KNOWN_FULL_NAMES = ["段洋硕"]
KNOWN_NAME_FRAGMENTS = {"段", "段洋", "洋硕", "硕"}

ROLE_RE = re.compile(r"\([A-Z0-9,，、\s\*]+\)")
VEVENT_RE = re.compile(r"BEGIN:VEVENT\s.*?END:VEVENT", re.S)


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

    # 正常航段跨日通常只有几小时。
    # 如果被写成 25、26 小时，基本就是整天 (+1) 污染。
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
    text = re.sub(r"\s{2,}", " ", text)
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


def remove_leading_known_fragment(token: str, existing_bases: set[str]) -> str:
    token = norm(token)

    if not token:
        return token

    for frag in sorted(KNOWN_NAME_FRAGMENTS, key=len, reverse=True):
        if not token.startswith(frag):
            continue

        candidate = token[len(frag):].strip()

        if not candidate:
            continue

        if looks_like_person_token(candidate):
            return candidate

        if base_name(candidate) in existing_bases:
            return candidate

    return token


def should_drop_person(token: str, existing_bases: set[str]) -> bool:
    token = norm(token)
    b = base_name(token)

    if not token or not b:
        return True

    if b in KNOWN_NAME_FRAGMENTS:
        return True

    for full in KNOWN_FULL_NAMES:
        if full in existing_bases and b in {full[:1], full[:2], full[1:], full[-1:]}:
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
    raw = [norm(p) for p in people if norm(p)]

    if not raw:
        return []

    bases_before = {base_name(x) for x in raw if base_name(x)}

    preliminary = []
    for token in raw:
        preliminary.append(remove_leading_known_fragment(token, bases_before))

    bases = {base_name(x) for x in preliminary if base_name(x)}

    if any(base_name(x) in KNOWN_NAME_FRAGMENTS for x in preliminary):
        if "段洋硕" not in bases:
            preliminary.append("段洋硕")
            bases.add("段洋硕")

    cleaned = []
    seen_exact = set()
    seen_base_with_role = set()

    for token in preliminary:
        token = norm(token)
        b = base_name(token)

        if should_drop_person(token, bases):
            continue

        if not has_role(token) and b in seen_base_with_role:
            continue

        if has_role(token):
            seen_base_with_role.add(b)

        if token not in seen_exact:
            cleaned.append(token)
            seen_exact.add(token)

    role_bases = {base_name(x) for x in cleaned if has_role(x)}
    final = []
    seen = set()

    for token in cleaned:
        b = base_name(token)

        if not has_role(token) and b in role_bases:
            continue

        if token not in seen:
            final.append(token)
            seen.add(token)

    return final


def clean_description_people(desc: str) -> str:
    lines = desc.split("\n")
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]
        out.append(line)

        if line.strip() != "人员名单：":
            i += 1
            continue

        i += 1
        people = []

        while i < len(lines):
            current = lines[i]
            stripped = current.strip()

            if not stripped:
                break

            if stripped.startswith("•"):
                people.append(stripped[1:].strip())
                i += 1
                continue

            if looks_like_person_token(stripped):
                people.append(stripped)
                i += 1
                continue

            break

        cleaned_people = clean_people_list(people)

        for p in cleaned_people:
            out.append(f"• {p}")

    return "\n".join(out)


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

    desc_escaped = get_line(block, "DESCRIPTION")
    if desc_escaped:
        desc = unescape_ics_text(desc_escaped)
        desc = remove_false_nextday_marks(desc, real_cross_day)
        desc = clean_description_people(desc)
        block = set_line(block, "DESCRIPTION", escape_ics_text(desc))

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
