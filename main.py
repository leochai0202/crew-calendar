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


LOGIN_URL = "https://cp.9cair.com"
MISSION_URL = "https://cp.9cair.com/html/task/mission.html"

USERNAME = os.environ.get("CREW_USERNAME") or os.environ.get("USERNAME")
PASSWORD = os.environ.get("CREW_PASSWORD") or os.environ.get("PASSWORD")

ARTIFACT_DIR = "debug_output"
AIRPORT_ALIASES_FILE = "airport_aliases.json"
SH_TZ = ZoneInfo("Asia/Shanghai")

MAX_DAYS = 7
HEADLESS = os.environ.get("HEADLESS", "1") != "0"


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
            logging.StreamHandler()
        ]
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
}

AIRPORT_CN_TO_ICAO = {}
AIRPORT_ICAO_TO_CN = {}
AIRPORT_NAMES = []

KNOWN_PEOPLE = [
    "段洋硕",
]

COMMON_SURNAMES = {
    "赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈", "褚", "卫", "蒋", "沈", "韩", "杨",
    "朱", "秦", "尤", "许", "何", "吕", "施", "张", "孔", "曹", "严", "华", "金", "魏", "陶", "姜",
    "戚", "谢", "邹", "喻", "柏", "水", "窦", "章", "云", "苏", "潘", "葛", "奚", "范", "彭", "郎",
    "鲁", "韦", "昌", "马", "苗", "凤", "花", "方", "俞", "任", "袁", "柳", "酆", "鲍", "史", "唐",
    "费", "廉", "岑", "薛", "雷", "贺", "倪", "汤", "滕", "殷", "罗", "毕", "郝", "邬", "安", "常",
    "乐", "于", "时", "傅", "皮", "卞", "齐", "康", "伍", "余", "元", "卜", "顾", "孟", "平", "黄",
    "和", "穆", "萧", "尹", "姚", "邵", "湛", "汪", "祁", "毛", "禹", "狄", "米", "贝", "明", "臧",
    "计", "伏", "成", "戴", "谈", "宋", "茅", "庞", "熊", "纪", "舒", "屈", "项", "祝", "董", "梁",
    "杜", "阮", "蓝", "闵", "席", "季", "麻", "强", "贾", "路", "娄", "危", "江", "童", "颜", "郭",
    "梅", "盛", "林", "刁", "钟", "徐", "丘", "骆", "高", "夏", "蔡", "田", "樊", "胡", "凌", "霍",
    "虞", "万", "支", "柯", "昝", "管", "卢", "莫", "经", "房", "裘", "缪", "干", "解", "应", "宗",
    "丁", "宣", "贲", "邓", "郁", "单", "杭", "洪", "包", "诸", "左", "石", "崔", "吉", "钮", "龚",
    "程", "嵇", "邢", "滑", "裴", "陆", "荣", "翁", "荀", "羊", "於", "惠", "甄", "曲", "家", "封",
    "芮", "羿", "储", "靳", "汲", "邴", "糜", "松", "井", "段", "富", "巫", "乌", "焦", "巴", "弓",
    "牧", "隗", "山", "谷", "车", "侯", "宓", "蓬", "全", "郗", "班", "仰", "秋", "仲", "伊", "宫",
    "宁", "仇", "栾", "暴", "甘", "钭", "厉", "戎", "祖", "武", "符", "刘", "景", "詹", "束", "龙",
    "叶", "幸", "司", "韶", "郜", "黎", "蓟", "薄", "印", "宿", "白", "怀", "蒲", "台", "从", "鄂",
    "索", "咸", "籍", "赖", "卓", "蔺", "屠", "蒙", "池", "乔", "阴", "郁", "胥", "能", "苍", "双"
}

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
GENERIC_TASK_WORDS = ["训练", "考勤", "摆渡", "置位", "航班", "备份", "待命"]
LATIN_PERSON_RE = re.compile(r"[A-Z][A-Z\s\.\-']{1,80}\([^)]*\)")
TRANSPORT_HINT_WORDS = ["搭乘", "乘坐", "火车", "高铁", "动车", "去", "前往", "至", "返回"]
ROLE_WORDS = {"机长", "副驾驶", "乘务长", "随机人员", "加机组人员"}
GENERIC_SKIP_WORDS = {
    "理论课", "应急", "生存", "复训", "模拟机", "定期复", "训练结合", "熟练", "检查",
    "检", "考", "理论", "课程", "复习", "训练课", "定期", "结合"
}


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
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
        if not hhmm or not isinstance(hhmm, str):
            return None, False
        parts = hhmm.split(":")
        if len(parts) != 2:
            return None, False
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None, False
        dt = datetime(year, month, day, hh, mm, tzinfo=SH_TZ)
        return dt, True
    except (ValueError, TypeError):
        return None, False


def safe_name(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", s).strip("_") or "unnamed"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=8000)
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:200]
        logger.warning(f"页面文本读取失败: {error_type}: {error_msg}")
        try:
            with open(os.path.join(ARTIFACT_DIR, "page_text_errors.log"), "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now(SH_TZ).isoformat()}] {error_type}: {error_msg}\n")
        except Exception:
            pass
        return ""


