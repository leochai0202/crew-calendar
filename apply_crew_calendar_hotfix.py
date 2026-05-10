#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crew-calendar hotfix patcher

用途：
1) 自动修改当前仓库里的 main.py：
   - 收紧 DOM 读取范围，避免把别的日期/隐藏卡片里的 Grounding 串进训练日期；
   - 增加污染块保护，发现串卡就丢弃，宁愿回退摘要，也不写错停飞；
   - 修改等待详情逻辑，让 get_day_block 带 fallback_text 参与污染判断。

2) 自动清理当前 ICS 里 2026-05-10 / 2026-05-11 明显错误的 Grounding/停飞事件。
   下一次 python main.py 跑完后，会重新按最新抓取结果生成这两天任务。

使用方法：
把本文件放到仓库根目录，与 main.py 同级，然后运行：
    python apply_crew_calendar_hotfix.py
之后再运行：
    python main.py
或者提交后让 GitHub Actions 自动跑。
"""

import os
import re
import shutil
from datetime import datetime

MAIN_FILE = "main.py"
TARGET_DATES = {"20260510", "20260511"}
ICS_FILES = [
    "crew_schedule.ics",
    "flight.ics",
    "ferry.ics",
    "training.ics",
    "positioning.ics",
    "other.ics",
]


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def backup_file(path: str):
    if not os.path.exists(path):
        return ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.backup_hotfix_{stamp}"
    shutil.copy(path, backup)
    return backup


def find_function_span(source: str, func_name: str):
    pattern = re.compile(rf"^def {re.escape(func_name)}\s*\(.*?^def ", re.S | re.M)
    m = pattern.search(source)
    if m:
        return m.start(), m.end() - len("def ")

    pattern_last = re.compile(rf"^def {re.escape(func_name)}\s*\(.*\Z", re.S | re.M)
    m = pattern_last.search(source)
    if m:
        return m.start(), m.end()

    return None


def replace_function(source: str, func_name: str, replacement: str) -> str:
    span = find_function_span(source, func_name)
    if not span:
        raise RuntimeError(f"没有找到函数：{func_name}")
    start, end = span
    replacement = replacement.rstrip() + "\n\n\n"
    return source[:start] + replacement + source[end:]


GET_DAY_BLOCK_BY_DOM = r'''def get_day_block_by_dom(page, header: str, next_header=None) -> str:
    """
    严格版 DOM 读取：
    只读取“当前日期行所在任务列表区域”下面、下一个日期头之前的可见详情。
    不再全页面按 Y 坐标大范围扫，避免把 Grounding / 其它日期串进当前日期。
    """
    try:
        result = page.evaluate(
            """
            ({header, nextHeader}) => {
                function norm(s) {
                    return String(s || "")
                        .replace(/\\u00a0/g, " ")
                        .replace(/[ \\t]+/g, " ")
                        .replace(/\\r/g, "")
                        .trim();
                }

                function visible(el) {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (!style) return false;
                    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
                    const r = el.getBoundingClientRect();
                    if (!r || r.width < 1 || r.height < 1) return false;
                    return true;
                }

                function rectInfo(el) {
                    const r = el.getBoundingClientRect();
                    return {
                        top: r.top,
                        bottom: r.bottom,
                        left: r.left,
                        right: r.right,
                        width: r.width,
                        height: r.height
                    };
                }

                function countDateHeaders(s) {
                    const m = String(s || "").match(/\\d{2}月\\d{2}日\\s*周./g);
                    return m ? m.length : 0;
                }

                const all = Array.from(document.querySelectorAll("body *"));
                let headerCandidates = [];

                for (const el of all) {
                    if (!visible(el)) continue;

                    const text = norm(el.innerText || el.textContent || "");
                    if (!text) continue;
                    if (!text.includes(header)) continue;

                    const r = el.getBoundingClientRect();

                    // 排除全页面大容器：包含太多日期头的一律不要
                    if (countDateHeaders(text) >= 3) continue;

                    let score = 0;

                    if (text === header) score += 30;
                    if (text.startsWith(header)) score += 50;
                    if (/\\d{2}:\\d{2}\\s*[-~～—–]+\\s*\\d{2}:\\d{2}/.test(text)) score += 30;
                    if (/(训练|航班|置位|摆渡|备份|待命|考勤|停飞|Grounding)/.test(text)) score += 30;

                    // 右侧任务列表通常较宽，左侧日历小格子较窄
                    if (r.width >= 300) score += 20;
                    if (r.left >= 250) score += 20;

                    // 过大的容器扣分
                    if (r.height > 180) score -= 40;
                    if (text.length > 300) score -= 40;

                    headerCandidates.push({el, text, score, rect: rectInfo(el)});
                }

                if (!headerCandidates.length) {
                    return {ok: false, reason: "header_not_found", text: "", debug: {}};
                }

                headerCandidates.sort((a, b) => b.score - a.score);
                const headerEl = headerCandidates[0].el;

                // 向上找“日期任务行”容器，但不能找到整页大容器
                let rowNode = headerEl;
                for (let i = 0; i < 8; i++) {
                    if (!rowNode || !rowNode.parentElement) break;

                    const parent = rowNode.parentElement;
                    const pr = parent.getBoundingClientRect();
                    const pt = norm(parent.innerText || parent.textContent || "");

                    if (countDateHeaders(pt) >= 3) break;
                    if (pt.length > 600) break;

                    if (pr.width >= 350 && pr.height >= 28 && pr.height <= 160) {
                        rowNode = parent;
                    }

                    if (pr.width >= 500 && pr.height >= 35 && pr.height <= 120) {
                        rowNode = parent;
                        break;
                    }
                }

                const rowRect = rowNode.getBoundingClientRect();
                const headerTop = rowRect.top;
                const rowBottom = rowRect.bottom;

                // 只允许读取当前任务列表横向区域，避免读到左侧日历或其它面板
                const regionLeft = Math.max(0, rowRect.left - 30);
                const regionRight = Math.min(window.innerWidth, rowRect.right + 30);

                let nextTop = Infinity;

                if (nextHeader) {
                    let nextCandidates = [];

                    for (const el of all) {
                        if (!visible(el)) continue;

                        const text = norm(el.innerText || el.textContent || "");
                        if (!text || !text.includes(nextHeader)) continue;
                        if (countDateHeaders(text) >= 3) continue;

                        const r = el.getBoundingClientRect();

                        if (r.top <= headerTop + 5) continue;

                        // 必须和当前任务列表横向区域有交集
                        const overlap = Math.min(r.right, regionRight) - Math.max(r.left, regionLeft);
                        if (overlap <= 20) continue;

                        let score = 0;
                        if (text.startsWith(nextHeader)) score += 50;
                        if (/\\d{2}:\\d{2}\\s*[-~～—–]+\\s*\\d{2}:\\d{2}/.test(text)) score += 20;
                        if (r.width >= 300) score += 20;
                        if (r.height > 180) score -= 30;

                        nextCandidates.push({el, score, top: r.top});
                    }

                    if (nextCandidates.length) {
                        nextCandidates.sort((a, b) => {
                            if (b.score !== a.score) return b.score - a.score;
                            return a.top - b.top;
                        });
                        nextTop = nextCandidates[0].top;
                    }
                }

                const rows = [];

                for (const el of all) {
                    if (!visible(el)) continue;

                    const r = el.getBoundingClientRect();

                    // 只读日期行下方到下一个日期头之前
                    if (r.bottom < rowBottom - 3) continue;
                    if (r.top > nextTop - 5) continue;

                    // 必须在同一个任务列表横向区域
                    const overlap = Math.min(r.right, regionRight) - Math.max(r.left, regionLeft);
                    if (overlap <= 20) continue;

                    const text = norm(el.innerText || el.textContent || "");
                    if (!text) continue;
                    if (text.length > 800) continue;
                    if (countDateHeaders(text) >= 2) continue;

                    // 只取更像叶子节点的文本，避免父容器重复吞大段
                    let childTextCount = 0;
                    for (const child of Array.from(el.children || [])) {
                        if (!visible(child)) continue;
                        const ct = norm(child.innerText || child.textContent || "");
                        if (ct && text.includes(ct)) childTextCount++;
                    }

                    if (childTextCount >= 3 && text.length > 120) continue;

                    rows.push({
                        top: r.top,
                        left: r.left,
                        bottom: r.bottom,
                        text,
                        tag: el.tagName,
                        cls: String(el.className || "").slice(0, 100)
                    });
                }

                rows.sort((a, b) => {
                    if (Math.abs(a.top - b.top) > 3) return a.top - b.top;
                    return a.left - b.left;
                });

                const seen = new Set();
                const lines = [];

                function addLine(s) {
                    s = norm(s);
                    if (!s) return;
                    if (s.length > 300) return;
                    if (nextHeader && s.includes(nextHeader)) return;
                    if (seen.has(s)) return;
                    seen.add(s);
                    lines.push(s);
                }

                addLine(header);

                for (const row of rows) {
                    const parts = row.text.split(/\\n+/).map(norm).filter(Boolean);

                    for (const p of parts) {
                        if (p === header) continue;

                        if (p.includes(header)) {
                            const after = norm(p.slice(p.indexOf(header) + header.length));
                            if (after) addLine(after);
                            continue;
                        }

                        addLine(p);
                    }
                }

                return {
                    ok: true,
                    reason: "ok",
                    text: lines.join("\\n"),
                    debug: {
                        selectedHeaderText: headerCandidates[0].text,
                        selectedHeaderScore: headerCandidates[0].score,
                        selectedHeaderRect: headerCandidates[0].rect,
                        rowRect: rectInfo(rowNode),
                        regionLeft,
                        regionRight,
                        nextTop,
                        sample: rows.slice(0, 40)
                    }
                };
            }
            """,
            {"header": header, "nextHeader": next_header or ""},
        )

        save_text(
            f"dom_read_{safe_name(header)}.json",
            json.dumps(result, ensure_ascii=False, indent=2),
        )

        if isinstance(result, dict) and result.get("ok") and result.get("text"):
            return normalize_text(result.get("text", ""))

    except Exception as e:
        logger.warning(f"{header} DOM 严格区域读取失败：{e}")

    return ""'''


BLOCK_LOOKS_POLLUTED = r'''def block_looks_polluted(day_block: str, header: str, fallback_text: str = "") -> bool:
    """
    防串卡污染：
    如果当前日期摘要是训练/航班/置位/摆渡，
    但 DOM 详情里读出了 Grounding/停飞，判定为污染块，不写入。
    """
    day_block = normalize_text(day_block)
    fallback_text = normalize_text(fallback_text)

    if not day_block:
        return False

    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    joined = "\n".join(lines)

    other_headers = []
    for line in lines:
        if DAY_HEADER_RE.match(line) and line != header:
            other_headers.append(line)

    if other_headers:
        return True

    date_header_count = len(re.findall(r"\d{2}月\d{2}日\s*周.", joined))
    if date_header_count >= 2:
        return True

    fallback_kind = classify_card_kind(fallback_text, header) if fallback_text else "generic"
    block_kind = classify_card_kind(day_block, header)

    fallback_is_training = fallback_kind == "training" or any(k in fallback_text for k in TRAINING_KEYWORDS)
    fallback_is_flight = fallback_kind == "flight" or bool(FLIGHT_NO_RE.search(fallback_text))
    fallback_is_positioning = fallback_kind == "positioning"
    fallback_is_ferry = fallback_kind == "ferry"

    block_has_grounding = any(k in joined for k in STOP_KEYWORDS)
    block_has_training = any(k in joined for k in TRAINING_KEYWORDS)

    if block_has_grounding and (fallback_is_training or fallback_is_flight or fallback_is_positioning or fallback_is_ferry):
        return True

    if block_kind == "stop" and fallback_kind in {"training", "flight", "positioning", "ferry", "standby", "attendance"}:
        return True

    # 同一块里既有训练细节又有 Grounding，通常是串读
    if block_has_grounding and block_has_training:
        return True

    # 一个日期块里出现过多不同任务关键词，容易是读串
    kind_hits = 0
    for group in [
        POSITIONING_KEYWORDS,
        FERRY_KEYWORDS,
        TRAINING_KEYWORDS,
        STOP_KEYWORDS,
        ATTENDANCE_KEYWORDS,
        STANDBY_KEYWORDS,
    ]:
        if any(k in joined for k in group):
            kind_hits += 1

    if kind_hits >= 3:
        return True

    return False'''


GET_DAY_BLOCK = r'''def get_day_block(page, header: str, next_header=None, fallback_text: str = "") -> str:
    dom_block = get_day_block_by_dom(page, header, next_header=next_header)
    body_block = get_day_block_by_body_text(page, header, next_header=next_header)

    if dom_block and block_looks_polluted(dom_block, header, fallback_text=fallback_text):
        save_text(f"polluted_dom_block_{safe_name(header)}.txt", dom_block)
        dom_block = ""

    if body_block and block_looks_polluted(body_block, header, fallback_text=fallback_text):
        save_text(f"polluted_body_block_{safe_name(header)}.txt", body_block)
        body_block = ""

    if dom_block and not body_block:
        return dom_block

    if body_block and not dom_block:
        return body_block

    if dom_block and body_block:
        dom_score = len(dom_block)
        body_score = len(body_block)

        if any(k in dom_block for k in DETAIL_SIGNAL_KEYWORDS):
            dom_score += 500

        if any(k in body_block for k in DETAIL_SIGNAL_KEYWORDS):
            body_score += 500

        if "航班动态" in dom_block:
            dom_score += 500

        if "航班动态" in body_block:
            body_score += 500

        chosen = dom_block if dom_score >= body_score else body_block

        if block_looks_polluted(chosen, header, fallback_text=fallback_text):
            save_text(f"polluted_chosen_block_{safe_name(header)}.txt", chosen)
            return ""

        return chosen

    return ""'''


WAIT_FOR_REAL_DAY_DETAIL = r'''def wait_for_real_day_detail(page, header: str, next_header=None, fallback_text: str = "", max_wait_ms: int = 10000):
    deadline = datetime.now() + timedelta(milliseconds=max_wait_ms)

    last_block = ""
    last_cards = []
    has_real_detail = False

    while datetime.now() < deadline:
        try:
            day_block = get_day_block(
                page,
                header,
                next_header=next_header,
                fallback_text=fallback_text,
            )

            if block_looks_polluted(day_block, header, fallback_text=fallback_text):
                save_text(f"polluted_wait_block_{safe_name(header)}.txt", day_block)
                day_block = ""

            cards = split_day_block_into_cards(header, day_block)

            last_block = day_block
            last_cards = cards

            if day_block_has_real_detail(day_block, header, fallback_text=fallback_text):
                has_real_detail = True
                return last_block, last_cards, has_real_detail

            if cards_have_real_detail(cards, header, fallback_text=fallback_text):
                has_real_detail = True
                return last_block, last_cards, has_real_detail

        except Exception as e:
            logger.warning(f"等待 {header} 详情时读取失败: {e}")

        random_like_wait(page, 800, 400)

    return last_block, last_cards, has_real_detail'''


def patch_main_py():
    if not os.path.exists(MAIN_FILE):
        raise FileNotFoundError(f"当前目录没有找到 {MAIN_FILE}，请把本脚本放到仓库根目录运行。")

    source = read_text(MAIN_FILE)
    backup = backup_file(MAIN_FILE)

    source = replace_function(source, "get_day_block_by_dom", GET_DAY_BLOCK_BY_DOM)

    if "def block_looks_polluted(" in source:
        source = replace_function(source, "block_looks_polluted", BLOCK_LOOKS_POLLUTED)
    else:
        span = find_function_span(source, "get_day_block")
        if not span:
            raise RuntimeError("没有找到 get_day_block，无法插入 block_looks_polluted")
        start, _ = span
        source = source[:start] + BLOCK_LOOKS_POLLUTED.rstrip() + "\n\n\n" + source[start:]

    source = replace_function(source, "get_day_block", GET_DAY_BLOCK)
    source = replace_function(source, "wait_for_real_day_detail", WAIT_FOR_REAL_DAY_DETAIL)

    write_text(MAIN_FILE, source)
    print(f"✅ 已修补 {MAIN_FILE}")
    if backup:
        print(f"   备份文件：{backup}")


def vevent_date(block: str) -> str:
    m = re.search(r"^DTSTART(?:;[^:]+)?:([0-9]{8})T", block, flags=re.M)
    return m.group(1) if m else ""


def is_bad_grounding_event(block: str) -> bool:
    date = vevent_date(block)
    if date not in TARGET_DATES:
        return False

    if "Grounding" in block or "类型：停飞" in block or "SUMMARY:📋" in block or "SUMMARY:\\ud83d\\udccb" in block:
        return True

    # 之前串卡可能把 05月10日 周日 训练写到了 05月11日
    if date == "20260511" and "05月10日 周日" in block:
        return True

    return False


def cleanup_ics_file(path: str):
    if not os.path.exists(path):
        return 0

    text = read_text(path)
    blocks = re.findall(r"BEGIN:VEVENT\s.*?END:VEVENT", text, flags=re.S)
    if not blocks:
        return 0

    removed = 0
    kept = []
    for block in blocks:
        if is_bad_grounding_event(block):
            removed += 1
        else:
            kept.append(block.strip())

    if removed == 0:
        return 0

    backup = backup_file(path)
    content = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Crew Calendar//CN"]
    content.extend(kept)
    content.append("END:VCALENDAR")
    write_text(path, "\n".join(content))
    print(f"🧹 已清理 {path}: 删除 {removed} 个错误事件")
    if backup:
        print(f"   备份文件：{backup}")
    return removed


def cleanup_wrong_ics_events():
    total = 0
    for path in ICS_FILES:
        total += cleanup_ics_file(path)
    if total:
        print(f"✅ ICS 错误事件清理完成，共删除 {total} 个。")
    else:
        print("ℹ️ 没有在 ICS 中找到需要清理的 2026-05-10/11 错误 Grounding 事件。")


def main():
    patch_main_py()
    cleanup_wrong_ics_events()
    print("\n下一步：运行 python main.py，或者提交到 GitHub 后让 Actions 自动跑。")
    print("这次修补会避免把训练日期读串成 Grounding；如果详情仍读不到，会回退摘要，不会再写错停飞。")


if __name__ == "__main__":
    main()
