import logging

import crew_calendar_main as calendar


HEADER = "08月11日 周二"
SUMMARY = "航班 06:50 - 13:45"

CARD_6809 = """9C6809
B6562
A320
05:00 沈阳桃仙 航班动态
沈阳桃仙桂林两江 06:50 - 10:40"""

CARD_7080 = """9C7080
B6562
A320
09:55 桂林两江 航班动态
桂林两江扬州泰州 11:25 - 13:45"""

REAL_CARDS = [{"text": CARD_6809}, {"text": CARD_7080}]
REAL_BLOCK = calendar.build_day_block_from_detail_cards(HEADER, REAL_CARDS)


def test_already_expanded_detail_is_read_without_toggle(monkeypatch) -> None:
    monkeypatch.setattr(
        calendar,
        "wait_for_real_day_detail",
        lambda *args, **kwargs: (REAL_BLOCK, REAL_CARDS, True),
    )
    monkeypatch.setattr(
        calendar,
        "click_day_toggle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("expanded detail must not be toggled")
        ),
    )

    clicked, block, cards, ready = calendar.expand_day_get_real_detail(
        object(), HEADER, fallback_text=SUMMARY
    )

    assert clicked is False
    assert ready is True
    assert block == REAL_BLOCK
    assert cards == REAL_CARDS


def test_collapsed_detail_is_toggled_exactly_once(monkeypatch) -> None:
    reads = iter(
        [
            ("", [], False),
            (REAL_BLOCK, REAL_CARDS, True),
        ]
    )
    clicks = []
    monkeypatch.setattr(
        calendar,
        "wait_for_real_day_detail",
        lambda *args, **kwargs: next(reads),
    )
    monkeypatch.setattr(
        calendar,
        "inspect_day_detail_panel",
        lambda *args, **kwargs: {"state": calendar.DETAIL_COLLAPSED},
    )
    monkeypatch.setattr(
        calendar,
        "click_day_toggle",
        lambda *args, **kwargs: clicks.append(HEADER) or True,
    )

    clicked, block, cards, ready = calendar.expand_day_get_real_detail(
        object(), HEADER, fallback_text=SUMMARY
    )

    assert clicked is True
    assert ready is True
    assert clicks == [HEADER]
    assert block == REAL_BLOCK
    assert cards == REAL_CARDS


def test_summary_is_ignored_when_two_real_cards_are_visible() -> None:
    assert calendar.cards_have_real_detail(
        REAL_CARDS,
        HEADER,
        fallback_text=SUMMARY,
    )
    day_blocks = [
        {
            "day_header": HEADER,
            "day_block": REAL_BLOCK,
            "cards": REAL_CARDS,
        }
    ]

    items = calendar.prepare_items(day_blocks, 2026)

    assert [item["flight_no"] for item in items] == ["9C6809", "9C7080"]
    assert all(not item.get("summary_fallback") for item in items)


def test_visible_cards_can_come_from_independent_detail_panel() -> None:
    class IndependentPanelPage:
        def evaluate(self, script, header):
            assert header == HEADER
            assert "independentCards" in script
            return {
                "state": calendar.DETAIL_EXPANDED,
                "date_selected": True,
                "detail_visible": True,
                "toggle_found": True,
                "cards": REAL_CARDS,
            }

    assert calendar.get_selected_day_detail_cards(IndependentPanelPage(), HEADER) == REAL_CARDS


def test_click_sent_without_visible_detail_is_not_ready(monkeypatch) -> None:
    reads = iter([("", [], False), ("", [], False)])
    monkeypatch.setattr(
        calendar,
        "wait_for_real_day_detail",
        lambda *args, **kwargs: next(reads),
    )
    monkeypatch.setattr(
        calendar,
        "inspect_day_detail_panel",
        lambda *args, **kwargs: {"state": calendar.DETAIL_COLLAPSED},
    )
    clicks = []
    monkeypatch.setattr(
        calendar,
        "click_day_toggle",
        lambda *args, **kwargs: clicks.append(HEADER) or True,
    )

    clicked, block, cards, ready = calendar.expand_day_get_real_detail(
        object(), HEADER, fallback_text=SUMMARY
    )

    assert clicked is True
    assert ready is False
    assert block == ""
    assert cards == []
    assert clicks == [HEADER]


def _summary_only_collection(monkeypatch, *, has_history: bool):
    monkeypatch.setattr(calendar, "load_all_visible_tasks", lambda page: None)
    monkeypatch.setattr(calendar, "get_day_headers", lambda page: [HEADER])
    monkeypatch.setattr(
        calendar,
        "get_day_summary_task_map",
        lambda page: {HEADER: SUMMARY},
    )
    monkeypatch.setattr(
        calendar,
        "expand_day_get_real_detail",
        lambda *args, **kwargs: (False, "", [], False),
    )
    monkeypatch.setattr(
        calendar,
        "existing_last_good_detail_for_day",
        lambda *args, **kwargs: has_history,
    )
    return calendar.collect_day_blocks(object(), page_year=2026)


def test_summary_refresh_keeps_existing_real_history(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING)

    assert _summary_only_collection(monkeypatch, has_history=True) == []
    assert "DETAIL_REFRESH_FAILED_USING_LAST_GOOD_DATA" in caplog.text


def test_first_summary_only_result_never_enters_flight_calendar(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING)

    assert _summary_only_collection(monkeypatch, has_history=False) == []
    assert "DETAIL_REFRESH_FAILED_NO_LAST_GOOD_DATA" in caplog.text
    items = calendar.prepare_items(
        [
            {
                "day_header": HEADER,
                "day_block": f"{HEADER}\n{SUMMARY}",
                "cards": [{"text": SUMMARY, "summary_fallback": True}],
            }
        ],
        2026,
    )
    assert items == []


def test_real_detail_replaces_summary_only_collection(monkeypatch) -> None:
    monkeypatch.setattr(calendar, "load_all_visible_tasks", lambda page: None)
    monkeypatch.setattr(calendar, "get_day_headers", lambda page: [HEADER])
    monkeypatch.setattr(
        calendar,
        "get_day_summary_task_map",
        lambda page: {HEADER: SUMMARY},
    )
    monkeypatch.setattr(
        calendar,
        "expand_day_get_real_detail",
        lambda *args, **kwargs: (False, REAL_BLOCK, REAL_CARDS, True),
    )

    blocks = calendar.collect_day_blocks(object(), page_year=2026)
    items = calendar.prepare_items(blocks, 2026)

    assert [item["flight_no"] for item in items] == ["9C6809", "9C7080"]


def test_jiayuguan_normalization_is_unchanged() -> None:
    assert calendar.BASE_AIRPORT_CN_TO_ICAO["嘉峪关"] == "ZLJQ"
    assert calendar.BASE_AIRPORT_CN_TO_ICAO["嘉峪关酒泉"] == "ZLJQ"
    calendar.rebuild_airport_indexes()
    assert calendar.split_concat_airport_route("嘉峪关酒泉沈阳桃仙") == (
        "嘉峪关酒泉",
        "沈阳桃仙",
    )


def test_non_flight_task_classification_is_unchanged() -> None:
    assert calendar.classify_card_kind("理论课 08:00 - 10:00") == "training"
    assert calendar.classify_card_kind("置位 08:00 - 10:00") == "positioning"
    assert calendar.classify_card_kind("摆渡 08:00 - 10:00") == "ferry"
    assert calendar.classify_card_kind("待命 08:00 - 10:00") == "standby"
