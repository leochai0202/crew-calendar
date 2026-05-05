import os
import re
import zipfile
from pathlib import Path

ZIP_NAME = "debug-output 2(3).zip"

ICS_FILES = [
    "crew_schedule.ics",
    "training.ics",
    "flight.ics",
    "positioning.ics",
    "ferry.ics",
    "other.ics",
]


def extract_uid(block: str) -> str:
    m = re.search(r"^UID:(.+)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def extract_dtstart(block: str) -> str:
    m = re.search(r"^DTSTART(?:;[^:]+)?:([0-9T]+)$", block, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def extract_dtend(block: str) -> str:
    m = re.search(r"^DTEND(?:;[^:]+)?:([0-9T]+)$", block, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def extract_summary(block: str) -> str:
    m = re.search(r"^SUMMARY:(.+)$", block, flags=re.M)
    return m.group(1).strip() if m else ""


def read_ics_blocks_from_text(text: str) -> list[str]:
    return re.findall(r"BEGIN:VEVENT.*?END:VEVENT", text, flags=re.S)


def read_ics_blocks_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return read_ics_blocks_from_text(text)


def read_ics_blocks_from_zip(zip_path: Path, member_name: str) -> list[str]:
    if not zip_path.exists():
        return []
    with zipfile.ZipFile(zip_path, "r") as zf:
        if member_name not in zf.namelist():
            return []
        text = zf.read(member_name).decode("utf-8", errors="ignore")
    return read_ics_blocks_from_text(text)


def block_quality(block: str) -> int:
    score = 0
    summary = extract_summary(block)
    if summary:
        score += len(summary)

    if "航线：" in block:
        score += 20
    if "签到：" in block:
        score += 20
    if "地点：" in block:
        score += 15
    if "机型：" in block:
        score += 10
    if "注册号：" in block:
        score += 10
    if "人员名单：" in block:
        score += 15
    if "版本：" in block:
        score += 5

    return score


def similarity_key(block: str) -> tuple[str, str, str]:
    return (
        extract_dtstart(block),
        extract_dtend(block),
        extract_summary(block).replace(" ", ""),
    )


def merge_blocks(backup_blocks: list[str], current_blocks: list[str]) -> list[str]:
    merged_by_uid: dict[str, str] = {}

    for block in backup_blocks + current_blocks:
        uid = extract_uid(block)
        if not uid:
            continue
        if uid not in merged_by_uid:
            merged_by_uid[uid] = block
        else:
            if block_quality(block) > block_quality(merged_by_uid[uid]):
                merged_by_uid[uid] = block

    grouped: dict[tuple[str, str, str], str] = {}
    for block in merged_by_uid.values():
        key = similarity_key(block)
        if key not in grouped:
            grouped[key] = block
        else:
            if block_quality(block) > block_quality(grouped[key]):
                grouped[key] = block

    result = list(grouped.values())
    result.sort(key=lambda b: (extract_dtstart(b), extract_uid(b)))
    return result


def write_ics(path: Path, blocks: list[str]):
    content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Crew Calendar//CN",
        *blocks,
        "END:VCALENDAR",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def main():
    root = Path(".")
    zip_path = root / ZIP_NAME

    if not zip_path.exists():
        raise FileNotFoundError(f"没找到 {ZIP_NAME}")

    for ics_name in ICS_FILES:
        backup_name = f"backup_{ics_name}"

        backup_blocks = read_ics_blocks_from_zip(zip_path, backup_name)
        current_blocks = read_ics_blocks_from_file(root / ics_name)

        merged = merge_blocks(backup_blocks, current_blocks)
        write_ics(root / ics_name, merged)

        print(
            f"{ics_name}: backup={len(backup_blocks)} current={len(current_blocks)} merged={len(merged)}"
        )

    print("恢复完成：历史任务已尽量从 backup 合并回正式 ICS。")


if __name__ == "__main__":
    main()
