import os
import re
import io
import json
import base64
import shutil
import hashlib
from itertools import product
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, ImageFilter
import pytesseract
from playwright.sync_api import sync_playwright


LOGIN_URL = "https://cp.9cair.com"
MISSION_URL = "https://cp.9cair.com/html/task/mission.html"

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]

ARTIFACT_DIR = "debug_output"
if os.path.exists(ARTIFACT_DIR):
    shutil.rmtree(ARTIFACT_DIR)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

SH_TZ = ZoneInfo("Asia/Shanghai")
AIRPORT_ALIASES_FILE = "airport_aliases.json"

# =========================
# 基础机场表（内置常见机场）
# =========================
BASE_AIRPORT_CN_TO_ICAO = {
    "上海虹桥": "ZSSS",
    "上海浦东": "ZSPD",
    "西安咸阳": "ZLXY",
    "重庆江北": "ZUCK",
    "大连周水子": "ZYTL",
    "深圳宝安": "ZGSZ",
    "济南遥墙": "ZSJN",
    "哈尔滨太平": "ZYHB",
    "淮安涟水": "ZSSH",
    "呼和浩特白塔": "ZBHH",
    "长春龙嘉": "ZYCC",
    "兰州中川": "ZLLL",
    "广州白云": "ZGGG",
    "揭阳潮汕": "ZGOW",
    "札幌新千岁": "RJCC",
    "新千岁": "RJCC",
    "南宁吴圩": "ZGNN",
    "曼谷素旺那普": "VTBS",
    "曼谷素万那普": "VTBS",
}

AIRPORT_CN_TO_ICAO = {}
AIRPORT_ICAO_TO_CN = {}
AIRPORT_NAMES = []

# =========================
# 正则常量
# =========================
FLIGHT_NO_RE = re.compile(r"9C\d{3,4}[A-Z]?")
REG_MODEL_RE = re.compile(r"^B[0-9A-Z]{4,5}A(?:319|320|321)$")
REG_AND_MODEL_RE = re.compile(r"\b(B[0-9A-Z]{4,5})(A319|A320|A321)\b")
REG_ONLY_RE = re.compile(r"\bB[0-9A-Z]{4,5}\b")
TIME_RANGE_RE = re.compile(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})")
PAGE_YEAR_MONTH_RE = re.compile(r"(\d{4})年(\d{1,2})月")
PURE_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
ICAO_RE = re.compile(r"\b[A-Z]{4}\b")
LATIN_PERSON_RE = re.compile(r"[A-Z][A-Z\s\.\-']{1,80}\([^)]*\)")


# =========================
# 基础工具
# =========================
def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_text(filename: str, text: str):
    with open(os.path.join(ARTIFACT_DIR, filename), "w", encoding="utf-8") as f:
        f.write(text)


def save_bytes(filename: str, content: bytes):
    with open(os.path.join(ARTIFACT_DIR, filename), "wb") as f:
        f.write(content)


