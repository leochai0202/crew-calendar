from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from crew_agents import flight_prep_agent as agent
from crew_agents.ics_utils import CalendarEvent


BEIJING = ZoneInfo("Asia/Shanghai")
AIRPORTS = ["济南遥墙", "深圳宝安"]


def _event() -> CalendarEvent:
    return CalendarEvent(
        uid="route-guard",
        summary="✈️ 9C6596Y 济南遥墙→深圳宝安",
        start=datetime(2026, 9, 25, 8, 0, tzinfo=BEIJING),
        end=datetime(2026, 9, 25, 10, 30, tzinfo=BEIJING),
        description=(
            "类型：航班\n"
            "航班：9C6596Y\n"
            "航线：济南遥墙 → 深圳宝安\n"
            "签到：05:30｜济南遥墙\n"
            "机型：A320｜注册号：B-6667\n"
            "人员名单：\n"
            "• 段洋硕\n"
            "• 张三(R)"
        ),
        location="济南遥墙",
        properties={},
        source_file="test.ics",
    )


def _briefing(extra: str) -> str:
    return (
        "我是来自飞行十五中队的副驾驶段洋硕。\n\n"
        "上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）：\n"
        "上一次作为PF教员评价：评价；作为PM机长评价：评价。\n\n"
        "个人对本次航班中识别的风险：\n"
        "天气及动态资料以航前资料为准。\n\n"
        "核心威胁：\n\n"
        "济南遥墙机场：\n"
        f"{extra}\n\n"
        "深圳宝安机场：\n"
        "结合当日运行资料完成航前准备。\n"
    )


def _errors(extra: str) -> list[str]:
    return agent.validate_content(
        _briefing(extra),
        _event(),
        {"name": "段洋硕"},
        AIRPORTS,
        language="zh",
    )


@pytest.mark.parametrize(
    "route_text",
    [
        "济南-深圳航线运行信息以当日资料为准。",
        "济南遥墙→深圳宝安的运行信息以当日资料为准。",
        "济南至深圳航线运行信息以当日资料为准。",
        "大连-济南航线运行信息以当日资料为准。",
    ],
)
def test_operational_route_text_is_not_internal_matching_metadata(
    route_text: str,
) -> None:
    assert _errors(route_text) == []


@pytest.mark.parametrize(
    ("leaked_text", "expected_token"),
    [
        ("本次航班号为9C6596Y。", "9C6596Y"),
        ("本次飞机注册号为B-6667。", "B-6667"),
        ("签到：05:30。", "签到："),
        ("本次与张三一同执飞。", "张三"),
    ],
)
def test_true_internal_matching_metadata_remains_blocked(
    leaked_text: str,
    expected_token: str,
) -> None:
    assert f"正文泄露内部匹配信息：{expected_token}" in _errors(leaked_text)
