from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


REPO_ROOT = Path(__file__).resolve().parents[1]
BEIJING = ZoneInfo("Asia/Shanghai")
TARGET = date(2026, 8, 26)
REAL_PDF_CANDIDATES = sorted(
    (REPO_ROOT / "knowledge" / "pdf").glob(
        "*机场特点汇总(Airport Information)*.pdf"
    )
)
REAL_PDF = REAL_PDF_CANDIDATES[-1] if REAL_PDF_CANDIDATES else Path("missing.pdf")


def _event() -> CalendarEvent:
    return CalendarEvent(
        uid="fixed-output",
        summary="✈️ 9C8885 上海虹桥→贵阳龙洞堡",
        start=datetime(2026, 8, 26, 17, 5, tzinfo=BEIJING),
        end=datetime(2026, 8, 26, 19, 55, tzinfo=BEIJING),
        description=(
            "类型：航班\n航班：9C8885\n航线：上海虹桥 → 贵阳龙洞堡\n"
            "人员名单：\n• 段洋硕"
        ),
        location="上海虹桥",
        properties={},
        source_file="test.ics",
    )


def _profile() -> dict:
    return {
        "name": "段洋硕",
        "unit": "飞行十五中队",
        "role": "副驾驶",
        "technical_level": "A2",
        "promotion_date": "1月13日",
        "stage_hours": 75,
        "stage_landings": 12,
        "landings_90_days": 8,
        "recent_feedback": {
            "PF": "PF评价",
            "PM": "PM评价",
        },
    }


def _fact(
    fact_id: str,
    airport: str,
    text: str,
    *,
    category: str,
) -> agent.BilingualFact:
    return agent.BilingualFact(
        fact_id=fact_id,
        text_zh=text,
        text_en="Source fact.",
        airport=airport,
        source_file="knowledge/pdf/manual.pdf",
        source="PDF",
        source_page="1",
        source_heading=f"{airport}运行特点",
        source_section="典型不安全事件" if category == "typical" else "核心威胁",
        operational_phase="general",
        airport_specific=True,
        category=category,
        source_text_zh=text,
        source_fact_ids=(fact_id,),
        source_record_ids=(fact_id,),
        source_clauses=(text,),
        source_original_texts=(text,),
    )


def test_chinese_output_uses_fixed_five_part_order_and_numbered_events() -> None:
    event = _event()
    airports = list(event.route)
    typical = {
        airport: [_fact(f"{airport}-typical", airport, f"{airport}真实事件", category="typical")]
        for airport in airports
    }
    core = {
        airport: [_fact(f"{airport}-core", airport, f"{airport}核心事实", category="core")]
        for airport in airports
    }

    content = agent.render_chinese_briefing(
        event,
        TARGET,
        _profile(),
        [{"airport": airport, "within": True} for airport in airports],
        typical,
        core,
        "上海虹桥机场航班时段天气以航前最新TAF/METAR及放行资料为准。",
    )

    headings = [
        "上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）：",
        "个人对本次航班中识别的风险：",
        "上海虹桥机场典型不安全事件：",
        "贵阳龙洞堡机场典型不安全事件：",
        "核心威胁：",
    ]
    assert content.startswith("我是来自飞行十五中队的副驾驶段洋硕")
    assert [content.index(heading) for heading in headings] == sorted(
        content.index(heading) for heading in headings
    )
    assert "上海虹桥机场典型不安全事件：\n1. 上海虹桥真实事件。" in content
    assert "贵阳龙洞堡机场典型不安全事件：\n1. 贵阳龙洞堡真实事件。" in content
    assert content.count("核心威胁：") == 1
    assert "近期注意点" not in content
    assert not any(
        heading in content for heading in ("指挥特点：", "道面特点：", "气象特点：")
    )
    core_text = content.split("核心威胁：", 1)[1]
    assert not re.search(r"(?m)^\s*\d+[.、]", core_text)
    assert "我们应" not in content


def test_complete_source_original_allows_an_explicit_control_measure() -> None:
    fact = _fact(
        "source-original-control",
        "贵阳龙洞堡",
        "进近过程中注意航迹变化",
        category="core",
    )
    fact = replace(
        fact,
        source_text_zh="进近过程中存在航迹变化",
        source_clauses=("进近过程中存在航迹变化",),
        source_original_texts=("进近过程中存在航迹变化，注意航迹变化。",),
        mitigation=(),
        restriction=(),
    )

    assert agent.validate_source_semantic_preservation(fact) == []


