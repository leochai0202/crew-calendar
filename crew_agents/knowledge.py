from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_airport_information_file(knowledge_dir: str | Path) -> Path | None:
    root = Path(knowledge_dir)
    candidates = sorted(
        [
            *root.glob("airport_information*.txt"),
            *root.glob("*机场特点*.txt"),
            *root.glob("AirDropManual*.txt"),
        ],
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def extract_relevant_chunks(
    text: str,
    terms: Iterable[str],
    *,
    window: int = 5000,
    max_chars: int = 24000,
) -> str:
    terms = [t.strip() for t in terms if t and t.strip()]
    if not text or not terms:
        return ""
    lowered = text.lower()
    ranges: list[tuple[int, int]] = []
    for term in sorted(set(terms), key=len, reverse=True):
        start = 0
        term_lower = term.lower()
        while True:
            idx = lowered.find(term_lower, start)
            if idx < 0:
                break
            ranges.append((max(0, idx - window // 3), min(len(text), idx + window)))
            start = idx + max(1, len(term_lower))
            if len(ranges) >= 30:
                break
        if len(ranges) >= 30:
            break

    if not ranges:
        return ""
    ranges.sort()
    merged: list[list[int]] = []
    for begin, end in ranges:
        if not merged or begin > merged[-1][1] + 200:
            merged.append([begin, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    chunks: list[str] = []
    used = 0
    for begin, end in merged:
        chunk = text[begin:end].strip()
        if not chunk:
            continue
        if "住宿酒店资源汇总" in chunk and not any(
            keyword in chunk for keyword in ("典型", "核心威胁", "运行特点", "跑道", "滑行", "进近")
        ):
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        chunk = chunk[:remaining]
        chunks.append(chunk)
        used += len(chunk)
    return "\n\n--- 相关资料分隔 ---\n\n".join(chunks)


def load_airport_supplements(path: str | Path, airports: Iterable[str]) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(_read_text(p))
    supplements = data.get("airports", data)
    result: dict = {}
    for requested in airports:
        for name, value in supplements.items():
            if name == requested or name in requested or requested in name:
                result[requested] = value
                break
    return result


def collect_airport_knowledge(
    knowledge_dir: str | Path,
    supplement_path: str | Path,
    airports: Iterable[str],
    icaos: Iterable[str],
) -> dict:
    airport_list = list(dict.fromkeys(a for a in airports if a))
    terms = [*airport_list, *[code for code in icaos if code]]
    source_file = find_airport_information_file(knowledge_dir)
    extracted = ""
    if source_file:
        extracted = extract_relevant_chunks(_read_text(source_file), terms)
    return {
        "source_file": str(source_file) if source_file else "",
        "manual_chunks": extracted,
        "supplements": load_airport_supplements(supplement_path, airport_list),
    }