def is_day_header(line: str) -> bool:
    return DAY_HEADER_RE.match(line) is not None


def time_range_search(text: str):
    return TIME_RANGE_RE.search(text)


def split_prefix_time_suffix(line: str):
    m = TIME_RANGE_RE.search(line)
    if not m:
        return "", "", "", ""
    start_time = m.group(1)
    end_time = m.group(2)
    prefix = normalize_text(line[:m.start()])
    suffix = normalize_text(line[m.end():])
    return prefix, start_time, end_time, suffix


def has_next_day_marker(text: str) -> bool:
    text = normalize_text(text)
    markers = ["(+1)", "（+1）", "＋1", "+1", "次日", "第二天", "翌日"]
    return any(m in text for m in markers)


def load_airport_aliases():
    if not os.path.exists(AIRPORT_ALIASES_FILE):
        return {}

    try:
        with open(AIRPORT_ALIASES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        backup_file = AIRPORT_ALIASES_FILE + ".backup"
        if os.path.exists(backup_file):
            try:
                with open(backup_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    logger.info("从备份文件恢复机场别名")
                    return data
            except Exception:
                pass
    except Exception as e:
        logger.error(f"加载机场别名失败: {e}")

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

        if os.path.exists(AIRPORT_ALIASES_FILE):
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
        if icao not in AIRPORT_ICAO_TO_CN:
            AIRPORT_ICAO_TO_CN[icao] = name

    AIRPORT_NAMES = sorted(AIRPORT_CN_TO_ICAO.keys(), key=len, reverse=True)


def add_airport_alias(icao: str, alias: str):
    icao = normalize_text(icao).upper()
    alias = normalize_text(alias)

    if not re.fullmatch(r"[A-Z]{4}", icao):
        return
    if not alias or len(alias) < 2:
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
    count = imgs.count()
    for i in range(count):
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


def login(page, max_retries: int = 10):
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"登录尝试 {attempt}/{max_retries}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, f"login_page_{attempt}.png"), full_page=True)
            save_text(f"login_page_{attempt}.txt", page_text(page))
        except Exception as e:
            logger.error(f"登录页加载失败: {e}")
            if attempt == max_retries:
                raise
            page.wait_for_timeout(4000)
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

                page.wait_for_timeout(4500)

                body_text = page_text(page)
                page.screenshot(
                    path=os.path.join(ARTIFACT_DIR, f"login_attempt_{attempt}_{idx}_{cand}.png"),
                    full_page=True
                )
                save_text(f"login_attempt_{attempt}_{idx}_{cand}.txt", body_text)

                if ("统一认证中心" not in body_text) and ("Login" not in body_text):
                    logger.info(f"登录成功 (验证码: {cand})")
                    return

                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"验证码 {cand} 尝试失败: {e}")
                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass

    raise RuntimeError("多次尝试后仍无法登录")


def open_mission_page(page):
    for i in range(3):
        try:
            logger.info(f"打开任务页面 (尝试 {i + 1}/3)")
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
                logger.info("任务页面已加载")
                return

        except Exception as e:
            logger.error(f"打开任务页面失败: {e}")
            if i == 2:
                raise
            page.wait_for_timeout(5000)

    raise RuntimeError("未能进入任务列表页")


def get_day_headers(page) -> list:
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

    if MAX_DAYS > 0:
        out = out[:MAX_DAYS]

    logger.info(f"找到 {len(out)} 个日期头")
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


def get_day_block(page, header: str, next_header: str | None) -> str:
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


def detect_card_task_type(card_text: str, day_text: str, card_kind: str) -> str:
    if card_kind == "flight":
        for t in ["置位", "摆渡", "航班"]:
            if t in card_text or t in day_text:
                return t
        return "航班"

    for t in ["训练", "考勤", "摆渡", "置位", "备份", "待命", "航班"]:
        if t in card_text or t in day_text:
            return t

    return "其他"


def task_bucket(task_type: str) -> str:
    return {
        "航班": "flight",
        "置位": "positioning",
        "训练": "training",
        "摆渡": "ferry",
    }.get(task_type, "other")


def extract_date(text: str, page_year: int):
    m = re.search(r"(\d{2})月(\d{2})日", text)
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


def looks_like_generic_time_line(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return False
    if not TIME_RANGE_RE.search(line):
        return False
    if FLIGHT_NO_RE.search(line):
        return False
    if "航班动态" in line:
        return False
    return True


def looks_like_generic_chunk(lines: list) -> bool:
    if not lines:
        return False

    joined = "\n".join(lines)
    if not time_range_search(joined):
        return False

    for i, line in enumerate(lines):
        if is_flight_line(line):
            return False
        if is_old_style_header_line(line):
            return False
        if i + 1 < len(lines):
            if is_flight_line(line) and is_reg_model_line(lines[i + 1]):
                return False

    for line in lines:
        prefix, st, et, suffix = split_prefix_time_suffix(line)
        if st and et and prefix and not FLIGHT_NO_RE.search(prefix):
            return True

    for i in range(len(lines) - 1):
        title_line = normalize_text(lines[i])
        time_line = normalize_text(lines[i + 1])

        if not title_line or not time_line:
            continue
        if is_day_header(title_line):
            continue
        if is_flight_line(title_line):
            continue
        if is_old_style_header_line(title_line):
            continue
        if looks_like_generic_time_line(time_line):
            return True

    return False


def split_day_block_into_cards(day_header: str, day_block: str) -> list:
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    lines = clean_tail_noise(lines)

    if lines and day_header in lines[0]:
        lines = lines[1:]

    if not lines:
        return []

    flight_starts = []
    for i in range(len(lines)):
        line = lines[i]
        if i + 1 < len(lines):
            if is_flight_line(line) and is_reg_model_line(lines[i + 1]):
                flight_starts.append(i)
                continue
        if is_old_style_header_line(line):
            flight_starts.append(i)

    flight_starts = sorted(set(flight_starts))
    cards = []

    if not flight_starts:
        if looks_like_generic_chunk(lines):
            cards.append({"kind": "generic", "text": "\n".join(lines).strip()})
        return cards

    first_start = flight_starts[0]
    pre_lines = clean_tail_noise(lines[:first_start])
    if looks_like_generic_chunk(pre_lines):
        cards.append({"kind": "generic", "text": "\n".join(pre_lines).strip()})

    for idx, start_i in enumerate(flight_starts):
        end_i = flight_starts[idx + 1] if idx + 1 < len(flight_starts) else len(lines)
        chunk_lines = clean_tail_noise(lines[start_i:end_i])

        filtered = []
        for line in chunk_lines:
            if re.fullmatch(r"(9C\d{3,4}[A-Z]?\s*){2,}", line):
                continue
            filtered.append(line)

        chunk = "\n".join(filtered).strip()
        if not chunk:
            continue
        if not time_range_search(chunk):
            continue
        if not FLIGHT_NO_RE.search(chunk):
            continue

        cards.append({"kind": "flight", "text": chunk})

    if flight_starts:
        last_start = flight_starts[-1]
        tail_lines = clean_tail_noise(lines[last_start + 1:])
        if tail_lines and looks_like_generic_chunk(tail_lines):
            tail_text = "\n".join(tail_lines).strip()
            exists_same = any(c["kind"] == "generic" and c["text"] == tail_text for c in cards)
            if not exists_same:
                cards.append({"kind": "generic", "text": tail_text})

    return cards


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
        if FLIGHT_NO_RE.fullmatch(line):
            continue
        if is_old_style_header_line(line):
            continue
        if is_reg_model_line(line):
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


def parse_route_cn_from_line(line: str):
    line = TIME_RANGE_RE.sub("", line).strip()
    line = line.replace("—", "-").replace("－", "-")
    line = re.sub(r"\s+", "", line)

    if "→" in line:
        dep_cn, arr_cn = line.split("→", 1)
        return dep_cn.strip(), arr_cn.strip()

    for dep_name in AIRPORT_NAMES:
        if line.startswith(dep_name):
            remain = line[len(dep_name):].strip()
            if not remain:
                continue
            for arr_name in AIRPORT_NAMES:
                if remain == arr_name:
                    return dep_name, arr_name
            return dep_name, remain

    return "", ""


def get_code_pair_from_day_block(day_block: str, flight_no: str):
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    lines = clean_tail_noise(lines)

    if not lines:
        return "", ""

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


def infer_route_names_from_codes(route_line: str, dep: str, arr: str, checkin_place: str = ""):
    route_line = TIME_RANGE_RE.sub("", route_line).strip()
    route_line = route_line.replace("—", "-").replace("－", "-")
    route_line = re.sub(r"\s+", "", route_line)

    dep_cn = AIRPORT_ICAO_TO_CN.get(dep, "")
    arr_cn = AIRPORT_ICAO_TO_CN.get(arr, "")

    if not dep_cn and checkin_place and re.fullmatch(r"[\u4e00-\u9fff]{2,12}", checkin_place):
        dep_cn = checkin_place

    if dep_cn and route_line.startswith(dep_cn):
        remain = route_line[len(dep_cn):].strip()
        if remain and not arr_cn:
            arr_cn = remain

    if arr_cn and route_line.endswith(arr_cn):
        remain = route_line[:-len(arr_cn)].strip()
        if remain and not dep_cn:
            dep_cn = remain

    return dep_cn, arr_cn


def extract_airports(card_text: str, day_block: str, flight_no: str, checkin_place: str = ""):
    dep_cn = ""
    arr_cn = ""
    dep = ""
    arr = ""

    lines = [x.strip() for x in card_text.splitlines() if x.strip()]

    candidate_lines = []
    for line in lines:
        if time_range_search(line) and "航班动态" not in line:
            candidate_lines.append(line)

    route_line = candidate_lines[-1] if candidate_lines else ""

    if route_line:
        dep_cn_try, arr_cn_try = parse_route_cn_from_line(route_line)
        dep_cn = dep_cn_try or dep_cn
        arr_cn = arr_cn_try or arr_cn
        dep = AIRPORT_CN_TO_ICAO.get(dep_cn, dep)
        arr = AIRPORT_CN_TO_ICAO.get(arr_cn, arr)

    if not dep or not arr:
        dep_code, arr_code = get_code_pair_from_day_block(day_block, flight_no)
        dep = dep or dep_code
        arr = arr or arr_code

    if route_line and (dep or arr):
        dep_cn2, arr_cn2 = infer_route_names_from_codes(route_line, dep, arr, checkin_place=checkin_place)
        dep_cn = dep_cn or dep_cn2
        arr_cn = arr_cn or arr_cn2

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

    if dep and dep_cn:
        add_airport_alias(dep, dep_cn)
    if arr and arr_cn:
        add_airport_alias(arr, arr_cn)

    return dep, arr, dep_cn, arr_cn


def _split_chinese_block_to_names_flight(block: str) -> list:
    block = normalize_text(block)
    if not block:
        return []

    n = len(block)
    if n == 2:
        return [block]
    if n == 3:
        return [block]
    if n == 4:
        return [block[:2], block[2:]]
    if n == 5:
        return [block[:3], block[3:]]
    if n == 6:
        return [block[:3], block[3:]]
    if n == 7:
        return [block[:3], block[3:5], block[5:]]
    if n == 8:
        return [block[:2], block[2:4], block[4:6], block[6:]]

    pieces = []
    temp = block
    while len(temp) > 0:
        if len(temp) in (2, 3):
            pieces.append(temp)
            break
        if len(temp) == 4:
            pieces.extend([temp[:2], temp[2:]])
            break
        if len(temp) == 5:
            pieces.extend([temp[:3], temp[3:]])
            break
        if len(temp) == 6:
            pieces.extend([temp[:3], temp[3:]])
            break
        pieces.append(temp[:3])
        temp = temp[3:]

    return [x for x in pieces if 2 <= len(x) <= 3]


def split_people_from_line_flight(line: str) -> list:
    line = normalize_text(line)
    if not line:
        return []

    if any(x in line for x in ["查看更多", "航班动态"]):
        return []

    exclude_words = ROLE_WORDS | set(GENERIC_TASK_WORDS)

    results = []
    working = line

    for name in KNOWN_PEOPLE:
        if name in working and name not in results:
            results.append(name)
            working = working.replace(name, " ")

    for m in LATIN_PERSON_RE.findall(working):
        m = normalize_text(m)
        if m and m not in results:
            results.append(m)
            working = working.replace(m, " ")

    zh_tagged = list(re.finditer(r"([\u4e00-\u9fff]{2,3}\([^)]*\))", working))
    for m in zh_tagged:
        person = normalize_text(m.group(1))
        if person and person not in results:
            results.append(person)
    for m in zh_tagged:
        working = working.replace(m.group(1), " ")

    zh_blocks = re.findall(r"[\u4e00-\u9fff]+", working)
    for block in zh_blocks:
        block = normalize_text(block)
        if not block or block in exclude_words:
            continue
        names = _split_chinese_block_to_names_flight(block)
        for name in names:
            if name not in exclude_words and name not in results:
                results.append(name)

    cleaned = []
    seen = set()
    for x in results:
        x = normalize_text(x)
        if not x:
            continue
        if x in exclude_words:
            continue
        if re.search(r"\d{2}:\d{2}", x):
            continue
        if len(x) <= 1:
            continue
        if x not in seen:
            cleaned.append(x)
            seen.add(x)

    return cleaned


def likely_name_block_generic(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return False
    if any(x in line for x in TRANSPORT_HINT_WORDS):
        return False
    if time_range_search(line):
        return False
    if "→" in line or "->" in line:
        return False
    if MODEL_ONLY_RE.fullmatch(line):
        return False
    if line in ROLE_WORDS:
        return False
    if line in GENERIC_SKIP_WORDS:
        return False
    if any(x in line for x in ["理论课", "模拟机", "熟练检查", "复训", "训练", "课程"]):
        return False
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,40}", line):
        return False
    return True


def split_continuous_chinese_names_generic(line: str) -> list:
    """
    用于训练/考勤等 generic 场景下的连续中文姓名串拆分。
    规则：
    - 优先命中已知姓名
    - 其次按中文姓名 2~3 字拆分
    - 优先姓氏+2字名；也允许 2 字姓名
    """
    s = normalize_text(line)
    if not s:
        return []

    if not likely_name_block_generic(s):
        return []

    known_sorted = sorted(set(KNOWN_PEOPLE), key=len, reverse=True)

    memo = {}

    def dfs(i: int):
        if i == len(s):
            return []
        if i in memo:
            return memo[i]

        best = None

        # 1) 先试已知姓名
        for name in known_sorted:
            if s.startswith(name, i):
                tail = dfs(i + len(name))
                if tail is not None:
                    cand = [name] + tail
                    if best is None or len(cand) < len(best):
                        best = cand

        # 2) 再试 3 字姓名（姓+2字名）
        if i + 3 <= len(s):
            piece = s[i:i + 3]
            if piece[0] in COMMON_SURNAMES:
                tail = dfs(i + 3)
                if tail is not None:
                    cand = [piece] + tail
                    if best is None or len(cand) < len(best):
                        best = cand

        # 3) 再试 2 字姓名
        if i + 2 <= len(s):
            piece = s[i:i + 2]
            if piece[0] in COMMON_SURNAMES:
                tail = dfs(i + 2)
                if tail is not None:
                    cand = [piece] + tail
                    if best is None or len(cand) < len(best):
                        best = cand

        memo[i] = best
        return best

    result = dfs(0)
    if not result:
        return []

    cleaned = []
    for name in result:
        name = normalize_text(name)
        if not name:
            continue
        if name in ROLE_WORDS or name in GENERIC_SKIP_WORDS or name in GENERIC_TASK_WORDS:
            return []
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,3}", name):
            return []
        cleaned.append(name)

    return cleaned


def split_people_from_line_generic(line: str) -> list:
    line = normalize_text(line)
    if not line:
        return []

    if any(x in line for x in ["查看更多", "航班动态"]):
        return []
    if any(x in line for x in TRANSPORT_HINT_WORDS):
        return []
    if "->" in line or "→" in line:
        return []
    if MODEL_ONLY_RE.fullmatch(line):
        return []
    if re.fullmatch(r"\d{2}:\d{2}", line):
        return []
    if time_range_search(line):
        return []

    results = []
    seen = set()

    for name in KNOWN_PEOPLE:
        if name in line and name not in seen:
            results.append(name)
            seen.add(name)

    for m in LATIN_PERSON_RE.findall(line):
        m = normalize_text(m)
        if m and m not in seen:
            results.append(m)
            seen.add(m)

    # 先试正常分隔模式
    parts = re.split(r"[\s,，、/]+", line)
    split_hit = False
    for part in parts:
        part = normalize_text(part)
        if not part:
            continue
        if part in ROLE_WORDS or part in GENERIC_TASK_WORDS or part in GENERIC_SKIP_WORDS:
            continue
        if re.search(r"\d{2}:\d{2}", part):
            continue
        if any(x in part for x in TRANSPORT_HINT_WORDS):
            continue
        if MODEL_ONLY_RE.fullmatch(part):
            continue
        if 2 <= len(part) <= 4 and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", part):
            if part not in seen:
                results.append(part)
                seen.add(part)
                split_hit = True

    # 如果没有通过分隔符拿到足够名字，再尝试“整串连续中文姓名”拆分
    if not split_hit and likely_name_block_generic(line):
        continuous = split_continuous_chinese_names_generic(line)
        for name in continuous:
            if name not in seen:
                results.append(name)
                seen.add(name)

    return results


def extract_people_lines_flight(card_text: str) -> list:
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]

    out = []
    capture = False

    for line in lines:
        if line in ROLE_WORDS:
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
        if "航班动态" in line or "查看更多" in line:
            continue
        if time_range_search(line):
            continue
        if re.fullmatch(r"\d{2}:\d{2}", line):
            continue
        if len(line) == 1:
            continue

        pieces = split_people_from_line_flight(line)
        for p in pieces:
            p = re.sub(r"\s+", " ", p).strip()
            if p and p not in out and len(p) > 1:
                out.append(p)

    return out