def escape_ics_text(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\n", r"\n")
    return text


def format_dt_local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def make_datetime(year: int, month: int, day: int, hhmm: str) -> datetime:
    hh, mm = map(int, hhmm.split(":"))
    return datetime(year, month, day, hh, mm, tzinfo=SH_TZ)


def safe_name(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-]+", "_", s).strip("_") or "unnamed"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =========================
# 机场别名自动积累
# =========================
def load_airport_aliases():
    if not os.path.exists(AIRPORT_ALIASES_FILE):
        return {}

    try:
        with open(AIRPORT_ALIASES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_airport_aliases(data: dict):
    try:
        with open(AIRPORT_ALIASES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        pass


def rebuild_airport_indexes():
    global AIRPORT_CN_TO_ICAO, AIRPORT_ICAO_TO_CN, AIRPORT_NAMES

    AIRPORT_CN_TO_ICAO = dict(BASE_AIRPORT_CN_TO_ICAO)
    alias_data = load_airport_aliases()

    for icao, aliases in alias_data.items():
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            alias = normalize_text(str(alias))
            if alias:
                AIRPORT_CN_TO_ICAO[alias] = icao

    AIRPORT_ICAO_TO_CN = {}
    for name, icao in AIRPORT_CN_TO_ICAO.items():
        if icao not in AIRPORT_ICAO_TO_CN:
            AIRPORT_ICAO_TO_CN[icao] = name

    AIRPORT_NAMES = sorted(AIRPORT_CN_TO_ICAO.keys(), key=len, reverse=True)


def add_airport_alias(icao: str, alias: str):
    icao = normalize_text(icao).upper()
    alias = normalize_text(alias)

    if not re.fullmatch(r"[A-Z]{4}", icao):
        return
    if not alias:
        return
    if len(alias) < 2:
        return
    if re.fullmatch(r"[A-Z]{4}", alias):
        return

    data = load_airport_aliases()
    aliases = data.get(icao, [])
    if alias not in aliases:
        aliases.append(alias)
        data[icao] = sorted(set(aliases), key=lambda x: (len(x), x))
        save_airport_aliases(data)
        rebuild_airport_indexes()


# =========================
# 验证码
# =========================
def normalize_candidate(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    if len(text) == 5:
        text = text[:4]
    return text


def score_candidate(text: str) -> int:
    if not text:
        return 0
    score = 0
    if len(text) == 4:
        score += 100
    elif len(text) == 5:
        score += 60
    elif len(text) == 3:
        score += 40
    else:
        score += 10
    score += sum(ch.isalnum() for ch in text)
    return score


def expand_char_options(ch: str):
    mapping = {
        "0": ["0", "O"], "O": ["O", "0"],
        "1": ["1", "I", "L"], "I": ["I", "1", "L"], "L": ["L", "1", "I"],
        "5": ["5", "S"], "S": ["S", "5"],
        "8": ["8", "B"], "B": ["B", "8", "3"],
        "2": ["2", "Z"], "Z": ["Z", "2"],
        "6": ["6", "G"], "G": ["G", "6"],
        "3": ["3", "B"],
        "7": ["7", "T"], "T": ["T", "7"],
    }
    return mapping.get(ch, [ch])


def generate_code_candidates(code: str, limit: int = 20):
    pools = [expand_char_options(ch) for ch in code]
    all_codes = []
    for combo in product(*pools):
        cand = "".join(combo)
        if cand not in all_codes:
            all_codes.append(cand)
        if len(all_codes) >= limit:
            break
    return all_codes


def extract_captcha_bytes(page) -> bytes:
    imgs = page.locator("img")
    count = imgs.count()

    for i in range(count):
        try:
            src = imgs.nth(i).get_attribute("src", timeout=1000)
            if src and src.startswith("data:image"):
                return base64.b64decode(src.split(",", 1)[1])
        except Exception:
            pass

    raise RuntimeError("未找到验证码图片")


def build_variants(img_bytes: bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img = ImageOps.autocontrast(img)

    variants = []
    variants.append(("base_x3", img.resize((img.width * 3, img.height * 3))))
    variants.append(("base_x4", img.resize((img.width * 4, img.height * 4))))

    for threshold in [135, 145, 155, 165, 175, 185]:
        bw = img.point(lambda x, t=threshold: 255 if x > t else 0, mode="1")
        bw = bw.resize((bw.width * 3, bw.height * 3))
        variants.append((f"bw_{threshold}", bw))

    inv = ImageOps.invert(img).resize((img.width * 3, img.height * 3))
    variants.append(("invert_x3", inv))

    sharp = img.filter(ImageFilter.SHARPEN).resize((img.width * 3, img.height * 3))
    variants.append(("sharp_x3", sharp))

    median = img.filter(ImageFilter.MedianFilter(size=3)).resize((img.width * 3, img.height * 3))
    variants.append(("median_x3", median))

    return variants


def solve_captcha(page, attempt_no: int = 0) -> str:
    img_bytes = extract_captcha_bytes(page)
    save_bytes(f"captcha_attempt_{attempt_no}.png", img_bytes)

    variants = build_variants(img_bytes)

    configs = [
        r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        r'--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        r'--psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    ]

    candidates = []
    raw_log = []

    for variant_name, variant in variants:
        for cfg in configs:
            raw = pytesseract.image_to_string(variant, config=cfg)
            cleaned = normalize_candidate(raw)
            raw_log.append(f"{variant_name} | {cfg} | raw={raw!r} | cleaned={cleaned!r}")
            if cleaned:
                candidates.append(cleaned)

    save_text(f"captcha_attempt_{attempt_no}_ocr.txt", "\n".join(raw_log))

    if not candidates:
        return ""

    candidates = sorted(candidates, key=score_candidate, reverse=True)
    return candidates[0][:4]


# =========================
# 登录
# =========================
def fill_login_form(page, code: str):
    inputs = page.locator("input")
    if inputs.count() < 3:
        raise RuntimeError("登录页输入框数量异常")

    inputs.nth(0).fill("")
    inputs.nth(1).fill("")
    inputs.nth(2).fill("")

    inputs.nth(0).fill(USERNAME)
    inputs.nth(1).fill(PASSWORD)
    inputs.nth(2).fill(code)


def page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=8000)
    except Exception:
        return ""


def login(page, max_retries: int = 10):
    for attempt in range(1, max_retries + 1):
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, f"login_page_{attempt}.png"), full_page=True)
            save_text(f"login_page_{attempt}.txt", page_text(page))
        except Exception:
            if attempt == max_retries:
                raise
            page.wait_for_timeout(4000)
            continue

        best_code = solve_captcha(page, attempt_no=attempt)
        if len(best_code) != 4:
            save_text(f"login_attempt_{attempt}_result.txt", "OCR 未得到有效 4 位验证码")
            continue

        candidates = generate_code_candidates(best_code, limit=20)
        save_text(f"login_attempt_{attempt}_candidates.txt", "\n".join(candidates))

        for idx, cand in enumerate(candidates, start=1):
            try:
                fill_login_form(page, cand)
                page.click("text=Login")
                page.wait_for_timeout(4500)

                body_text = page_text(page)
                page.screenshot(
                    path=os.path.join(ARTIFACT_DIR, f"login_attempt_{attempt}_{idx}_{cand}.png"),
                    full_page=True
                )
                save_text(f"login_attempt_{attempt}_{idx}_{cand}.txt", body_text)

                if ("统一认证中心" not in body_text) and ("Login" not in body_text):
                    return

                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass
            except Exception as e:
                save_text(f"login_attempt_{attempt}_{idx}_{cand}_error.txt", repr(e))
                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass

    raise RuntimeError("多次尝试后仍无法登录")


# =========================
# 页面操作
# =========================
def open_mission_page(page):
    for i in range(3):
        try:
            page.goto(MISSION_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)

            try:
                page.locator("text=我的任务").first.click(timeout=5000)
                page.wait_for_timeout(3000)
            except Exception:
                pass

            try:
                if page.locator("text=意见反馈").count() > 0 and page.locator("text=确认").count() > 0:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            body_text = page_text(page)
            if re.search(r"\d{2}月\d{2}日\s*周.", body_text):
                return

        except Exception:
            if i == 2:
                raise
            page.wait_for_timeout(5000)

    raise RuntimeError("未能进入任务列表页")


def get_day_headers(page):
    text = page_text(page)
    headers = []
    for line in text.splitlines():
        line = normalize_text(line)
        if not line:
            continue

        m = re.match(r"^(\d{2}月\d{2}日\s*周.)", line)
        if m:
            headers.append(m.group(1))

    seen = set()
    out = []
    for h in headers:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def click_day_toggle(page, header: str) -> bool:
    row = page.locator(f"text={header}").first
    box = row.bounding_box()
    if not box:
        return False

    x = box["x"] + box["width"] - 28
    y = box["y"] + box["height"] / 2
    page.mouse.click(x, y)
    return True


def expand_day(page, header: str) -> bool:
    ok = click_day_toggle(page, header)
    if ok:
        page.wait_for_timeout(1800)
    return ok


def collapse_day(page, header: str):
    try:
        ok = click_day_toggle(page, header)
        if ok:
            page.wait_for_timeout(800)
    except Exception:
        pass


def get_day_block(page, header: str, next_header: str | None):
    body_text = normalize_text(page.locator("body").inner_text())
    start = body_text.find(header)
    if start == -1:
        return ""

    if next_header:
        end = body_text.find(next_header, start + len(header))
        if end != -1:
            return body_text[start:end].strip()

    return body_text[start:].strip()


def detect_page_year(page) -> int:
    text = page_text(page)
    m = PAGE_YEAR_MONTH_RE.search(text)
    if m:
        return int(m.group(1))
    return datetime.now(SH_TZ).year


# =========================
# 任务识别
# =========================
def detect_task_type(text: str) -> str:
    for t in ["置位", "航班", "训练", "摆渡", "备份", "待命", "考勤"]:
        if t in text:
            return t
    return "任务"


def task_bucket(task_type: str) -> str:
    return {
        "航班": "flight",
        "置位": "positioning",
        "训练": "training",
        "摆渡": "ferry",
    }.get(task_type, "other")


def extract_date(text: str, page_year: int):
    m = re.search(r'(\d{2})月(\d{2})日', text)
    if not m:
        return None
    month = int(m.group(1))
    day = int(m.group(2))
    return page_year, month, day


def is_flight_line(s: str) -> bool:
    return FLIGHT_NO_RE.fullmatch(s) is not None


def is_reg_model_line(s: str) -> bool:
    return REG_MODEL_RE.fullmatch(s) is not None


def is_old_style_header_line(s: str) -> bool:
    s = normalize_text(s)
    return re.fullmatch(r"9C\d{3,4}[A-Z]?\s+B[0-9A-Z]{4,5}\s+A(?:319|320|321)", s) is not None


def extract_old_style_header(line: str):
    line = normalize_text(line)
    m = re.match(r"^(9C\d{3,4}[A-Z]?)\s+(B[0-9A-Z]{4,5})\s+(A319|A320|A321)$", line)
    if not m:
        return None
    return {
        "flight_no": m.group(1),
        "reg": m.group(2),
        "model": m.group(3),
    }


def clean_tail_noise(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if not line:
            continue
        if "查看更多" in line:
            continue
        if PURE_DATE_PREFIX_RE.match(line):
            continue
        cleaned.append(line)
    return cleaned


def split_day_block_into_cards(day_block: str):
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    lines = clean_tail_noise(lines)
    if not lines:
        return []

    starts = []
    for i in range(len(lines)):
        line = lines[i]

        if i + 1 < len(lines):
            if is_flight_line(line) and is_reg_model_line(lines[i + 1]):
                starts.append(i)
                continue

        if extract_old_style_header(line):
            starts.append(i)
            continue

    starts = sorted(set(starts))
    if not starts:
        return []

    cards = []
    for idx, start_i in enumerate(starts):
        end_i = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        chunk_lines = clean_tail_noise(lines[start_i:end_i])

        filtered = []
        for line in chunk_lines:
            if re.fullmatch(r"(9C\d{3,4}[A-Z]?\s*){2,}", line):
                continue
            filtered.append(line)

        chunk = "\n".join(filtered).strip()
        if not chunk:
            continue

        if not TIME_RANGE_RE.search(chunk):
            continue

        if not extract_flight_no(chunk):
            continue

        cards.append(chunk)

    uniq = []
    seen = set()
    for c in cards:
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    return uniq


# =========================
# 解析卡片
# =========================
def extract_flight_no(card_text: str) -> str:
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]

    for line in lines:
        if is_flight_line(line):
            return line

        m = re.match(r"(9C\d{3,4}[A-Z]?)\s+B[0-9A-Z]{4,5}\s+A(?:319|A320|A321)", line)
        if m:
            return m.group(1)

    m = FLIGHT_NO_RE.search(card_text)
    return m.group(0) if m else ""


def extract_reg_and_model(card_text: str):
    m = REG_AND_MODEL_RE.search(card_text)
    if m:
        return m.group(1), m.group(2)

    m_old = re.search(r"9C\d{3,4}[A-Z]?\s+(B[0-9A-Z]{4,5})\s+(A319|A320|A321)", card_text)
    if m_old:
        return m_old.group(1), m_old.group(2)

    reg = ""
    model = ""

    m_reg = REG_ONLY_RE.search(card_text)
    if m_reg:
        reg = m_reg.group(0)

    m_model = re.search(r'\b(A319|A320|A321)\b', card_text)
    if m_model:
        model = m_model.group(0)

    return reg, model


def extract_checkin(card_text: str):
    m = re.search(r'(\d{2}:\d{2})\s*([^\s]+)\s*航班动态', card_text)
    if m:
        return m.group(1), m.group(2)

    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    for line in lines:
        m_old = re.search(r'(\d{2}:\d{2})\s+([^\s]{2,20})', line)
        if not m_old:
            continue
        hhmm = m_old.group(1)
        place = m_old.group(2)
        if f"{hhmm}-" in line:
            continue
        if place in ["A319", "A320", "A321", "航班动态"]:
            continue
        if FLIGHT_NO_RE.fullmatch(place):
            continue
        return hhmm, place

    return "", ""


def extract_start_end_time(card_text: str):
    ranges = TIME_RANGE_RE.findall(card_text)
    if ranges:
        return ranges[-1][0], ranges[-1][1]
    return "", ""


def parse_route_cn_from_line(line: str):
    line = TIME_RANGE_RE.sub("", line).strip()
    line = line.replace("—", "-").replace("－", "-")
    line = re.sub(r"\s+", "", line)

    if "→" in line:
        dep_cn, arr_cn = line.split("→", 1)
        return dep_cn.strip(), arr_cn.strip()

    for dep_cn in AIRPORT_NAMES:
        if line.startswith(dep_cn):
            remain = line[len(dep_cn):].strip()
            if remain:
                return dep_cn, remain

    return "", ""


def extract_airports(card_text: str):
    dep_cn = ""
    arr_cn = ""
    dep = ""
    arr = ""

    lines = [x.strip() for x in card_text.splitlines() if x.strip()]

    candidate_lines = []
    for line in lines:
        if TIME_RANGE_RE.search(line) and "航班动态" not in line:
            candidate_lines.append(line)

    if candidate_lines:
        dep_cn, arr_cn = parse_route_cn_from_line(candidate_lines[-1])
        dep = AIRPORT_CN_TO_ICAO.get(dep_cn, "")
        arr = AIRPORT_CN_TO_ICAO.get(arr_cn, "")

    codes = ICAO_RE.findall(card_text)
    uniq = []
    for c in codes:
        if c not in uniq:
            uniq.append(c)

    if len(uniq) >= 2:
        dep = dep or uniq[0]
        arr = arr or uniq[1]
        dep_cn = dep_cn or AIRPORT_ICAO_TO_CN.get(dep, "")
        arr_cn = arr_cn or AIRPORT_ICAO_TO_CN.get(arr, "")

        if dep_cn:
            add_airport_alias(dep, dep_cn)
        if arr_cn:
            add_airport_alias(arr, arr_cn)

    return dep, arr, dep_cn, arr_cn


# =========================
# 人员名单（最保守模式）
# =========================
def extract_chinese_tagged_people(line: str):
    results = []
    for m in re.finditer(r"\([^)]*\)", line):
        left = line[:m.start()]
        paren = m.group(0)

        j = len(left) - 1
        while j >= 0 and "\u4e00" <= left[j] <= "\u9fff":
            j -= 1
        chinese_block = left[j + 1:]

        if not chinese_block:
            continue

        if 2 <= len(chinese_block) <= 4:
            name = chinese_block
        elif len(chinese_block) > 4:
            name = chinese_block[-3:]
        else:
            continue

        person = f"{name}{paren}"
        if person not in results:
            results.append(person)

    return results


def split_people_from_line(line: str):
    line = normalize_text(line)
    if not line:
        return []

    if any(x in line for x in ["查看更多", "航班动态"]):
        return []

    results = []

    en_matches = LATIN_PERSON_RE.findall(line)
    for m in en_matches:
        m = re.sub(r"\s+", " ", m).strip()
        if m and m not in results:
            results.append(m)

    zh_tagged = extract_chinese_tagged_people(line)
    for m in zh_tagged:
        if m and m not in results:
            results.append(m)

    if results:
        remaining = line
        for m in results:
            remaining = remaining.replace(m, " ")

        remaining = re.sub(r"\([^)]*\)", " ", remaining)
        remaining = re.sub(r"\s+", " ", remaining).strip()

        if remaining:
            for token in remaining.split(" "):
                token = token.strip()
                if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token):
                    if token not in results:
                        results.append(token)

        return results

    parts = [x.strip() for x in re.split(r"\s+", line) if x.strip()]
    pure_names = []
    for p in parts:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", p):
            pure_names.append(p)

    if pure_names:
        return pure_names

    return [line]


def extract_people_lines(card_text: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]

    out = []
    capture = False

    people_markers = {"机长", "副驾驶", "乘务长", "随机人员", "加机组人员"}

    for line in lines:
        if line in people_markers:
            capture = True
            continue

        if not capture:
            continue

        if is_flight_line(line):
            break
        if is_reg_model_line(line):
            break
        if is_old_style_header_line(line):
            break
        if PURE_DATE_PREFIX_RE.match(line):
            break

        if "航班动态" in line:
            continue
        if "查看更多" in line:
            continue
        if TIME_RANGE_RE.search(line):
            continue
        if re.fullmatch(r"\d{2}:\d{2}", line):
            continue

        pieces = split_people_from_line(line)
        for p in pieces:
            p = re.sub(r"\s+", " ", p).strip()
            if p and p not in out:
                out.append(p)

    return out


# =========================
# ICS 输出 / 增量更新
# =========================
def title_icon(task_type: str) -> str:
    return {
        "航班": "✈️",
        "置位": "📍",
        "训练": "🎓",
        "摆渡": "🚐",
        "备份": "🗂",
        "待命": "🕒",
        "考勤": "📋",
        "任务": "🗂",
    }.get(task_type, "🗂")


def build_title(task_type, flight_no, dep, arr, dep_cn, arr_cn):
    icon = title_icon(task_type)

    if flight_no and dep_cn and arr_cn:
        return f"{icon} {flight_no} {dep_cn}→{arr_cn}"
    if flight_no and dep and arr:
        return f"{icon} {flight_no} {dep}→{arr}"
    if flight_no and dep_cn and arr:
        return f"{icon} {flight_no} {dep_cn}→{arr}"
    if flight_no and dep and arr_cn:
        return f"{icon} {flight_no} {dep}→{arr_cn}"
    if flight_no:
        return f"{icon} {flight_no}"
    return f"{icon} {task_type}"


def build_description(item: dict) -> str:
    lines = []
    lines.append(item["day_header"])

    if item["task_type"] != "航班":
        lines.append(f"类型：{item['task_type']}")

    lines.append(f"航班：{item['flight_no']}")

    if item["dep_cn"] and item["arr_cn"]:
        lines.append(f"航线：{item['dep_cn']} → {item['arr_cn']}")
    elif item["dep"] and item["arr"]:
        lines.append(f"航线：{item['dep']} → {item['arr']}")
    elif item["dep_cn"] and item["arr"]:
        lines.append(f"航线：{item['dep_cn']} → {item['arr']}")
    elif item["dep"] and item["arr_cn"]:
        lines.append(f"航线：{item['dep']} → {item['arr_cn']}")

    if item["checkin_time"] and item["checkin_place"]:
        lines.append(f"签到：{item['checkin_time']}｜{item['checkin_place']}")
    elif item["checkin_time"]:
        lines.append(f"签到：{item['checkin_time']}")
    elif item["checkin_place"]:
        lines.append(f"签到地点：{item['checkin_place']}")

    if item["start_time"] and item["end_time"]:
        lines.append(f"任务：{item['start_time']} - {item['end_time']}")

    if item["model"] and item["reg"]:
        lines.append(f"机型：{item['model']}｜注册号：{item['reg']}")
    elif item["model"]:
        lines.append(f"机型：{item['model']}")
    elif item["reg"]:
        lines.append(f"注册号：{item['reg']}")

    if item["people_lines"]:
        lines.append("")
        lines.append("人员名单：")
        for p in item["people_lines"]:
            lines.append(f"• {p}")

    return "\n".join(lines)


def build_vevent(item: dict) -> str:
    title = build_title(
        item["task_type"], item["flight_no"], item["dep"], item["arr"],
        item["dep_cn"], item["arr_cn"]
    )
    desc = build_description(item)
    alarm_desc = f"{item['flight_no']} 签到提醒" if item["flight_no"] else "签到提醒"

    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{item['task_type']}-{item['flight_no']}-{format_dt_local(item['start_dt'])}-{format_dt_local(item['end_dt'])}@crew-calendar",
        f"SUMMARY:{escape_ics_text(title)}",
        f"DTSTART;TZID=Asia/Shanghai:{format_dt_local(item['start_dt'])}",
        f"DTEND;TZID=Asia/Shanghai:{format_dt_local(item['end_dt'])}",
        f"DESCRIPTION:{escape_ics_text(desc)}",
        "BEGIN:VALARM",
        "TRIGGER:-PT90M",
        f"DESCRIPTION:{escape_ics_text(alarm_desc)}",
        "ACTION:DISPLAY",
        "END:VALARM",
        "END:VEVENT",
    ])