def test_new_unsourced_measure_falls_back_to_pre_polish_text() -> None:
    fact = _fact(
        "unsourced-control",
        "贵阳龙洞堡",
        "雷暴风险，做好复飞预案",
        category="core",
    )
    fact = replace(
        fact,
        source_text_zh="雷暴风险",
        source_clauses=("雷暴风险",),
        source_original_texts=("雷暴风险。",),
        text_before_polish="雷暴风险",
        text_after_polish="雷暴风险，做好复飞预案",
    )
    diagnostics: list[dict[str, object]] = []

    resolved = agent.apply_source_guard_fallbacks([fact], diagnostics)

    assert [item.text_zh for item in resolved] == ["雷暴风险"]
    assert resolved[0].fallback_used == "text_before_polish"
    assert diagnostics[0]["guard_failed"] is True
    assert diagnostics[0]["paragraph_dropped"] is False


def test_unprovable_single_fact_is_dropped_without_discarding_safe_fact() -> None:
    safe = _fact("safe", "贵阳龙洞堡", "跑道存在坡度", category="core")
    unsafe = _fact("unsafe", "贵阳龙洞堡", "跑道存在坡度", category="core")
    unsafe = replace(
        unsafe,
        condition_scope=(("daypart", "night"),),
        text_before_polish="跑道存在坡度",
    )
    diagnostics: list[dict[str, object]] = []

    resolved = agent.apply_source_guard_fallbacks([safe, unsafe], diagnostics)

    assert [item.fact_id for item in resolved] == ["safe"]
    assert len(diagnostics) == 1
    assert diagnostics[0]["fact_id"] == "unsafe"
    assert diagnostics[0]["fallback_used"] == "dropped"
    assert diagnostics[0]["paragraph_dropped"] is True


def _copy_runtime_repo(destination: Path) -> None:
    (destination / "config").mkdir(parents=True)
    (destination / "knowledge" / "pdf").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "crew_calendar_main.py", destination)
    shutil.copy2(REPO_ROOT / "flight.ics", destination)
    for name in (
        "prep_settings.json",
        "pilot_profile.json",
        "airport_experience.json",
        "airport_supplements.json",
    ):
        shutil.copy2(REPO_ROOT / "config" / name, destination / "config" / name)
    settings_path = destination / "config" / "prep_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["auto_update_airport_experience"] = False
    settings["include_weather_section"] = False
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(
        REPO_ROOT / "knowledge" / "airport_information_20260615.txt",
        destination / "knowledge" / "airport_information_20260615.txt",
    )
    shutil.copy2(REAL_PDF, destination / "knowledge" / "pdf" / REAL_PDF.name)


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_real_august_twenty_six_generates_with_local_guard_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "august-26"
    _copy_runtime_repo(repo)
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", "2026-08-26"],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    content = (output / "latest.txt").read_text(encoding="utf-8")
    assert meta["status"] == "SUCCESS"
    assert meta["flight_numbers"] == ["9C8885", "9C8970"]
    assert (output / "2026-08-26_航前准备.txt").exists()
    assert "个人对本次航班中识别的风险：" in content
    assert "近期注意点" not in content
    assert all(airport in content for airport in ("上海虹桥机场：", "贵阳龙洞堡机场：", "扬州泰州机场："))
    for group in meta["prep_groups"]:
        group_content = (output / group["output"]).read_text(encoding="utf-8")
        assert group_content.count("核心威胁：") == 1
        assert "个人对本次航班中识别的风险：" in group_content
        risk_section = group_content.split(
            "个人对本次航班中识别的风险：", 1
        )[1].split("\n\n", 1)[0]
        for other_airport in set(meta["airports"]) - set(group["airports"]):
            assert agent.airport_with_suffix(other_airport) not in risk_section
        assert not re.search(r"(?m)^\s*\d+[.、]", group_content.split("核心威胁：", 1)[1])
        for airport in group["airports"]:
            title = f"{agent.airport_with_suffix(airport)}典型不安全事件："
            if title in group_content:
                section = group_content.split(title, 1)[1].split("\n\n", 1)[0]
                assert re.search(r"(?m)^1\.\s+\S", section)
    guiyang_outcomes = [
        item
        for item in meta.get("source_guard_outcomes", [])
        if item.get("fact_id") == "贵阳龙洞堡_core_record_14"
    ]
    assert all(item["guard_failed"] for item in guiyang_outcomes)
    assert all("source_original_text" in item for item in guiyang_outcomes)


@pytest.mark.parametrize("target_date", ["2026-08-14", "2026-08-18"])
@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_existing_august_regressions_still_generate(
    target_date: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / target_date
    _copy_runtime_repo(repo)
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda *args, **kwargs: SimpleNamespace(icao="", metar="", taf="", error=""),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["flight_prep_agent.py", "--repo", str(repo), "--target-date", target_date],
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0
    meta = json.loads(
        (repo / "flight_preparation" / "latest_meta.json").read_text(
            encoding="utf-8"
        )
    )
    assert meta["status"] == "SUCCESS"
    assert "个人对本次航班中识别的风险：" in (
        repo / "flight_preparation" / "latest.txt"
    ).read_text(encoding="utf-8")