def extract_people_lines_generic(lines: list, consumed_idx: set, title_text: str = "", location: str = ""):
    people = []
    extra_lines = []

    title_text = normalize_text(title_text)
    location = normalize_text(location)

    for idx, line in enumerate(lines):
        if idx in consumed_idx:
            continue

        line = normalize_text(line)
        if not line:
            continue
        if line in {"检", "考"}:
            continue
        if line in ROLE_WORDS:
            continue
        if is_day_header(line):
            continue
        if "查看更多" in line:
            continue
        if is_flight_line(line) or is_reg_model_line(line) or is_old_style_header_line(line):
            continue
        if ICAO_RE.fullmatch(line):
            continue
        if MODEL_ONLY_RE.fullmatch(line):
            continue
        if re.fullmatch(r"\d{2}:\d{2}", line):
            continue
        if len(line) == 1:
            continue
        if title_text and line == title_text:
            continue
        if location and line == location:
            continue
        if any(x in line for x in TRANSPORT_HINT_WORDS):
            extra_lines.append(line)
            continue
        if "-" in line and len(line) > 4 and not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", line):
            extra_lines.append(line)
            continue

        pieces = split_people_from_line_generic(line)
        if pieces:
            for p in pieces:
                p = normalize_text(p)
                if p and p not in people:
                    people.append(p)
            continue

        extra_lines.append(line)

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
    route_line = ""

    for idx, line in enumerate(lines):
        prefix, st, et, suffix = split_prefix_time_suffix(line)
        if st and et:
            time_line_idx = idx
            start_time, end_time = st, et
            route_line = prefix
            if suffix:
                location = suffix
            if has_next_day_marker(line):
                next_day = True
            consumed_idx.add(idx)
            break

    if time_line_idx is None:
        for idx in range(1, len(lines)):
            prev_line = normalize_text(lines[idx - 1])
            line = normalize_text(lines[idx])
            prefix, st, et, suffix = split_prefix_time_suffix(line)
            if st and et:
                time_line_idx = idx
                start_time, end_time = st, et
                route_line = prefix
                if suffix:
                    location = suffix
                title_text = prev_line
                consumed_idx.add(idx)
                consumed_idx.add(idx - 1)
                if has_next_day_marker(line):
                    next_day = True
                break

    if time_line_idx is not None and not title_text and time_line_idx > 0:
        prev = normalize_text(lines[time_line_idx - 1])
        if prev and not is_day_header(prev) and not time_range_search(prev):
            if not is_flight_line(prev) and not is_reg_model_line(prev):
                title_text = prev
                consumed_idx.add(time_line_idx - 1)

    if not title_text and lines:
        first = normalize_text(lines[0])
        if first and not is_day_header(first):
            title_text = first
            consumed_idx.add(0)

    if route_line:
        dep_cn_try, arr_cn_try = parse_route_cn_from_line(route_line)
        dep_cn = dep_cn_try or dep_cn
        arr_cn = arr_cn_try or arr_cn
        dep = AIRPORT_CN_TO_ICAO.get(dep_cn, dep)
        arr = AIRPORT_CN_TO_ICAO.get(arr_cn, arr)

    codes = []
    for line in lines:
        if ICAO_RE.fullmatch(line):
            codes.append(line)

    if len(codes) >= 2:
        dep = dep or codes[0]
        arr = arr or codes[1]
        dep_cn = dep_cn or AIRPORT_ICAO_TO_CN.get(dep, "")
        arr_cn = arr_cn or AIRPORT_ICAO_TO_CN.get(arr, "")

    if route_line and (dep or arr):
        dep_cn2, arr_cn2 = infer_route_names_from_codes(route_line, dep, arr)
        dep_cn = dep_cn or dep_cn2
        arr_cn = arr_cn or arr_cn2

    if dep and dep_cn:
        add_airport_alias(dep, dep_cn)
    if arr and arr_cn:
        add_airport_alias(arr, arr_cn)

    if dep_cn and arr_cn:
        title_text = f"{dep_cn}→{arr_cn}"
    elif dep and arr:
        title_text = f"{dep}→{arr}"
    elif not title_text:
        for line in lines:
            if any(x in line for x in TRANSPORT_HINT_WORDS):
                title_text = line
                break
        if not title_text and lines:
            title_text = lines[0]

    people_lines, extra_lines = extract_people_lines_generic(
        lines, consumed_idx, title_text=title_text, location=location
    )

    dedup_extra = []
    seen_extra = set()
    for line in extra_lines:
        line = normalize_text(line)
        if not line:
            continue
        if line == title_text:
            continue
        if line == route_line:
            continue
        if MODEL_ONLY_RE.fullmatch(line):
            continue
        if re.fullmatch(r"\d{2}:\d{2}", line):
            continue
        if len(line) == 1:
            continue
        if line in ROLE_WORDS:
            continue
        if line not in seen_extra:
            dedup_extra.append(line)
            seen_extra.add(line)
    extra_lines = dedup_extra

    if not start_time or not end_time:
        return None

    start_dt, valid_start = make_datetime_safe(year, month, day_num, start_time)
    end_dt, valid_end = make_datetime_safe(year, month, day_num, end_time)
    if not valid_start or not valid_end:
        return None

    diff_minutes = (end_dt - start_dt).total_seconds() / 60
    if next_day:
        end_dt += timedelta(days=1)
    elif diff_minutes < 0:
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
    dep, arr, dep_cn, arr_cn = extract_airports(
        card_text,
        day_task_text,
        flight_no,
        checkin_place=checkin_place
    )
    people_lines = extract_people_lines_flight(card_text)
    task_type = detect_card_task_type(card_text, day_task_text, "flight")
    next_day = has_next_day_marker(card_text)

    if not flight_no or not start_time or not end_time:
        return None

    start_dt, valid_start = make_datetime_safe(year, month, day_num, start_time)
    end_dt, valid_end = make_datetime_safe(year, month, day_num, end_time)

    if not valid_start or not valid_end:
        logger.warning(f"无效时间格式: {flight_no} {start_time}-{end_time}")
        return None

    diff_minutes = (end_dt - start_dt).total_seconds() / 60

    if next_day:
        end_dt += timedelta(days=1)
    elif diff_minutes < 0:
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
        "其他": "🗂",
    }.get(task_type, "🗂")