def extract_uid_from_vevent(vevent: str) -> str:
    m = re.search(r"^UID:(.+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else ""


def extract_dtstart_from_vevent(vevent: str) -> str:
    m = re.search(r"^DTSTART(?:;[^:]+)?:([0-9T]+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def normalize_vevent_for_compare(vevent: str) -> str:
    lines = [x.strip() for x in vevent.strip().splitlines() if x.strip()]
    return "\n".join(lines)


def load_existing_vevents(filename: str):
    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}

    events = {}
    matches = re.findall(r"BEGIN:VEVENT\s.*?END:VEVENT", content, flags=re.S)
    for block in matches:
        block = block.strip()
        uid = extract_uid_from_vevent(block)
        if uid:
            events[uid] = block
    return events


def merge_events_incremental(existing_events: dict, new_events: dict):
    merged = dict(existing_events)

    changed = False
    added = 0
    updated = 0
    unchanged = 0

    for uid, new_block in new_events.items():
        old_block = existing_events.get(uid)

        if old_block is None:
            merged[uid] = new_block
            changed = True
            added += 1
            continue

        if normalize_vevent_for_compare(old_block) == normalize_vevent_for_compare(new_block):
            unchanged += 1
            continue

        merged[uid] = new_block
        changed = True
        updated += 1

    return merged, changed, added, updated, unchanged


def write_calendar(filename: str, items: list[dict], preserve_existing: bool = True):
    new_events = {}
    for item in items:
        vevent = build_vevent(item)
        uid = extract_uid_from_vevent(vevent)
        if uid:
            new_events[uid] = vevent

    if preserve_existing:
        existing_events = load_existing_vevents(filename)
        merged_events, _, _, _, _ = merge_events_incremental(existing_events, new_events)
    else:
        merged_events = new_events

    ordered = sorted(
        merged_events.values(),
        key=lambda x: (extract_dtstart_from_vevent(x), extract_uid_from_vevent(x))
    )

    content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Crew Calendar//CN",
    ]
    content.extend(ordered)
    content.append("END:VCALENDAR")

    final_text = "\n".join(content)

    old_text = None
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                old_text = f.read()
        except Exception:
            old_text = None

    if old_text == final_text:
        return False

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_text)
    return True


