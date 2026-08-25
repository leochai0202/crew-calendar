from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from crew_agents import flight_prep_agent as agent


REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_PDF_CANDIDATES = sorted(
    (REPO_ROOT / "knowledge" / "pdf").glob(
        "*机场特点汇总(Airport Information)*.pdf"
    )
)
REAL_PDF = REAL_PDF_CANDIDATES[-1] if REAL_PDF_CANDIDATES else Path("missing.pdf")
REAL_PDF_VERSION = agent.manual_version(REAL_PDF) if REAL_PDF.exists() else 0
REAL_TARGET_DATE = "2026-07-08"
REAL_FLIGHT_NUMBER = "9C7165"
REAL_DEPARTURE = "上海浦东"
REAL_ARRIVAL = "西宁曹家堡"
KEY_AIRPORTS = (REAL_DEPARTURE, REAL_ARRIVAL)


def test_pdf_20260720_outranks_txt_20260615(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    pdf_dir = knowledge / "pdf"
    pdf_dir.mkdir(parents=True)
    (knowledge / "airport_information_20260615.txt").write_text(
        "版本号 20260615\n上海浦东机场运行特点\n",
        encoding="utf-8",
    )
    pdf = pdf_dir / "AirDropManual-机场特点汇总(Airport Information)20260720-Manual.pdf"
    pdf.write_bytes(b"%PDF-test")

    candidates = agent.find_airport_manual_candidates(knowledge)

    assert candidates[0] == pdf.resolve()
    assert agent.manual_version(candidates[0]) == 20260720
    assert agent.manual_information_type(candidates[0]) == "PDF"


def test_pdf_normalization_filters_only_known_repeated_lines() -> None:
    raw = "\n".join(
        [
            "非受 控文件 ，仅供 参考 FORREFE RENCEO NLY",
            "版本号 20260720 修改日期：2026 年 7 月 20 日",
            "版本号：20260720",
            "523/1722",
            "上海 / 浦东 机场运行特点（ZSPD）",
            "Command characteristics and operational precautions.",
            "PF/PM应交叉检查跑道和程序。",
        ]
    )

    normalized = agent.normalize_pdf_page(raw)

    assert "非受" not in normalized
    assert "版本号" not in normalized
    assert "523/1722" not in normalized
    assert "上海 / 浦东 机场运行特点（ZSPD）" in normalized
    assert "Command characteristics and operational precautions." in normalized
    assert "PF/PM应交叉检查跑道和程序。" in normalized


def test_pdf_extraction_is_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = 0

    class FakePage:
        def extract_text(self) -> str:
            return "上海浦东机场运行特点\n" + ("机场运行风险。" * 3000)

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    def fake_reader(_: str) -> FakeReader:
        nonlocal calls
        calls += 1
        return FakeReader()

    monkeypatch.setattr(agent, "PdfReader", fake_reader)
    agent.extract_pdf_text.cache_clear()
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-test")

    first = agent.extract_pdf_text(str(pdf.resolve()))
    second = agent.extract_pdf_text(str(pdf.resolve()))

    assert first == second
    assert calls == 1


def test_pdf_failure_falls_back_to_txt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    knowledge = tmp_path / "knowledge"
    pdf_dir = knowledge / "pdf"
    pdf_dir.mkdir(parents=True)
    pdf = pdf_dir / "AirDropManual-机场特点汇总(Airport Information)20260720-Manual.pdf"
    pdf.write_bytes(b"%PDF-broken")
    txt = knowledge / "airport_information_20260720.txt"
    txt_text = "\n".join(
        [
            "版本号 20260720",
            "上海 / 浦东 机场运行特点（ZSPD）",
            "典型不安全事件",
            "1. 曾发生鸟击事件。",
            "核心威胁",
            "1. 地面滑行应防止跑道侵入。",
        ]
    )
    txt.write_text(txt_text, encoding="utf-8")

    def fake_read(path: Path) -> tuple[str, list[str]]:
        if path.suffix.lower() == ".pdf":
            raise RuntimeError("模拟PDF读取失败")
        return txt_text, []

    monkeypatch.setattr(agent, "read_manual_text", fake_read)
    data, source, version, source_type, warnings = agent.manual_airport_data(
        knowledge,
        ["上海浦东"],
        {"上海浦东": "ZSPD"},
        max_items=5,
    )

    assert "上海浦东" in data
    assert Path(source) == txt.resolve()
    assert version == 20260720
    assert source_type == "TXT"
    assert any("模拟PDF读取失败" in warning for warning in warnings)
    assert any("已安全回退" in warning for warning in warnings)


def test_pdf_failure_does_not_fall_back_to_older_txt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    knowledge = tmp_path / "knowledge"
    pdf_dir = knowledge / "pdf"
    pdf_dir.mkdir(parents=True)
    pdf = pdf_dir / "AirDropManual-机场特点汇总(Airport Information)20260720-Manual.pdf"
    pdf.write_bytes(b"%PDF-broken")
    older = knowledge / "airport_information_20260615.txt"
    older.write_text(
        "版本号 20260615\n上海浦东机场运行特点\n典型不安全事件\n1. 旧事件。",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        agent,
        "read_manual_text",
        lambda path: (_ for _ in ()).throw(RuntimeError("模拟PDF读取失败")),
    )
    data, source, version, source_type, warnings = agent.manual_airport_data(
        knowledge,
        ["上海浦东"],
        {"上海浦东": "ZSPD"},
        max_items=5,
    )

    assert data == {}
    assert source == ""
    assert version == 0
    assert source_type == ""
    assert any("模拟PDF读取失败" in warning for warning in warnings)


@pytest.mark.parametrize(
    "airport",
    ["上海浦东", "西宁曹家堡", "南昌昌北", "丽江三义"],
)
def test_curated_typical_content_is_not_replaced_by_pdf_facts(airport: str) -> None:
    sentinel = ["PDF最新事实不应覆盖人工精选运行表达。"]

    output = agent.selected_typical_items(
        airport,
        sentinel,
        sentinel,
        month=7,
        max_items=5,
        detail=True,
    )

    assert output == agent.CURATED_TYPICAL_INCIDENTS[airport][:5]
    assert all("PDF最新事实" not in item for item in output)


def test_curated_core_content_is_not_replaced_by_pdf_facts() -> None:
    sentinel = ["PDF最新事实不应覆盖人工精选运行表达。"]

    assert agent.airport_core_items(
        "西宁曹家堡", sentinel, agent.date(2026, 7, 8), detail=True
    ) == agent.CURATED_CORE_THREATS["西宁曹家堡"][:6]
    assert agent.airport_core_items(
        "南昌昌北", sentinel, agent.date(2026, 7, 8), detail=True
    ) == agent.CURATED_CORE_THREATS["南昌昌北"][:6]

    pudong = agent.airport_core_items(
        "上海浦东", sentinel, agent.date(2026, 7, 8), detail=True
    )
    lijiang = agent.airport_core_items(
        "丽江三义", sentinel, agent.date(2026, 7, 8), detail=True
    )
    assert len(pudong) >= 6
    assert len(lijiang) >= 4
    assert all("PDF最新事实" not in item for item in [*pudong, *lijiang])


def _copy_real_runtime_repo(destination: Path, *, include_pdf: bool) -> None:
    (destination / "config").mkdir(parents=True)
    (destination / "knowledge").mkdir(parents=True)
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
    if include_pdf:
        pdf_dir = destination / "knowledge" / "pdf"
        pdf_dir.mkdir()
        shutil.copy2(REAL_PDF, pdf_dir / REAL_PDF.name)


def _run_real_task(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
) -> tuple[str, dict]:
    monkeypatch.setattr(
        agent,
        "fetch_airport_weather",
        lambda icao, timeout=20: SimpleNamespace(
            icao=icao,
            metar="",
            taf="",
            error="",
        ),
    )
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "flight_prep_agent.py",
            "--repo",
            str(repo),
            "--target-date",
            REAL_TARGET_DATE,
            "--flight-number",
            REAL_FLIGHT_NUMBER,
            "--departure",
            REAL_DEPARTURE,
            "--arrival",
            REAL_ARRIVAL,
        ],
    )
    agent.extract_pdf_text.cache_clear()

    assert agent.main() == 0

    output = repo / "flight_preparation"
    group = (output / "latest.txt").read_text(encoding="utf-8")
    meta = json.loads((output / "latest_meta.json").read_text(encoding="utf-8"))
    assert not (output / f"{REAL_TARGET_DATE}_航前准备_详细版.txt").exists()
    return group, meta


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def _headings(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().endswith("：")
    ]


