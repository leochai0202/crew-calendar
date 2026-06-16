from crew_agents.knowledge import extract_relevant_chunks


def test_extract_relevant_chunks_ignores_unrelated():
    text = "A" * 100 + "深圳机场 核心威胁 雷雨 滑行" + "B" * 1000 + "无关内容"
    out = extract_relevant_chunks(text, ["深圳机场"], window=300, max_chars=500)
    assert "深圳机场" in out
    assert len(out) <= 500