def build_title(item: dict) -> str:
    icon = title_icon(item["task_type"])
    flight_no = item["flight_no"]
    dep = item["dep"]
    arr = item["arr"]
    dep_cn = item["dep_cn"]
    arr_cn = item["arr_cn"]
    title_text = item.get("title_text", "").strip()

    if flight_no and dep_cn and arr_cn:
        if item["end_dt"].date() > item["start_dt"].date():
            return f"{icon} {flight_no} {dep_cn}→{arr_cn}(+1)"
        return f"{icon} {flight_no} {dep_cn}→{arr_cn}"

    if flight_no and dep_cn and arr:
        if item["end_dt"].date() > item["start_dt"].date():
            return f"{icon} {flight_no} {dep_cn}→{arr}(+1)"
        return f"{icon} {flight_no} {dep_cn}→{arr}"

    if flight_no and dep and arr_cn:
        if item["end_dt"].date() > item["start_dt"].date():
            return f"{icon} {flight_no} {dep}→{arr_cn}(+1)"
        return f"{icon} {flight_no} {dep}→{arr_cn}"

    if flight_no and dep and arr:
        if item["end_dt"].date() > item["start_dt"].date():
            return f"{icon} {flight_no} {dep}-{arr}(+1)"
        return f"{icon} {flight_no} {dep}-{arr}"

    if flight_no:
        return f"{icon} {flight_no}"

    if dep_cn and arr_cn:
        return f"{icon} {dep_cn}→{arr_cn}"
    if dep and arr:
        return f"{icon} {dep}→{arr}"

    return f"{icon} {title_text or item['task_type']}"