def _section(text: str, heading: str) -> str:
    return next(
        part
        for part in _paragraphs(text)
        if part.startswith(heading)
    )


@pytest.mark.skipif(not REAL_PDF.exists(), reason="仓库未包含机场手册PDF")
def test_real_flight_before_after_pdf_regression(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline_repo = tmp_path / "baseline"
    upgraded_repo = tmp_path / "upgraded"
    _copy_real_runtime_repo(baseline_repo, include_pdf=False)
    _copy_real_runtime_repo(upgraded_repo, include_pdf=True)

    baseline_group, baseline_meta = _run_real_task(
        monkeypatch,
        baseline_repo,
    )
    upgraded_group, upgraded_meta = _run_real_task(
        monkeypatch,
        upgraded_repo,
    )

    assert baseline_meta["airport_information_type"] == "TXT"
    assert baseline_meta["airport_information_version"] == 20260615
    assert upgraded_meta["airport_information_type"] == "PDF"
    assert upgraded_meta["airport_information_version"] == REAL_PDF_VERSION

    assert _paragraphs(upgraded_group)[:2] == _paragraphs(baseline_group)[:2]
    assert "作为PF/PM各取最近一次" in _paragraphs(upgraded_group)[1]
    assert _headings(upgraded_group) == _headings(baseline_group)

    for airport in KEY_AIRPORTS:
        typical_section = _section(
            upgraded_group,
            f"{airport}机场典型不安全事件：",
        )
        assert re.search(r"(?m)^1\.\s+\S", typical_section)
        assert not re.search(r"(?m)^\d+、", typical_section)
        assert "责任中队" not in typical_section
        assert "机场运行特点" not in typical_section

    for heading in ("上海浦东机场：", "西宁曹家堡机场："):
        assert _section(upgraded_group, heading) == _section(baseline_group, heading)

    assert len(upgraded_group) <= int(len(baseline_group) * 1.15)