def event_quality(item: dict) -> int:
    score = 0
    if item["flight_no"]:
        score += 10
    if item["dep"] and item["arr"]:
        score += 50
    if item["dep_cn"] and item["arr_cn"]:
        score += 20
    if item["reg"]:
        score += 10
    if item["model"]:
        score += 10
    if item["checkin_time"]:
        score += 10
    if item["checkin_place"]:
        score += 10
    if item["people_lines"]:
        score += 10
    return score


# =========================
# 主流程
# =========================
def collect_day_blocks(page):
    day_headers = get_day_headers(page)
    save_text("day_headers.txt", "\n".join(day_headers))

    result = []
    for idx, header in enumerate(day_headers):
        next_header = day_headers[idx + 1] if idx + 1 < len(day_headers) else None

        if not expand_day(page, header):
            continue

        try:
            day_block = get_day_block(page, header, next_header)
            cards = split_day_block_into_cards(day_block)
            raw_task_type = detect_task_type(day_block)

            key = safe_name(header)
            save_text(f"block_{key}.txt", day_block)
            save_text(f"cards_{key}.txt", "\n\n==========\n\n".join(cards))

            result.append({
                "day_header": header,
                "task_type": raw_task_type,
                "cards": cards,
            })
        finally:
            collapse_day(page, header)

    return result