def build_description(item: dict) -> str:
    lines = []
    lines.append(item["day_header"])
    lines.append(f"类型：{item['task_type']}")

    if item["flight_no"]:
        lines.append(f"航班：{item['flight_no']}")
    elif item.get("title_text"):
        lines.append(f"事项：{item['title_text']}")

    if item["dep_cn"] and item["arr_cn"]:
        if item["end_dt"].date() > item["start_dt"].date():
            lines.append(f"航线：{item['dep_cn']} → {item['arr_cn']}(+1)")
        else:
            lines.append(f"航线：{item['dep_cn']} → {item['arr_cn']}")
    elif item["dep_cn"] and item["arr"]:
        if item["end_dt"].date() > item["start_dt"].date():
            lines.append(f"航线：{item['dep_cn']} → {item['arr']}(+1)")
        else:
            lines.append(f"航线：{item['dep_cn']} → {item['arr']}")
    elif item["dep"] and item["arr_cn"]:
        if item["end_dt"].date() > item["start_dt"].date():
            lines.append(f"航线：{item['dep']} → {item['arr_cn']}(+1)")
        else:
            lines.append(f"航线：{item['dep']} → {item['arr_cn']}")
    elif item["dep"] and item["arr"]:
        if item["end_dt"].date() > item["start_dt"].date():
            lines.append(f"航线：{item['dep']} → {item['arr']}(+1)")
        else:
            lines.append(f"航线：{item['dep']} → {item['arr']}")

    if item["checkin_time"] and item["checkin_place"]:
        lines.append(f"签到：{item['checkin_time']}｜{item['checkin_place']}")
    elif item["checkin_time"]:
        lines.append(f"签到：{item['checkin_time']}")

    if item["location"]:
        lines.append(f"地点：{item['location']}")

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


