import os
import re
import io
import json
import base64
import shutil
import hashlib
import logging
from itertools import product
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, ImageFilter
import pytesseract
from playwright.sync_api import sync_playwright

try:
    import ddddocr  # type: ignore
    HAS_DDDDOCR = True
except Exception:
    HAS_DDDDOCR = False


LOGIN_URL = "https://cp.9cair.com"
MISSION_URL = "https://cp.9cair.com/html/task/mission.html"

USERNAME = os.environ.get("CREW_USERNAME") or os.environ.get("USERNAME")
PASSWORD = os.environ.get("CREW_PASSWORD") or os.environ.get("PASSWORD")

ARTIFACT_DIR = "debug_output"
AIRPORT_ALIASES_FILE = "airport_aliases.json"
SH_TZ = ZoneInfo("Asia/Shanghai")

HEADLESS = os.environ.get("HEADLESS", "1") != "0"
ALARM_MINUTES = 90
LOAD_MORE_MAX_ROUNDS = 8


if os.path.exists(ARTIFACT_DIR):
    shutil.rmtree(ARTIFACT_DIR)
os.makedirs(ARTIFACT_DIR, exist_ok=True)


def setup_logging():
    log_file = os.path.join(ARTIFACT_DIR, "execution.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)


logger = setup_logging()

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
    "扬州泰州": "ZSYZ",
    "厦门高崎": "ZSAM",
    "泉州晋江": "ZSQZ",
    "曼谷素旺那普": "VTBS",
    "曼谷素万那普": "VTBS",
    "金边德崇": "VDTI",
    "石家庄正定": "ZBSJ",
    "正定": "ZBSJ",
    "宁波栎社": "ZSNB",
    "栎社": "ZSNB",
    "天津滨海": "ZBTJ",
    "滨海": "ZBTJ",
    "东营胜利": "ZSDY",
    "东营": "ZSDY",
    "北京首都": "ZBAA",
    "北京大兴": "ZBAD",
    "成都天府": "ZUTF",
    "成都双流": "ZUUU",
    "昆明长水": "ZPPP",
    "武汉天河": "ZHHH",
    "南京禄口": "ZSNJ",
    "杭州萧山": "ZSHC",
    "青岛胶东": "ZSQD",
    "郑州新郑": "ZHCC",
    "长沙黄花": "ZGHA",
    "福州长乐": "ZSFZ",
    "沈阳桃仙": "ZYTX",
    "太原武宿": "ZBYN",
    "乌鲁木齐地窝堡": "ZWWW",
    "海口美兰": "ZJHK",
    "三亚凤凰": "ZJSY",
}

AIRPORT_CN_TO_ICAO = {}
AIRPORT_ICAO_TO_CN = {}
AIRPORT_NAMES = []

KNOWN_PEOPLE = [
    "段洋硕",
    "张子钦",
    "陈员",
    "康铁辉",
    "王闯",
    "许磊",
    "李罡",
    "杨刚",
    "鲍国际",
    "许晓君",
]

FLIGHT_NO_RE = re.compile(r"9C\d{3,4}[A-Z]?")
REG_MODEL_RE = re.compile(r"^B[0-9A-Z]{4,5}A(?:319|320|321)$")
REG_AND_MODEL_RE = re.compile(r"\b(B[0-9A-Z]{4,5})(A319|A320|A321)\b")
REG_ONLY_RE = re.compile(r"\bB[0-9A-Z]{4,5}\b")
MODEL_ONLY_RE = re.compile(r"\bA(?:319|320|321)\b")
TIME_RANGE_RE = re.compile(r"(\d{2}:\d{2})\s*[-~～—–]+\s*(\d{2}:\d{2})")
PAGE_YEAR_MONTH_RE = re.compile(r"(\d{4})年(\d{1,2})月")
PURE_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
ICAO_RE = re.compile(r"\b[A-Z]{4}\b")
DAY_HEADER_RE = re.compile(r"^\d{2}月\d{2}日\s*周.")
LATIN_PERSON_RE = re.compile(r"[A-Z][A-Z\s\.\-']{1,80}\([^)]*\)")
ZH_TAGGED_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}\([^)]*\)")
ZH_NAME_WITH_ROLE_RE = re.compile(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?")
SHORT_ROLE_RE = re.compile(r"\([A-Z]\)")

ROLE_WORDS = {"机长", "副驾驶", "乘务长", "随机人员", "加机组人员", "观察员"}
TRANSPORT_HINT_WORDS = ["搭乘", "乘坐", "火车", "高铁", "动车", "去", "前往", "至", "返回"]
TASK_TITLE_WORDS = {
    "理论课", "模拟机", "应急", "生存", "复训", "训练", "考勤", "检查",
    "定期", "熟练", "结合", "晋级", "考试", "安保", "程序",
    "停飞", "开会", "英语", "副驾驶", "机长", "乘务长", "随机人员",
    "加机组人员", "观察员", "检", "考", "协同", "签到", "劳动节", "立夏",
    "个起落",
}
GENERIC_TASK_WORDS = ["训练", "考勤", "摆渡", "置位", "航班", "备份", "待命", "停飞"]


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).replace("\u00a0", " ").replace("\r", "")
    text = text.replace("（", "(").replace("）", ")")
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
    text = text or ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", r"\;")
    text = text.replace(",", r"\,")
    text = text.replace("\n", r"\n")
    return text


def format_dt_local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def make_datetime_safe(year: int, month: int, day: int, hhmm: str):
    try:
        hh, mm = map(int, hhmm.split(":"))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None, False
        return datetime(year, month, day, hh, mm, tzinfo=SH_TZ), True
    except Exception:
        return None, False