def create_multi_calendars_from_blocks(day_blocks, page_year: int):
    buckets = {
        "flight": [],
        "positioning": [],
        "training": [],
        "ferry": [],
        "other": [],
    }
    best_events = {}

    for day in day_blocks:
        date_info = extract_date(day["day_header"], page_year)
        if not date_info:
            continue

        year, month, day_num = date_info
        task_type = day["task_type"]

        for card_text in day["cards"]:
            flight_no = extract_flight_no(card_text)
            reg, model = extract_reg_and_model(card_text)
            start_time, end_time = extract_start_end_time(card_text)
            checkin_time, checkin_place = extract_checkin(card_text)
            dep, arr, dep_cn, arr_cn = extract_airports(card_text)
            people_lines = extract_people_lines(card_text)

            if not flight_no or not start_time or not end_time:
                continue

            start_dt = make_datetime(year, month, day_num, start_time)
            end_dt = make_datetime(year, month, day_num, end_time)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            item = {
                "day_header": day["day_header"],
                "task_type": task_type,
                "flight_no": flight_no,
                "dep": dep,
                "arr": arr,
                "dep_cn": dep_cn,
                "arr_cn": arr_cn,
                "start_time": start_time,
                "end_time": end_time,
                "checkin_time": checkin_time,
                "checkin_place": checkin_place,
                "model": model,
                "reg": reg,
                "people_lines": people_lines,
                "start_dt": start_dt,
                "end_dt": end_dt,
            }

            group_key = (
                task_type,
                flight_no,
                start_dt.isoformat(),
                end_dt.isoformat(),
            )

            q = event_quality(item)
            item["quality"] = q

            if group_key not in best_events or q > best_events[group_key]["quality"]:
                best_events[group_key] = item

    for item in best_events.values():
        buckets[task_bucket(item["task_type"])].append(item)

    for key in buckets:
        buckets[key].sort(key=lambda x: (x["start_dt"], x["flight_no"]))

    changed_root = False

    changed_root |= write_calendar("flight.ics", buckets["flight"], preserve_existing=True)
    changed_root |= write_calendar("positioning.ics", buckets["positioning"], preserve_existing=True)
    changed_root |= write_calendar("training.ics", buckets["training"], preserve_existing=True)
    changed_root |= write_calendar("ferry.ics", buckets["ferry"], preserve_existing=True)
    changed_root |= write_calendar("other.ics", buckets["other"], preserve_existing=True)

    total_items = (
        buckets["flight"]
        + buckets["positioning"]
        + buckets["training"]
        + buckets["ferry"]
        + buckets["other"]
    )
    total_items.sort(key=lambda x: (x["start_dt"], x["flight_no"]))
    changed_root |= write_calendar("crew_schedule.ics", total_items, preserve_existing=True)

    # debug_output 只写本次结果，不保历史
    write_calendar(os.path.join(ARTIFACT_DIR, "flight.ics"), buckets["flight"], preserve_existing=False)
    write_calendar(os.path.join(ARTIFACT_DIR, "positioning.ics"), buckets["positioning"], preserve_existing=False)
    write_calendar(os.path.join(ARTIFACT_DIR, "training.ics"), buckets["training"], preserve_existing=False)
    write_calendar(os.path.join(ARTIFACT_DIR, "ferry.ics"), buckets["ferry"], preserve_existing=False)
    write_calendar(os.path.join(ARTIFACT_DIR, "other.ics"), buckets["other"], preserve_existing=False)
    write_calendar(os.path.join(ARTIFACT_DIR, "crew_schedule.ics"), total_items, preserve_existing=False)

    save_text("changed_root_flag.txt", str(changed_root))


def run():
    rebuild_airport_indexes()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.set_default_timeout(90000)
        page.set_default_navigation_timeout(90000)

        login(page, max_retries=10)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "after_login.png"), full_page=True)
        save_text("after_login.txt", page_text(page))

        open_mission_page(page)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "mission_page_ready.png"), full_page=True)
        save_text("mission_body_text.txt", page_text(page))

        page_year = detect_page_year(page)
        save_text("page_year.txt", str(page_year))

        day_blocks = collect_day_blocks(page)
        create_multi_calendars_from_blocks(day_blocks, page_year)

        context.close()
        browser.close()


if __name__ == "__main__":
    run()