def version_identity(item: dict) -> str:
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
    }
    return stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:32]


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

    uid_base = version_identity(item)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid_base}@crew-calendar",
        f"SUMMARY:{escape_ics_text(title)}",
        f"DTSTART;TZID=Asia/Shanghai:{format_dt_local(item['start_dt'])}",
        f"DTEND;TZID=Asia/Shanghai:{format_dt_local(item['end_dt'])}",
        f"DESCRIPTION:{escape_ics_text(desc)}",
    ]

    if item["location"]:
        lines.append(f"LOCATION:{escape_ics_text(item['location'])}")

    lines.extend([
        "BEGIN:VALARM",
        "TRIGGER:-PT90M",
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


def extract_description_from_vevent(vevent: str) -> str:
    m = re.search(r"^DESCRIPTION:(.+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else ""


def extract_dtstart_from_vevent(vevent: str) -> str:
    m = re.search(r"^DTSTART(?:;[^:]+)?:([0-9T]+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def extract_dtend_from_vevent(vevent: str) -> str:
    m = re.search(r"^DTEND(?:;[^:]+)?:([0-9T]+)$", vevent, flags=re.M)
    return m.group(1).strip() if m else "99999999T999999"


def event_quality(item: dict) -> int:
    score = 0
    if item["flight_no"]:
        score += 10
    if item["dep"] or item["dep_cn"]:
        score += 20
    if item["arr"] or item["arr_cn"]:
        score += 20
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
        logger.info(f"{filename} 内容未变化")
        return False

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_text)
    logger.info(f"写入 {filename}: {len(ordered)} 个事件")
    return True


def route_text_from_summary(summary: str, flight_no: str) -> str:
    s = normalize_text(summary)
    if not s:
        return ""

    if flight_no and flight_no in s:
        pos = s.find(flight_no)
        s = s[pos + len(flight_no):].strip()

    if s.startswith(("✈️", "🚐", "📍", "🎓", "🗂", "🕒", "📋")):
        s = s[2:].strip()

    return s.strip()


def is_bad_training_event_block(block: str) -> bool:
    desc = extract_description_from_vevent(block)
    desc = desc.replace(r"\n", "\n")
    bad_tokens = [
        "人员名单：\n• 理论课",
        "人员名单：\n• 模拟机",
        "• 应急",
        "• 生存",
        "• 复训",
        "• 熟练",
        "• 检查",
        "• 定期复",
        "• 训练结合",
    ]
    return any(token in desc for token in bad_tokens)


def is_broken_old_summary_for_item(old_summary: str, item: dict, old_block: str = "") -> bool:
    correct_summary = build_title(item)
    old_summary = normalize_text(old_summary)

    if not old_summary or old_summary == correct_summary:
        return False

    flight_no = item["flight_no"]
    correct_dep = item["dep_cn"]
    correct_arr = item["arr_cn"]

    if flight_no and correct_dep and correct_arr and flight_no in old_summary:
        old_route = route_text_from_summary(old_summary, flight_no)
        if old_route:
            exact1 = f"{correct_dep}→{correct_arr}"
            exact2 = f"{correct_dep}→{correct_arr}(+1)"
            if old_route not in {exact1, exact2}:
                compact_old = old_route.replace("→", "").replace("-", "").replace("(+1)", "").replace(" ", "")
                compact_correct = f"{correct_dep}{correct_arr}"
                if compact_old == compact_correct:
                    return True

    if not flight_no:
        icon = title_icon(item["task_type"])
        old_no_icon = old_summary
        if old_no_icon.startswith(icon):
            old_no_icon = old_no_icon[len(icon):].strip()

        if MODEL_ONLY_RE.fullmatch(old_no_icon):
            return True
        if old_no_icon in {"摆渡", "置位", "训练", "其他"} and "→" in correct_summary:
            return True

        if item["task_type"] == "训练" and old_block and is_bad_training_event_block(old_block):
            return True

    return False


def collect_day_blocks(page) -> list:
    day_headers = get_day_headers(page)
    save_text("day_headers.txt", "\n".join(day_headers))

    result = []
    for idx, header in enumerate(day_headers):
        next_header = day_headers[idx + 1] if idx + 1 < len(day_headers) else None

        if not expand_day(page, header):
            continue

        try:
            day_block = get_day_block(page, header, next_header)
            cards = split_day_block_into_cards(header, day_block)

            key = safe_name(header)
            save_text(f"block_{key}.txt", day_block)
            save_text(
                f"cards_{key}.txt",
                "\n\n==========\n\n".join([f"[{c['kind']}]\n{c['text']}" for c in cards])
            )

            result.append({
                "day_header": header,
                "day_block": day_block,
                "cards": cards,
            })
        except Exception as e:
            logger.error(f"处理日期 {header} 失败: {e}")
        finally:
            collapse_day(page, header)

    logger.info(f"收集了 {len(result)} 个日期的数据")
    return result


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

            if not item:
                continue

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

    def merge_history(filename: str, bucket_items: list):
        existing_map = read_existing_events(filename)
        new_blocks = [build_vevent(item, version_tag=version_tag) for item in bucket_items]

        merged_map = dict(existing_map)
        for block in new_blocks:
            uid = extract_uid_from_vevent(block)
            if uid:
                merged_map[uid] = block

        for item in bucket_items:
            current_uid = extract_uid_from_vevent(build_vevent(item, version_tag=version_tag))
            current_dtstart = format_dt_local(item["start_dt"])
            current_dtend = format_dt_local(item["end_dt"])

            for uid, block in list(merged_map.items()):
                if uid == current_uid:
                    continue
                if extract_dtstart_from_vevent(block) != current_dtstart:
                    continue
                if extract_dtend_from_vevent(block) != current_dtend:
                    continue

                old_summary = extract_summary_from_vevent(block)
                if is_broken_old_summary_for_item(old_summary, item, old_block=block):
                    logger.info(f"自动清理旧错误事件: {uid} | {old_summary}")
                    del merged_map[uid]

        return list(merged_map.values())

    changed_root = False

    changed_root |= write_calendar_from_vevents("flight.ics", merge_history("flight.ics", buckets["flight"]))
    changed_root |= write_calendar_from_vevents("positioning.ics", merge_history("positioning.ics", buckets["positioning"]))
    changed_root |= write_calendar_from_vevents("training.ics", merge_history("training.ics", buckets["training"]))
    changed_root |= write_calendar_from_vevents("ferry.ics", merge_history("ferry.ics", buckets["ferry"]))
    changed_root |= write_calendar_from_vevents("other.ics", merge_history("other.ics", buckets["other"]))
    changed_root |= write_calendar_from_vevents("crew_schedule.ics", merge_history("crew_schedule.ics", total_items))

    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "flight.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["flight"]]
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "positioning.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["positioning"]]
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "training.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["training"]]
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "ferry.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["ferry"]]
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "other.ics"),
        [build_vevent(item, version_tag=version_tag) for item in buckets["other"]]
    )
    write_calendar_from_vevents(
        os.path.join(ARTIFACT_DIR, "crew_schedule.ics"),
        [build_vevent(item, version_tag=version_tag) for item in total_items]
    )

    save_text("changed_root_flag.txt", str(changed_root))
    logger.info(f"本次抓到 {len(total_items)} 个任务版本；历史任务继续保留")


def run():
    logger.info("=" * 60)
    logger.info("开始执行航班日历爬虫")
    logger.info("=" * 60)

    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少环境变量：CREW_USERNAME / CREW_PASSWORD")

    rebuild_airport_indexes()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
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