def safe_name(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", s).strip("_") or "unnamed"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=8000)
    except Exception as e:
        logger.warning(f"页面文本读取失败: {type(e).__name__}: {str(e)[:200]}")
        return ""


def random_like_wait(page, base_ms: int, jitter_ms: int = 400):
    page.wait_for_timeout(base_ms + (hash(datetime.now().isoformat()) % max(1, jitter_ms)))


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
        temp_file = AIRPORT_ALIASES_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        if os.path.exists(AIRPORT_ALIASES_FILE):
            backup_file = AIRPORT_ALIASES_FILE + ".backup"
            try:
                shutil.copy(AIRPORT_ALIASES_FILE, backup_file)
            except Exception:
                pass
            os.remove(AIRPORT_ALIASES_FILE)
        os.rename(temp_file, AIRPORT_ALIASES_FILE)
    except Exception as e:
        logger.error(f"保存机场别名失败: {e}")


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
        if icao not in AIRPORT_ICAO_TO_CN or len(name) > len(AIRPORT_ICAO_TO_CN[icao]):
            AIRPORT_ICAO_TO_CN[icao] = name

    AIRPORT_NAMES = sorted(AIRPORT_CN_TO_ICAO.keys(), key=len, reverse=True)


def add_airport_alias(icao: str, alias: str):
    icao = normalize_text(icao).upper()
    alias = normalize_text(alias)
    if not re.fullmatch(r"[A-Z]{4}", icao):
        return
    if not alias or len(alias) < 2 or re.fullmatch(r"[A-Z]{4}", alias):
        return
    data = load_airport_aliases()
    aliases = data.get(icao, [])
    if alias not in aliases:
        aliases.append(alias)
        data[icao] = sorted(set(aliases), key=lambda x: (len(x), x))
        save_airport_aliases(data)
        rebuild_airport_indexes()


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


def expand_char_options(ch: str) -> list:
    mapping = {
        "0": ["0", "O"], "O": ["O", "0"],
        "1": ["1", "I", "L"], "I": ["I", "1", "L"], "L": ["L", "1", "I"],
        "5": ["5", "S"], "S": ["S", "5"],
        "8": ["8", "B"], "B": ["B", "8", "3"],
        "2": ["2", "Z"], "Z": ["Z", "2"],
        "6": ["6", "G"], "G": ["G", "6"],
        "3": ["3", "B"],
        "7": ["7", "T"], "T": ["T", "7"],
        "9": ["9", "G"],
        "4": ["4", "A"], "A": ["A", "4"],
    }
    return mapping.get(ch, [ch])


def generate_code_candidates(code: str, limit: int = 20) -> list:
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
    for i in range(imgs.count()):
        try:
            src = imgs.nth(i).get_attribute("src", timeout=1000)
            if src and src.startswith("data:image"):
                return base64.b64decode(src.split(",", 1)[1])
        except Exception:
            pass
    raise RuntimeError("未找到验证码图片")


def build_variants(img_bytes: bytes) -> list:
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img = ImageOps.autocontrast(img)
    variants = [
        ("base_x3", img.resize((img.width * 3, img.height * 3))),
        ("base_x4", img.resize((img.width * 4, img.height * 4))),
    ]
    for threshold in [135, 145, 155, 165, 175, 185]:
        bw = img.point(lambda x, t=threshold: 255 if x > t else 0, mode="1")
        bw = bw.resize((bw.width * 3, bw.height * 3))
        variants.append((f"bw_{threshold}", bw))
    variants.append(("invert_x3", ImageOps.invert(img).resize((img.width * 3, img.height * 3))))
    variants.append(("sharp_x3", img.filter(ImageFilter.SHARPEN).resize((img.width * 3, img.height * 3))))
    variants.append(("median_x3", img.filter(ImageFilter.MedianFilter(size=3)).resize((img.width * 3, img.height * 3))))
    return variants


def solve_captcha_with_ddddocr(img_bytes: bytes) -> str:
    if not HAS_DDDDOCR:
        return ""
    try:
        ocr = ddddocr.DdddOcr(show_ad=False)
        return normalize_candidate(ocr.classification(img_bytes))[:4]
    except Exception as e:
        logger.warning(f"ddddocr 识别失败，回退 pytesseract: {e}")
        return ""


def solve_captcha_with_tesseract(img_bytes: bytes, attempt_no: int = 0) -> str:
    variants = build_variants(img_bytes)
    configs = [
        r"--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        r"--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        r"--psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
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


def solve_captcha(page, attempt_no: int = 0) -> str:
    img_bytes = extract_captcha_bytes(page)
    save_bytes(f"captcha_attempt_{attempt_no}.png", img_bytes)
    if HAS_DDDDOCR:
        result = solve_captcha_with_ddddocr(img_bytes)
        if len(result) == 4:
            save_text(f"captcha_attempt_{attempt_no}_ddddocr.txt", result)
            return result
    return solve_captcha_with_tesseract(img_bytes, attempt_no=attempt_no)


def fill_login_form(page, code: str):
    inputs = page.locator("input")
    if inputs.count() < 3:
        raise RuntimeError("登录页输入框数量异常")
    inputs.nth(0).fill(USERNAME)
    inputs.nth(1).fill(PASSWORD)
    inputs.nth(2).fill(code)


def login(page, max_retries: int = 10):
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"登录尝试 {attempt}/{max_retries}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            random_like_wait(page, 4500, 1200)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, f"login_page_{attempt}.png"), full_page=True)
            save_text(f"login_page_{attempt}.txt", page_text(page))
        except Exception as e:
            logger.error(f"登录页加载失败: {e}")
            if attempt == max_retries:
                raise
            continue

        best_code = solve_captcha(page, attempt_no=attempt)
        if len(best_code) != 4:
            continue

        candidates = generate_code_candidates(best_code, limit=20)
        save_text(f"login_attempt_{attempt}_candidates.txt", "\n".join(candidates))
        for idx, cand in enumerate(candidates, start=1):
            try:
                fill_login_form(page, cand)
                try:
                    page.locator("text=Login").first.click(timeout=3000)
                except Exception:
                    try:
                        page.locator("button").first.click(timeout=3000)
                    except Exception:
                        page.keyboard.press("Enter")

                random_like_wait(page, 4200, 900)
                body_text = page_text(page)
                page.screenshot(
                    path=os.path.join(ARTIFACT_DIR, f"login_attempt_{attempt}_{idx}_{cand}.png"),
                    full_page=True,
                )
                save_text(f"login_attempt_{attempt}_{idx}_{cand}.txt", body_text)

                if ("统一认证中心" not in body_text) and ("Login" not in body_text):
                    logger.info(f"登录成功 (验证码: {cand})")
                    return

                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    random_like_wait(page, 2200, 700)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"验证码 {cand} 尝试失败: {e}")

    raise RuntimeError("多次尝试后仍无法登录")


def open_mission_page(page):
    for i in range(3):
        try:
            logger.info(f"打开任务页面 (尝试 {i + 1}/3)")
            page.goto(MISSION_URL, wait_until="domcontentloaded", timeout=90000)
            random_like_wait(page, 4500, 1200)

            try:
                page.locator("text=我的任务").first.click(timeout=5000)
                random_like_wait(page, 2600, 900)
            except Exception:
                pass

            body_text = page_text(page)
            if re.search(r"\d{2}月\d{2}日\s*周.", body_text):
                logger.info("任务页面已加载")
                return
        except Exception as e:
            logger.error(f"打开任务页面失败: {e}")
            if i == 2:
                raise

    raise RuntimeError("未能进入任务列表页")


def get_day_headers(page) -> list:
    text = page_text(page)
    headers = []
    for line in text.splitlines():
        line = normalize_text(line)
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


def get_load_more_labels(page) -> list:
    text = page_text(page)
    labels = []
    for line in text.splitlines():
        line = normalize_text(line)
        if "查看更多" in line:
            labels.append(line)
    return labels


def click_load_more(page) -> bool:
    try:
        loc = page.locator("text=查看更多")
        count = loc.count()
        if count == 0:
            return False
        target = loc.nth(count - 1)
        try:
            target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        random_like_wait(page, 500, 300)
        target.click(timeout=4000)
        random_like_wait(page, 1800, 900)
        return True
    except Exception as e:
        logger.info(f"点击查看更多失败: {e}")
        return False


def load_all_visible_tasks(page, max_rounds: int = LOAD_MORE_MAX_ROUNDS):
    prev_signature = None
    for round_no in range(1, max_rounds + 1):
        headers_before = get_day_headers(page)
        more_before = get_load_more_labels(page)
        save_text(f"load_round_{round_no}_headers_before.txt", "\n".join(headers_before))
        save_text(f"load_round_{round_no}_more_before.txt", "\n".join(more_before))
        logger.info(f"第 {round_no} 轮加载前: 日期头 {len(headers_before)} 个, 查看更多 {len(more_before)} 个")

        signature_before = (
            len(headers_before),
            tuple(headers_before[-10:]),
            len(more_before),
            tuple(more_before[-5:]),
        )
        if not more_before:
            logger.info("没有查看更多了")
            return

        if not click_load_more(page):
            logger.info("查看更多无法继续点击")
            return

        headers_after = get_day_headers(page)
        more_after = get_load_more_labels(page)
        save_text(f"load_round_{round_no}_headers_after.txt", "\n".join(headers_after))
        save_text(f"load_round_{round_no}_more_after.txt", "\n".join(more_after))
        logger.info(f"第 {round_no} 轮加载后: 日期头 {len(headers_after)} 个, 查看更多 {len(more_after)} 个")

        signature_after = (
            len(headers_after),
            tuple(headers_after[-10:]),
            len(more_after),
            tuple(more_after[-5:]),
        )
        if signature_after == signature_before or signature_after == prev_signature:
            logger.info("点了查看更多但页面签名没继续变化，停止扩展")
            return
        prev_signature = signature_after


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
        random_like_wait(page, 1500, 700)
    return ok


def collapse_day(page, header: str):
    try:
        ok = click_day_toggle(page, header)
        if ok:
            random_like_wait(page, 700, 300)
    except Exception:
        pass


def is_day_expanded(page, header: str) -> bool:
    body = page_text(page)
    start = body.find(header)
    if start == -1:
        return False
    after = body[start:start + 1200]
    if "航班动态" in after:
        return True
    if len(re.findall(r"\d{2}:\d{2}\s*[-~～—–]+\s*\d{2}:\d{2}", after)) >= 1:
        return True
    if FLIGHT_NO_RE.search(after):
        return True
    return False


def expand_day_with_retry(page, header: str, retries: int = 3) -> bool:
    for _ in range(retries):
        if expand_day(page, header):
            if is_day_expanded(page, header):
                return True
        random_like_wait(page, 600, 300)
    return False


def get_day_block(page, header: str, next_header: str | None) -> str:
    body_text_all = normalize_text(page.locator("body").inner_text())
    start = body_text_all.find(header)
    if start == -1:
        return ""
    if next_header:
        end = body_text_all.find(next_header, start + len(header))
        if end != -1:
            return body_text_all[start:end].strip()

    remaining = body_text_all[start:]
    lines = remaining.splitlines()
    result_lines = []
    for line in lines:
        line_stripped = normalize_text(line)
        if "查看更多" in line_stripped and re.search(r"\d{4}-\d{2}-\d{2}", line_stripped):
            break
        if DAY_HEADER_RE.match(line_stripped) and line_stripped != header:
            break
        result_lines.append(line)
    return "\n".join(result_lines).strip()


def detect_page_year(page) -> int:
    text = page_text(page)
    m = PAGE_YEAR_MONTH_RE.search(text)
    if m:
        return int(m.group(1))
    return datetime.now(SH_TZ).year


def is_day_header(line: str) -> bool:
    return DAY_HEADER_RE.match(line) is not None


def time_range_search(text: str):
    return TIME_RANGE_RE.search(text)


def split_prefix_time_suffix(line: str):
    m = TIME_RANGE_RE.search(line)
    if not m:
        return "", "", "", ""
    return (
        normalize_text(line[:m.start()]),
        m.group(1),
        m.group(2),
        normalize_text(line[m.end():]),
    )


def has_next_day_marker(text: str) -> bool:
    text = normalize_text(text)
    return any(x in text for x in ["(+1)", "（+1）", "＋1", "+1", "次日", "第二天", "翌日"])


def strip_time_from_title(title: str) -> str:
    title = TIME_RANGE_RE.sub("", title).strip()
    title = re.sub(r"[\s~～\-–—]+$", "", title).strip()
    return title


def detect_card_task_type(card_text: str, day_text: str, card_kind: str) -> str:
    combined = card_text + "\n" + day_text

    if "置位" in combined:
        return "置位"
    if "摆渡" in combined:
        return "摆渡"
    if "停飞" in combined or "Grounding" in combined:
        return "停飞"
    if "训练" in combined:
        return "训练"
    if "考勤" in combined:
        return "考勤"

    if card_kind == "flight":
        return "航班"

    for t in ["备份", "待命", "航班"]:
        if t in combined:
            return t
    return "其他"


def task_bucket(task_type: str) -> str:
    return {
        "航班": "flight",
        "置位": "positioning",
        "训练": "training",
        "摆渡": "ferry",
        "停飞": "other",
    }.get(task_type, "other")


def extract_date(text: str, page_year: int):
    m = re.search(r"(\d{2})月(\d{2})日", text)
    if not m:
        return None
    return page_year, int(m.group(1)), int(m.group(2))


def is_flight_line(s: str) -> bool:
    return FLIGHT_NO_RE.fullmatch(s) is not None


def is_reg_model_line(s: str) -> bool:
    return REG_MODEL_RE.fullmatch(s) is not None


def is_old_style_header_line(s: str) -> bool:
    s = normalize_text(s)
    return re.fullmatch(r"9C\d{3,4}[A-Z]?\s+B[0-9A-Z]{4,5}\s+A(?:319|A320|A321)", s) is not None


def clean_tail_noise(lines: list) -> list:
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


def looks_like_flight_chunk(chunk_lines: list) -> bool:
    chunk = "\n".join(chunk_lines)
    if not TIME_RANGE_RE.search(chunk):
        return False
    if FLIGHT_NO_RE.search(chunk):
        return True
    if "航班动态" in chunk:
        return True
    if REG_AND_MODEL_RE.search(chunk):
        return True
    if len(re.findall(r"\b[A-Z]{4}\b", chunk)) >= 2:
        return True
    return False


def split_day_block_into_cards(day_header: str, day_block: str) -> list:
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    lines = clean_tail_noise(lines)

    if lines and day_header in lines[0]:
        lines = lines[1:]
    if not lines:
        return []

    cards = []
    current = []

    def flush_current():
        nonlocal current, cards
        if not current:
            return
        chunk = clean_tail_noise(current)
        if not chunk:
            current = []
            return
        kind = "flight" if looks_like_flight_chunk(chunk) else "generic"
        cards.append({"kind": kind, "text": "\n".join(chunk).strip()})
        current = []

    for i, line in enumerate(lines):
        is_start = False

        if is_old_style_header_line(line) or is_flight_line(line):
            is_start = True
        elif TIME_RANGE_RE.search(line) and any(k in line for k in ["置位", "摆渡", "训练", "考勤", "停飞", "Grounding"]):
            is_start = True
        elif i > 0 and TIME_RANGE_RE.search(line):
            prev = lines[i - 1]
            if any(k in prev for k in ["理论课", "模拟机", "训练", "考勤", "停飞", "Grounding"]):
                is_start = True

        if is_start and current:
            flush_current()

        current.append(line)

    flush_current()

    merged = []
    for c in cards:
        if not c["text"]:
            continue
        if merged and merged[-1]["kind"] == "generic" and c["kind"] == "generic":
            merged[-1]["text"] += "\n" + c["text"]
        else:
            merged.append(c)

    return merged


def extract_icao_pairs_from_card(card_text: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    seq = []
    for line in lines:
        if ICAO_RE.fullmatch(line):
            seq.append(line)
        elif seq:
            break
    if len(seq) >= 2:
        return seq[0], seq[-1]

    all_icao = []
    for m in ICAO_RE.finditer(card_text):
        code = m.group(0)
        if code not in all_icao:
            all_icao.append(code)
    if len(all_icao) >= 2:
        return all_icao[0], all_icao[-1]
    return "", ""


def _extract_cn_route_from_card(card_text: str, dep_icao: str, arr_icao: str):
    dep_cn = ""
    arr_cn = ""
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    for line in lines:
        if "航班动态" in line or MODEL_ONLY_RE.fullmatch(line):
            continue
        for sep in ["→", "——", "-", "─"]:
            if sep not in line:
                continue
            left, right = line.split(sep, 1)
            left = normalize_text(TIME_RANGE_RE.sub("", left))
            right = normalize_text(TIME_RANGE_RE.sub("", right))
            left = normalize_text(REG_AND_MODEL_RE.sub("", left))
            right = normalize_text(REG_AND_MODEL_RE.sub("", right))
            left = normalize_text(REG_ONLY_RE.sub("", left))
            right = normalize_text(REG_ONLY_RE.sub("", right))
            left = normalize_text(MODEL_ONLY_RE.sub("", left))
            right = normalize_text(MODEL_ONLY_RE.sub("", right))
            if re.fullmatch(r"[\u4e00-\u9fff]{2,8}", left):
                left_icao = AIRPORT_CN_TO_ICAO.get(left, "")
                if left_icao == dep_icao or (not dep_cn and not left_icao):
                    dep_cn = left
            if re.fullmatch(r"[\u4e00-\u9fff]{2,8}", right):
                right_icao = AIRPORT_CN_TO_ICAO.get(right, "")
                if right_icao == arr_icao or (not arr_cn and not right_icao):
                    arr_cn = right
            if dep_cn or arr_cn:
                break
        if dep_cn and arr_cn:
            break
    return dep_cn, arr_cn


def resolve_airport_names(dep_icao: str, arr_icao: str, card_text: str, checkin_place: str = ""):
    dep_cn = AIRPORT_ICAO_TO_CN.get(dep_icao, "")
    arr_cn = AIRPORT_ICAO_TO_CN.get(arr_icao, "")
    if not dep_cn and checkin_place and re.fullmatch(r"[\u4e00-\u9fff]{2,12}", checkin_place):
        dep_cn = checkin_place
    if not dep_cn or not arr_cn:
        dep_cn2, arr_cn2 = _extract_cn_route_from_card(card_text, dep_icao, arr_icao)
        dep_cn = dep_cn or dep_cn2
        arr_cn = arr_cn or arr_cn2
    if dep_icao and dep_cn:
        add_airport_alias(dep_icao, dep_cn)
    if arr_icao and arr_cn:
        add_airport_alias(arr_icao, arr_cn)
    return dep_cn, arr_cn


def get_code_pair_from_day_block(day_block: str, flight_no: str):
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    lines = clean_tail_noise(lines)
    first_detail_idx = None
    for i in range(len(lines)):
        if i + 1 < len(lines) and is_flight_line(lines[i]) and is_reg_model_line(lines[i + 1]):
            first_detail_idx = i
            break
        if is_old_style_header_line(lines[i]):
            first_detail_idx = i
            break

    prefix_lines = lines[:first_detail_idx] if first_detail_idx is not None else lines
    flight_order = []
    codes = []
    for line in prefix_lines:
        if is_flight_line(line):
            flight_order.append(line)
        elif ICAO_RE.fullmatch(line):
            codes.append(line)

    if flight_no not in flight_order:
        return "", ""
    idx = flight_order.index(flight_no)
    if len(codes) >= idx + 2:
        return codes[idx], codes[idx + 1]
    return "", ""


def extract_airports(card_text: str, day_block: str, flight_no: str, checkin_place: str = ""):
    dep, arr = extract_icao_pairs_from_card(card_text)
    if not dep or not arr:
        dep2, arr2 = get_code_pair_from_day_block(day_block, flight_no)
        dep = dep or dep2
        arr = arr or arr2
    dep_cn, arr_cn = resolve_airport_names(dep, arr, card_text, checkin_place=checkin_place)
    return dep, arr, dep_cn, arr_cn


def extract_flight_no(card_text: str) -> str:
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    for line in lines:
        if is_flight_line(line):
            return line
        m = re.match(r"(9C\d{3,4}[A-Z]?)\s+B[0-9A-Z]{4,5}\s+A(?:319|320|321)", line)
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
    m_model = re.search(r"\b(A319|A320|A321)\b", card_text)
    if m_model:
        model = m_model.group(0)
    return reg, model


def extract_checkin(card_text: str):
    m = re.search(r"(\d{2}:\d{2})\s*([^\s]{2,30})\s*航班动态", card_text)
    if m:
        return m.group(1), m.group(2)

    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    for line in lines:
        if "航班动态" not in line:
            continue
        m_old = re.search(r"(\d{2}:\d{2})\s+([^\s]{2,30})", line)
        if not m_old:
            continue
        hhmm = m_old.group(1)
        place = m_old.group(2)
        if f"{hhmm}-" in line or f"{hhmm}~" in line or f"{hhmm}～" in line:
            continue
        if place in ["A319", "A320", "A321", "航班动态"]:
            continue
        if FLIGHT_NO_RE.fullmatch(place):
            continue
        return hhmm, place
    return "", ""


def extract_start_end_time(card_text: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    candidate_lines = []
    for line in lines:
        if "航班动态" in line:
            continue
        if FLIGHT_NO_RE.fullmatch(line) or is_old_style_header_line(line) or is_reg_model_line(line):
            continue
        if TIME_RANGE_RE.search(line):
            candidate_lines.append(line)
    if candidate_lines:
        m = TIME_RANGE_RE.search(candidate_lines[-1])
        if m:
            return m.group(1), m.group(2)
    all_matches = TIME_RANGE_RE.findall(card_text)
    if all_matches:
        return all_matches[-1][0], all_matches[-1][1]
    return "", ""


# =========================
# 名单解析底层逻辑（保守）
# =========================

def standardize_people_text(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return ""
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\([A-Z]\))", r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def has_clear_delimiters(text: str) -> bool:
    text = standardize_people_text(text)
    if not text:
        return False
    return any(sep in text for sep in [" ", "　", "、", "，", ",", "/", "\n", "\t"])


def split_by_clear_delimiters(text: str) -> list:
    text = standardize_people_text(text)
    if not text:
        return []
    parts = re.split(r"[\s　、，,/]+", text)
    return [normalize_text(x) for x in parts if normalize_text(x)]


def looks_like_person_token(token: str) -> bool:
    token = normalize_text(token)
    if not token:
        return False
    if token in ROLE_WORDS or token in TASK_TITLE_WORDS or token in GENERIC_TASK_WORDS:
        return False
    if token == "个起落":
        return False
    if LATIN_PERSON_RE.fullmatch(token):
        return True
    if ZH_TAGGED_NAME_RE.fullmatch(token):
        return True
    if ZH_NAME_WITH_ROLE_RE.fullmatch(token):
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token):
        return True
    return False


def normalize_people_output(items: list) -> list:
    out = []
    seen = set()
    for x in items:
        x = normalize_text(x)
        if not x:
            continue
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def contains_suspicious_half_name(token: str) -> bool:
    token = normalize_text(token)
    role = ""
    m_role = SHORT_ROLE_RE.search(token)
    if m_role:
        role = m_role.group(0)
        token = token.replace(role, "")

    if len(token) <= 1:
        return True

    risky_prefixes = {"段洋", "张子"}
    if token in risky_prefixes:
        return True

    return False


def score_compact_split(tokens: list) -> int:
    score = 0
    anchor_count = 0
    role_count = 0
    for t in tokens:
        base = t
        if SHORT_ROLE_RE.search(t):
            role_count += 1
            base = SHORT_ROLE_RE.sub("", t)
        if base in KNOWN_PEOPLE:
            anchor_count += 1
            score += 10
        if len(base) == 3:
            score += 4
        elif len(base) == 2:
            score += 2
        elif len(base) == 4:
            score += 1

    score += role_count * 3
    score += anchor_count * 5
    score -= max(0, len(tokens) - 3)
    return score


def compact_people_candidates(text: str) -> list:
    text = standardize_people_text(text)
    if not text:
        return []
    if len(text) > 16:
        return []
    if not re.fullmatch(r"[\u4e00-\u9fff()A-Z]+", text):
        return []

    anchor_tokens = set(KNOWN_PEOPLE)
    for name in KNOWN_PEOPLE:
        anchor_tokens.add(f"{name}(R)")

    memo = {}

    def dfs(idx: int):
        if idx == len(text):
            return [[]]
        if idx in memo:
            return memo[idx]

        res = []

        for tok in sorted(anchor_tokens, key=len, reverse=True):
            if text.startswith(tok, idx):
                for tail in dfs(idx + len(tok)):
                    res.append([tok] + tail)

        for ln in [2, 3, 4]:
            if idx + ln <= len(text):
                base = text[idx:idx + ln]
                if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", base):
                    for tail in dfs(idx + ln):
                        res.append([base] + tail)
                    role = "(R)"
                    if text.startswith(role, idx + ln):
                        for tail in dfs(idx + ln + len(role)):
                            res.append([base + role] + tail)

        memo[idx] = res
        return res

    all_splits = dfs(0)
    candidates = []

    for tokens in all_splits:
        if not tokens:
            continue
        if len(tokens) > 5:
            continue
        if "".join(tokens) != text:
            continue
        if not all(looks_like_person_token(x) for x in tokens):
            continue
        if any(contains_suspicious_half_name(x) for x in tokens):
            continue

        score = score_compact_split(tokens)
        candidates.append((score, tokens))

    unique = {}
    for score, tokens in candidates:
        key = tuple(tokens)
        if key not in unique or score > unique[key]:
            unique[key] = score

    ranked = sorted(unique.items(), key=lambda kv: kv[1], reverse=True)
    return [list(k) for k, _ in ranked]


def smart_split_short_compact_people(line: str) -> list:
    line = standardize_people_text(line)
    if not line:
        return []

    if len(line) > 16:
        return []

    if has_clear_delimiters(line):
        return []

    candidates = compact_people_candidates(line)
    if not candidates:
        return []

    best = candidates[0]
    if len(best) <= 1:
        return []

    has_anchor = any(SHORT_ROLE_RE.sub("", x) in KNOWN_PEOPLE for x in best)
    has_role = any(SHORT_ROLE_RE.search(x) for x in best)
    all_normal_zh = all(
        re.fullmatch(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?", x) for x in best
    )

    if has_anchor or has_role:
        return best

    if 2 <= len(best) <= 4 and all_normal_zh:
        pure_len = len(SHORT_ROLE_RE.sub("", line))
        if pure_len <= 10:
            return best

    return []


def parse_people_line_conservatively(line: str):
    line = standardize_people_text(line)
    if not line:
        return "skip", []

    if line in ROLE_WORDS:
        return "skip", []

    if is_day_header(line) or "查看更多" in line:
        return "skip", []

    if is_flight_line(line) or is_reg_model_line(line) or is_old_style_header_line(line):
        return "skip", []

    if ICAO_RE.fullmatch(line) or MODEL_ONLY_RE.fullmatch(line):
        return "skip", []

    if re.fullmatch(r"\d{2}:\d{2}", line):
        return "skip", []

    if line == "个起落":
        return "skip", []

    if LATIN_PERSON_RE.fullmatch(line) or ZH_TAGGED_NAME_RE.fullmatch(line):
        return "split", [line]

    if not has_clear_delimiters(line):
        micro = smart_split_short_compact_people(line)
        if micro:
            return "split", micro

        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?", line):
            if contains_suspicious_half_name(line):
                return "keep", [line]
            return "split", [line]

        if re.fullmatch(r"[\u4e00-\u9fff()A-Z]{4,80}", line):
            return "keep", [line]

        return "skip", []

    parts = split_by_clear_delimiters(line)
    if not parts:
        return "skip", []

    valid = [p for p in parts if looks_like_person_token(p) and not contains_suspicious_half_name(p)]
    if not valid:
        return "skip", []

    if len(valid) < len(parts):
        ratio = len(valid) / max(1, len(parts))
        if ratio < 0.8:
            return "keep", [line]

    if len(valid) <= 5:
        return "split", valid

    return "keep", [line]


def extract_people_lines_flight(card_text: str) -> list:
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    people = []
    capture = False

    for line in lines:
        if line in ROLE_WORDS:
            capture = True
            continue

        if not capture:
            continue

        if is_flight_line(line) or is_reg_model_line(line) or is_old_style_header_line(line):
            break

        if PURE_DATE_PREFIX_RE.match(line):
            break

        if "航班动态" in line or "查看更多" in line or time_range_search(line):
            continue

        if re.fullmatch(r"\d{2}:\d{2}", line) or len(line) == 1:
            continue

        mode, result = parse_people_line_conservatively(line)
        if mode in ("split", "keep"):
            people.extend(result)

    return normalize_people_output(people)


def _parse_ferry_route_from_description(desc: str):
    dep_cn = ""
    arr_cn = ""
    found_airports = []
    temp = desc
    for name in AIRPORT_NAMES:
        if name in temp:
            pos = temp.find(name)
            found_airports.append((pos, name))
            temp = temp.replace(name, "〇" * len(name), 1)
    found_airports.sort(key=lambda x: x[0])
    if len(found_airports) >= 2:
        return found_airports[0][1], found_airports[-1][1]

    for keyword in ["去", "前往", "至"]:
        if keyword in desc:
            left_part, right_part = desc.split(keyword, 1)
            for name in AIRPORT_NAMES:
                if name in left_part and not dep_cn:
                    dep_cn = name
                if name in right_part and not arr_cn:
                    arr_cn = name
            if dep_cn or arr_cn:
                return dep_cn, arr_cn
    return dep_cn, arr_cn


def is_probably_people_zone(line: str) -> bool:
    line = standardize_people_text(line)
    if not line:
        return False
    if line == "个起落":
        return False
    if any(w in line for w in TRANSPORT_HINT_WORDS):
        return False
    if any(w in line for w in TASK_TITLE_WORDS):
        return False
    if "地点" in line or "任务" in line or "事项" in line or "类型" in line:
        return False
    if re.search(r"[：:。，、]", line) and not has_clear_delimiters(line):
        return False

    mode, result = parse_people_line_conservatively(line)
    return mode in ("split", "keep") and bool(result)


def extract_people_lines_generic(lines: list, consumed_idx: set, title_text: str = "", location: str = ""):
    people = []
    extra_lines = []

    title_text = normalize_text(title_text)
    location = normalize_text(location)

    # 只认尾部连续名单区块，不再整块乱扫
    tail_candidates = []
    for idx in range(len(lines) - 1, -1, -1):
        if idx in consumed_idx:
            continue
        line = normalize_text(lines[idx])
        if not line:
            continue
        if is_probably_people_zone(line):
            tail_candidates.append((idx, line))
        else:
            if tail_candidates:
                break

    tail_candidates.reverse()
    consumed_people_idx = set()

    for idx, line in tail_candidates:
        mode, result = parse_people_line_conservatively(line)
        if mode in ("split", "keep"):
            people.extend(result)
            consumed_people_idx.add(idx)

    for idx, line in enumerate(lines):
        if idx in consumed_idx or idx in consumed_people_idx:
            continue

        line = normalize_text(line)
        if not line:
            continue

        if line in ROLE_WORDS or is_day_header(line) or "查看更多" in line:
            continue

        if is_flight_line(line) or is_reg_model_line(line) or is_old_style_header_line(line):
            continue

        if ICAO_RE.fullmatch(line) or MODEL_ONLY_RE.fullmatch(line):
            continue

        if re.fullmatch(r"\d{2}:\d{2}", line) or len(line) == 1:
            continue

        if title_text and line == title_text:
            continue

        if location and line == location:
            continue

        if any(x in line for x in TRANSPORT_HINT_WORDS):
            extra_lines.append(line)
            continue

        is_title_like = (
            len(line) > 8
            or any(w in line for w in TASK_TITLE_WORDS)
            or any(w in line for w in GENERIC_TASK_WORDS)
        )
        if is_title_like:
            extra_lines.append(line)

    people = normalize_people_output(people)
    extra_lines = normalize_people_output(extra_lines)
    return people, extra_lines


def parse_generic_card(card_text: str, day_header: str, page_year: int, day_task_text: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    if not lines:
        return None

    date_info = extract_date(day_header, page_year)
    if not date_info:
        return None
    year, month, day_num = date_info

    task_type = detect_card_task_type(card_text, day_task_text, "generic")
    title_text = ""
    location = ""
    start_time = ""
    end_time = ""
    dep = arr = dep_cn = arr_cn = ""
    reg = ""
    model = ""
    consumed_idx = set()
    next_day = has_next_day_marker(card_text)

    for line in lines:
        m_model = MODEL_ONLY_RE.search(line)
        if m_model and not model:
            model = m_model.group(0)
        m_reg = REG_ONLY_RE.search(line)
        if m_reg and not reg:
            reg = m_reg.group(0)

    time_line_idx = None
    time_line_prefix = ""
    for idx, line in enumerate(lines):
        prefix, st, et, suffix = split_prefix_time_suffix(line)
        if st and et:
            time_line_idx = idx
            start_time, end_time = st, et
            time_line_prefix = prefix
            if suffix:
                location = suffix
            if has_next_day_marker(line):
                next_day = True
            consumed_idx.add(idx)
            break

    if time_line_idx is not None and time_line_idx > 0:
        for look_back in range(time_line_idx - 1, -1, -1):
            candidate = lines[look_back]
            if is_day_header(candidate) or ICAO_RE.fullmatch(candidate) or MODEL_ONLY_RE.fullmatch(candidate):
                continue
            if re.search(r"[\u4e00-\u9fffA-Za-z]", candidate):
                title_text = strip_time_from_title(candidate)
                consumed_idx.add(look_back)
                break

    if not title_text and time_line_prefix:
        title_text = strip_time_from_title(time_line_prefix)

    dep_icao_seq = [line for line in lines if ICAO_RE.fullmatch(line)]
    if len(dep_icao_seq) >= 2:
        dep = dep_icao_seq[0]
        arr = dep_icao_seq[-1]
        dep_cn = AIRPORT_ICAO_TO_CN.get(dep, "")
        arr_cn = AIRPORT_ICAO_TO_CN.get(arr, "")

    if not dep_cn or not arr_cn:
        for line in lines:
            if any(x in line for x in TRANSPORT_HINT_WORDS):
                dep_cn2, arr_cn2 = _parse_ferry_route_from_description(line)
                dep_cn = dep_cn or dep_cn2
                arr_cn = arr_cn or arr_cn2
                if dep_cn or arr_cn:
                    break

    if dep and dep_cn:
        add_airport_alias(dep, dep_cn)
    if arr and arr_cn:
        add_airport_alias(arr, arr_cn)

    if dep_cn and arr_cn:
        route_title = f"{dep_cn}→{arr_cn}"
        if task_type == "摆渡":
            title_text = route_title
        elif not title_text:
            title_text = route_title
    elif dep and arr and not title_text:
        title_text = f"{dep}→{arr}"

    if not title_text:
        for line in lines:
            line_clean = strip_time_from_title(line)
            if line_clean and line_clean not in TASK_TITLE_WORDS and not ICAO_RE.fullmatch(line_clean) and not MODEL_ONLY_RE.fullmatch(line_clean):
                title_text = line_clean
                break

    people_lines, extra_lines = extract_people_lines_generic(lines, consumed_idx, title_text=title_text, location=location)

    # 停飞一律不抓名单
    if task_type == "停飞":
        people_lines = []

    if not start_time or not end_time:
        return None

    start_dt, valid_start = make_datetime_safe(year, month, day_num, start_time)
    end_dt, valid_end = make_datetime_safe(year, month, day_num, end_time)
    if not valid_start or not valid_end:
        return None

    diff_minutes = (end_dt - start_dt).total_seconds() / 60
    if next_day or diff_minutes < 0:
        end_dt += timedelta(days=1)

    return {
        "day_header": day_header,
        "task_type": task_type,
        "flight_no": "",
        "title_text": title_text or task_type,
        "dep": dep,
        "arr": arr,
        "dep_cn": dep_cn,
        "arr_cn": arr_cn,
        "start_time": start_time,
        "end_time": end_time,
        "checkin_time": "",
        "checkin_place": "",
        "location": location,
        "model": model,
        "reg": reg,
        "people_lines": people_lines,
        "extra_lines": extra_lines,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "raw_card_text": normalize_text(card_text),
    }


def parse_flight_card(card_text: str, day_header: str, page_year: int, day_task_text: str):
    date_info = extract_date(day_header, page_year)
    if not date_info:
        return None
    year, month, day_num = date_info

    flight_no = extract_flight_no(card_text)
    reg, model = extract_reg_and_model(card_text)
    start_time, end_time = extract_start_end_time(card_text)
    checkin_time, checkin_place = extract_checkin(card_text)
    dep, arr, dep_cn, arr_cn = extract_airports(card_text, day_task_text, flight_no, checkin_place=checkin_place)
    people_lines = extract_people_lines_flight(card_text)
    task_type = detect_card_task_type(card_text, day_task_text, "flight")
    next_day = has_next_day_marker(card_text)

    if not flight_no or not start_time or not end_time:
        return None

    start_dt, valid_start = make_datetime_safe(year, month, day_num, start_time)
    end_dt, valid_end = make_datetime_safe(year, month, day_num, end_time)
    if not valid_start or not valid_end:
        return None

    diff_minutes = (end_dt - start_dt).total_seconds() / 60
    if next_day or diff_minutes < 0:
        end_dt += timedelta(days=1)

    return {
        "day_header": day_header,
        "task_type": task_type,
        "flight_no": flight_no,
        "title_text": "",
        "dep": dep,
        "arr": arr,
        "dep_cn": dep_cn,
        "arr_cn": arr_cn,
        "start_time": start_time,
        "end_time": end_time,
        "checkin_time": checkin_time,
        "checkin_place": checkin_place,
        "location": checkin_place,
        "model": model,
        "reg": reg,
        "people_lines": people_lines,
        "extra_lines": [],
        "start_dt": start_dt,
        "end_dt": end_dt,
        "raw_card_text": normalize_text(card_text),
    }


def title_icon(task_type: str) -> str:
    return {
        "航班": "✈️",
        "置位": "📍",
        "训练": "🎓",
        "摆渡": "🚐",
        "备份": "🗂",
        "待命": "🕒",
        "考勤": "📋",
        "停飞": "📋",
        "其他": "🗂",
    }.get(task_type, "🗂")


def build_title(item: dict) -> str:
    icon = title_icon(item["task_type"])
    flight_no = item["flight_no"]
    dep_cn = item["dep_cn"]
    arr_cn = item["arr_cn"]
    dep = item["dep"]
    arr = item["arr"]
    title_text = item.get("title_text", "").strip()
    cross_day = item["end_dt"].date() > item["start_dt"].date()
    suffix = "(+1)" if cross_day else ""

    if flight_no:
        if dep_cn and arr_cn:
            return f"{icon} {flight_no} {dep_cn}→{arr_cn}{suffix}"
        if dep_cn and arr:
            return f"{icon} {flight_no} {dep_cn}→{arr}{suffix}"
        if dep and arr_cn:
            return f"{icon} {flight_no} {dep}→{arr_cn}{suffix}"
        if dep and arr:
            return f"{icon} {flight_no} {dep}-{arr}{suffix}"
        return f"{icon} {flight_no}"

    if item["task_type"] == "停飞":
        clean_title = re.sub(r"\s*00:00\s*[~～\-–—]\s*(17:30|23:59)\s*$", "", title_text).strip()
        if clean_title:
            return f"{icon} {clean_title}"
        return f"{icon} 停飞 Grounding"

    if dep_cn and arr_cn:
        return f"{icon} {dep_cn}→{arr_cn}{suffix}"
    if dep and arr:
        return f"{icon} {dep}→{arr}{suffix}"
    if title_text:
        return f"{icon} {title_text}"
    return f"{icon} {item['task_type']}"


def build_description(item: dict) -> str:
    lines = [item["day_header"], f"类型：{item['task_type']}"]

    if item["flight_no"]:
        lines.append(f"航班：{item['flight_no']}")
    elif item.get("title_text"):
        lines.append(f"事项：{item['title_text']}")

    if item["dep_cn"] and item["arr_cn"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"航线：{item['dep_cn']} → {item['arr_cn']}{cross}")
    elif item["dep"] and item["arr"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"航线：{item['dep']} → {item['arr']}{cross}")

    if item["location"]:
        lines.append(f"地点：{item['location']}")

    if item["checkin_time"] and item["checkin_place"]:
        lines.append(f"签到：{item['checkin_time']}｜{item['checkin_place']}")
    elif item["checkin_time"]:
        lines.append(f"签到：{item['checkin_time']}")

    lines.append(f"任务：{item['start_time']} - {item['end_time']}")

    if item["model"] and item["reg"]:
        lines.append(f"机型：{item['model']}｜注册号：{item['reg']}")
    elif item["model"]:
        lines.append(f"机型：{item['model']}")
    elif item["reg"]:
        lines.append(f"注册号：{item['reg']}")

    if item["extra_lines"]:
        lines.append("")
        lines.append("说明：")
        for x in item["extra_lines"]:
            lines.append(f"• {x}")

    if item["people_lines"]:
        lines.append("")
        lines.append("人员名单：")
        for p in item["people_lines"]:
            lines.append(f"• {p}")

    return "\n".join(lines)


def stable_uid_seed(item: dict) -> str:
    """
    用原始卡片文本做稳定身份，避免字段修正时 UID 变化。
    """
    raw_card = normalize_text(item.get("raw_card_text", ""))
    date_key = item["start_dt"].strftime("%Y-%m-%d")
    seed = f"{item['day_header']}|{date_key}|{raw_card}"
    return stable_hash(seed)[:32]


def exact_content_signature(item: dict) -> str:
    payload = {
        "task_type": item["task_type"],
        "flight_no": item["flight_no"],
        "title_text": item.get("title_text", ""),
        "start_dt": item["start_dt"].isoformat(),
        "end_dt": item["end_dt"].isoformat(),
        "dep": item["dep"],
        "arr": item["arr"],
        "dep_cn": item["dep_cn"],
        "arr_cn": item["arr_cn"],
        "location": item["location"],
        "checkin_time": item["checkin_time"],
        "checkin_place": item["checkin_place"],
        "model": item["model"],
        "reg": item["reg"],
        "people_lines": item["people_lines"],
        "extra_lines": item["extra_lines"],
    }
    return stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:32]


def build_vevent(item: dict, version_tag: str = "") -> str:
    title = build_title(item)
    desc = build_description(item)
    if version_tag:
        desc = f"{desc}\n\n版本：{version_tag}"

    alarm_desc = f"{item['flight_no']} 签到提醒" if item["flight_no"] else f"{item.get('title_text', '任务')} 提醒"
    uid_base = stable_uid_seed(item)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid_base}@crew-calendar",
        f"SUMMARY:{escape_ics_text(title)}",
        f"DTSTART;TZID=Asia/Shanghai:{format_dt_local(item['start_dt'])}",
        f"DTEND;TZID=Asia/Shanghai:{format_dt_local(item['end_dt'])}",
        f"DESCRIPTION:{escape_ics_text(desc)}",
        f"X-CONTENT-SIGNATURE:{exact_content_signature(item)}",
    ]
    if item["location"]:
        lines.append(f"LOCATION:{escape_ics_text(item['location'])}")
    lines.extend([
        "BEGIN:VALARM",
        f"TRIGGER:-PT{ALARM_MINUTES}M",
        f"DESCRIPTION:{escape_ics_text(alarm_desc)}",
        "ACTION:DISPLAY",
        "END:VALARM",
        "END:VEVENT",
    ])
    return "\n".join(lines)


def extract_uid_from_vevent(vevent: str) -> str:
    m = re.search(r"^UID:(.+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else ""


def extract_summary_from_vevent(vevent: str) -> str:
    m = re.search(r"^SUMMARY:(.+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else ""


def extract_dtstart_from_vevent(vevent: str) -> str:
    m = re.search(r"^DTSTART(?:;[^:]+)?:([0-9T]+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def extract_dtend_from_vevent(vevent: str) -> str:
    m = re.search(r"^DTEND(?:;[^:]+)?:([0-9T]+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def extract_event_date_from_block(block: str) -> str:
    dt = extract_dtstart_from_vevent(block)
    return dt[:8] if len(dt) >= 8 else ""


def normalize_similarity_title(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\s*00:00\s*[~～\-–—]\s*(17:30|23:59)", "", text)
    text = text.replace(" ", "")
    return text


def are_high_confidence_duplicates(block_a: str, block_b: str) -> bool:
    if extract_dtstart_from_vevent(block_a) != extract_dtstart_from_vevent(block_b):
        return False
    if extract_dtend_from_vevent(block_a) != extract_dtend_from_vevent(block_b):
        return False

    sa = normalize_similarity_title(extract_summary_from_vevent(block_a))
    sb = normalize_similarity_title(extract_summary_from_vevent(block_b))
    if not sa or not sb:
        return False
    if sa == sb:
        return True

    fa = FLIGHT_NO_RE.search(sa)
    fb = FLIGHT_NO_RE.search(sb)
    if fa and fb and fa.group(0) == fb.group(0):
        return True

    return False


def block_quality(block: str) -> int:
    score = 0
    summary = normalize_text(extract_summary_from_vevent(block))
    score += len(summary)
    if "航班" in block:
        score += 10
    if "地点：" in block:
        score += 10
    if "航线：" in block:
        score += 10
    if "签到：" in block:
        score += 10
    if "机型：" in block:
        score += 10
    if "人员名单：" in block:
        score += 10
    return score


def cleanup_duplicate_blocks(blocks: list) -> list:
    groups = {}
    for block in blocks:
        key = (extract_dtstart_from_vevent(block), extract_dtend_from_vevent(block))
        groups.setdefault(key, []).append(block)

    final_blocks = []
    for _, group in groups.items():
        if len(group) == 1:
            final_blocks.extend(group)
            continue

        used = set()
        for i, a in enumerate(group):
            if i in used:
                continue
            cluster = [a]
            used.add(i)
            for j in range(i + 1, len(group)):
                if j in used:
                    continue
                b = group[j]
                if are_high_confidence_duplicates(a, b):
                    cluster.append(b)
                    used.add(j)

            best = max(cluster, key=block_quality)
            final_blocks.append(best)

    final_blocks.sort(key=lambda x: (extract_dtstart_from_vevent(x), extract_uid_from_vevent(x)))
    return final_blocks


def event_quality(item: dict) -> int:
    score = 0
    if item["flight_no"]:
        score += 30
    if item["dep"] or item["dep_cn"]:
        score += 10
    if item["arr"] or item["arr_cn"]:
        score += 10
    if item["dep_cn"] and item["arr_cn"]:
        score += 10
    if item["reg"]:
        score += 10
    if item["model"]:
        score += 10
    if item["checkin_time"]:
        score += 10
    if item["checkin_place"]:
        score += 10
    if item["location"]:
        score += 10
    if item["people_lines"]:
        score += 10
    if item.get("title_text"):
        score += 10
    return score


def read_existing_events(filename: str) -> dict:
    existing = {}
    if not os.path.exists(filename):
        return existing
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = re.findall(r"BEGIN:VEVENT\s.*?END:VEVENT", content, flags=re.S)
        for block in blocks:
            uid = extract_uid_from_vevent(block.strip())
            if uid:
                existing[uid] = block.strip()
    except Exception as e:
        logger.warning(f"读取现有事件失败: {e}")
    return existing


def write_calendar_from_vevents(filename: str, vevents: list) -> bool:
    unique = {}
    for block in vevents:
        uid = extract_uid_from_vevent(block)
        if uid:
            unique[uid] = block.strip()

    ordered = sorted(
        unique.values(),
        key=lambda x: (extract_dtstart_from_vevent(x), extract_uid_from_vevent(x)),
    )

    content = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Crew Calendar//CN"]
    content.extend(ordered)
    content.append("END:VCALENDAR")
    final_text = "\n".join(content)

    old_text = None
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                old_text = f.read()
        except Exception:
            pass

    if old_text == final_text:
        logger.info(f"{filename} 内容未变化")
        return False

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_text)
    logger.info(f"写入 {filename}: {len(ordered)} 个事件")
    return True


def prepare_items(day_blocks, page_year: int) -> list:
    raw_items = []
    for day in day_blocks:
        day_header = day["day_header"]
        day_block = day["day_block"]
        for card in day["cards"]:
            if card["kind"] == "flight":
                item = parse_flight_card(card["text"], day_header, page_year, day_block)
            else:
                item = parse_generic_card(card["text"], day_header, page_year, day_block)
            if item:
                raw_items.append(item)

    best_map = {}
    for item in raw_items:
        key = exact_content_signature(item)
        q = event_quality(item)
        item["quality"] = q
        if key not in best_map or q > best_map[key]["quality"]:
            best_map[key] = item

    items = list(best_map.values())
    items.sort(key=lambda x: (x["start_dt"], build_title(x)))
    return items


def build_version_tag() -> str:
    return datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M")


def merge_history_replace_scraped_dates(filename: str, bucket_items: list) -> list:
    existing_map = read_existing_events(filename)
    existing_blocks = list(existing_map.values())
    new_blocks = [build_vevent(item, version_tag=build_version_tag()) for item in bucket_items]

    scraped_dates = set()
    for item in bucket_items:
        scraped_dates.add(item["start_dt"].strftime("%Y%m%d"))

    kept_old_blocks = []
    for block in existing_blocks:
        event_date = extract_event_date_from_block(block)
        if event_date in scraped_dates:
            continue
        kept_old_blocks.append(block)

    merged_blocks = kept_old_blocks + new_blocks
    return cleanup_duplicate_blocks(merged_blocks)


def create_multi_calendars_from_blocks(day_blocks, page_year: int):
    items = prepare_items(day_blocks, page_year)
    version_tag = build_version_tag()

    buckets = {
        "flight": [],
        "positioning": [],
        "training": [],
        "ferry": [],
        "other": [],
    }

    for item in items:
        buckets[task_bucket(item["task_type"])].append(item)

    total_items = (
        buckets["flight"]
        + buckets["positioning"]
        + buckets["training"]
        + buckets["ferry"]
        + buckets["other"]
    )
    total_items.sort(key=lambda x: (x["start_dt"], build_title(x)))

    changed_root = False

    changed_root |= write_calendar_from_vevents(
        "flight.ics",
        merge_history_replace_scraped_dates("flight.ics", buckets["flight"])
    )
    changed_root |= write_calendar_from_vevents(
        "positioning.ics",
        merge_history_replace_scraped_dates("positioning.ics", buckets["positioning"])
    )
    changed_root |= write_calendar_from_vevents(
        "training.ics",
        merge_history_replace_scraped_dates("training.ics", buckets["training"])
    )
    changed_root |= write_calendar_from_vevents(
        "ferry.ics",
        merge_history_replace_scraped_dates("ferry.ics", buckets["ferry"])
    )
    changed_root |= write_calendar_from_vevents(
        "other.ics",
        merge_history_replace_scraped_dates("other.ics", buckets["other"])
    )
    changed_root |= write_calendar_from_vevents(
        "crew_schedule.ics",
        merge_history_replace_scraped_dates("crew_schedule.ics", total_items)
    )

    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "flight.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["flight"]],
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "positioning.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["positioning"]],
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "training.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["training"]],
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "ferry.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["ferry"]],
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "other.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["other"]],
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "crew_schedule.ics"),
        [build_vevent(item, version_tag=version_tag) for item in total_items]],
    )

    save_text("changed_root_flag.txt", str(changed_root))
    logger.info(f"本次抓到 {len(total_items)} 个任务；已对本次抓到日期做整日替换，避免旧脏事件残留")


def collect_day_blocks(page) -> list:
    load_all_visible_tasks(page)

    day_headers = get_day_headers(page)
    save_text("day_headers.txt", "\n".join(day_headers))

    result = []
    for idx, header in enumerate(day_headers):
        next_header = day_headers[idx + 1] if idx + 1 < len(day_headers) else None

        if not expand_day_with_retry(page, header):
            logger.warning(f"日期 {header} 展开失败")
            continue

        try:
            day_block = get_day_block(page, header, next_header)
            cards = split_day_block_into_cards(header, day_block)
            key = safe_name(header)
            save_text(f"block_{key}.txt", day_block)
            save_text(
                f"cards_{key}.txt",
                "\n\n==========\n\n".join([f"[{c['kind']}]\n{c['text']}" for c in cards]),
            )
            result.append({"day_header": header, "day_block": day_block, "cards": cards})
        except Exception as e:
            logger.error(f"处理日期 {header} 失败: {e}")
        finally:
            collapse_day(page, header)

    logger.info(f"收集了 {len(result)} 个日期的数据")
    return result


def snapshot_existing_calendars():
    backups = []
    for name in ["crew_schedule.ics", "flight.ics", "ferry.ics", "training.ics", "positioning.ics", "other.ics"]:
        if os.path.exists(name):
            backup_path = os.path.join(ARTIFACT_DIR, f"backup_{name}")
            shutil.copy(name, backup_path)
            backups.append(name)
    save_text("backed_up_files.txt", "\n".join(backups))


def run():
    logger.info("=" * 60)
    logger.info("开始执行航班日历爬虫")
    logger.info("=" * 60)

    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少环境变量：CREW_USERNAME / CREW_PASSWORD")

    snapshot_existing_calendars()
    rebuild_airport_indexes()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(90000)
        page.set_default_navigation_timeout(90000)

        try:
            login(page, max_retries=10)

            page.screenshot(path=os.path.join(ARTIFACT_DIR, "after_login.png"), full_page=True)
            save_text("after_login.txt", page_text(page))

            open_mission_page(page)

            page.screenshot(path=os.path.join(ARTIFACT_DIR, "mission_page_ready.png"), full_page=True)
            save_text("mission_body_text.txt", page_text(page))

            page_year = detect_page_year(page)
            save_text("page_year.txt", str(page_year))
            logger.info(f"页面年份: {page_year}")

            day_blocks = collect_day_blocks(page)
            if not day_blocks:
                raise RuntimeError("未抓到任何任务块，停止写入，保护现有 ICS")

            create_multi_calendars_from_blocks(day_blocks, page_year)

            logger.info("=" * 60)
            logger.info("执行完成！")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"执行出错: {e}", exc_info=True)
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
