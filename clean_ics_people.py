import os
import re
from pathlib import Path

# 后处理 ICS 人员名单：只清理明显串读/半截，不删除带数字的真实姓名（如王磊1）
# 目的：避免 main 里偶发把“段洋硕朱天扬(R)”拆成“段洋 / 硕朱天扬(R)”这类脏名单。

KNOWN_PEOPLE = ["段洋硕"]
ROLE_RE = re.compile(r"\([A-Z0-9,，*]+\)")
DESC_RE = re.compile(r"^(DESCRIPTION:)(.*)$", re.M)

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


def norm(s: str) -> str:
    return (s or "").replace("\\,", ",").replace("\\;", ";").strip()


def base_name(name: str) -> str:
    name = norm(name)
    if name.startswith("•"):
        name = name[1:].strip()
    return ROLE_RE.sub("", name).strip()


def has_role(name: str) -> bool:
    return bool(ROLE_RE.search(norm(name)))


def clean_people_list(people: list[str]) -> list[str]:
    # people items do not include bullet prefix here.
    raw = [norm(p) for p in people if norm(p)]
    bases = {base_name(p) for p in raw if base_name(p)}

    cleaned = []
    for p in raw:
        b = base_name(p)
        if not b:
            continue

        # 1) 已有完整本人姓名时，删除被切碎的半截：段洋 / 洋硕 / 段等
        is_partial_known = False
        for known in KNOWN_PEOPLE:
            if known in bases and b != known:
                if b in {known[:1], known[:2], known[1:], known[-1:]} or known.startswith(b):
                    is_partial_known = True
                    break
        if is_partial_known:
            continue

        # 2) 删除跨边界串读：如“硕朱天扬(R)”，如果“朱天扬(R)”也存在，则删前者。
        #    这里不按具体姓名写死，只要去掉第一个字后是另一个已存在姓名，就认为是边界串读。
        if len(b) >= 3 and b[1:] in bases:
            continue

        # 3) 删除“已知姓名最后一个字 + 另一个姓名”的串读：如 段洋硕 + 朱天扬 -> 硕朱天扬
        boundary_dirty = False
        for known in KNOWN_PEOPLE:
            if known in bases and b.startswith(known[-1]) and b[1:] in bases:
                boundary_dirty = True
                break
        if boundary_dirty:
            continue

        cleaned.append(p)

    # 4) 如果同时有带角色和不带角色的同一个人，优先保留带角色版本。
    role_bases = {base_name(p) for p in cleaned if has_role(p)}
    out = []
    seen = set()
    for p in cleaned:
        b = base_name(p)
        if b in role_bases and not has_role(p):
            continue
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def clean_description(desc: str) -> str:
    parts = desc.split(r"\n")
    out = []
    i = 0
    changed = False

    while i < len(parts):
        line = parts[i]
        out.append(line)

        if norm(line) == "人员名单：":
            i += 1
            people = []
            # 采集后续 bullet 行
            while i < len(parts):
                cur = parts[i]
                cur_norm = norm(cur)
                if cur_norm.startswith("•"):
                    people.append(cur_norm[1:].strip())
                    i += 1
                    continue
                break

            cleaned = clean_people_list(people)
            if cleaned != people:
                changed = True
            out.extend(["• " + p for p in cleaned])
            continue

        i += 1

    return r"\n".join(out) if changed else desc


def process_file(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")

    changed = False

    def repl(m: re.Match) -> str:
        nonlocal changed
        prefix, desc = m.group(1), m.group(2)
        new_desc = clean_description(desc)
        if new_desc != desc:
            changed = True
        return prefix + new_desc

    new_text = DESC_RE.sub(repl, text)
    if changed and new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main():
    changed_files = []
    for filename in ICS_FILES:
        p = Path(filename)
        if process_file(p):
            changed_files.append(filename)

    os.makedirs("debug_output", exist_ok=True)
    Path("debug_output/people_cleanup_postprocess.txt").write_text(
        "people-cleanup-postprocess-v1\n" + "\n".join(changed_files),
        encoding="utf-8",
    )

    if changed_files:
        print("Cleaned people lists in:")
        for f in changed_files:
            print("-", f)
    else:
        print("No people-list cleanup needed.")


if __name__ == "__main__":
    main()
