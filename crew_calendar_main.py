import re
import io
import json
import os
import csv
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
AIRPORTS_CSV_FILE = "airports.csv"

SH_TZ = ZoneInfo("Asia/Shanghai")

HEADLESS = os.environ.get("HEADLESS", "1") != "0"
ALARM_MINUTES = 90
LOAD_MORE_MAX_ROUNDS = 8
SEGMENT_CARD_MARKER = "__SEGMENT_CARD__"


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
    "虹桥": "ZSSS",
    "上海浦东": "ZSPD",
    "浦东": "ZSPD",
    "西安咸阳": "ZLXY",
    "咸阳": "ZLXY",
    "重庆江北": "ZUCK",
    "江北": "ZUCK",
    "大连周水子": "ZYTL",
    "周水子": "ZYTL",
    "深圳宝安": "ZGSZ",
    "宝安": "ZGSZ",
    "济南遥墙": "ZSJN",
    "遥墙": "ZSJN",
    "哈尔滨太平": "ZYHB",
    "太平": "ZYHB",
    "淮安涟水": "ZSSH",
    "涟水": "ZSSH",
    "呼和浩特白塔": "ZBHH",
    "白塔": "ZBHH",
    "长春龙嘉": "ZYCC",
    "龙嘉": "ZYCC",
    "兰州中川": "ZLLL",
    "中川": "ZLLL",
    "广州白云": "ZGGG",
    "白云": "ZGGG",
    "揭阳潮汕": "ZGOW",
    "潮汕": "ZGOW",
    "南宁吴圩": "ZGNN",
    "吴圩": "ZGNN",
    "扬州泰州": "ZSYZ",
    "扬泰": "ZSYZ",
    "厦门高崎": "ZSAM",
    "高崎": "ZSAM",
    "泉州晋江": "ZSQZ",
    "晋江": "ZSQZ",
    "金边德崇": "VDTI",
    "德崇": "VDTI",
    "石家庄正定": "ZBSJ",
    "正定": "ZBSJ",
    "宁波栎社": "ZSNB",
    "栎社": "ZSNB",
    "天津滨海": "ZBTJ",
    "滨海": "ZBTJ",
    "东营胜利": "ZSDY",
    "东营": "ZSDY",
    "北京首都": "ZBAA",
    "首都": "ZBAA",
    "北京大兴": "ZBAD",
    "大兴": "ZBAD",
    "成都天府": "ZUTF",
    "天府": "ZUTF",
    "成都双流": "ZUUU",
    "双流": "ZUUU",
    "昆明长水": "ZPPP",
    "长水": "ZPPP",
    "武汉天河": "ZHHH",
    "天河": "ZHHH",
    "南京禄口": "ZSNJ",
    "禄口": "ZSNJ",
    "杭州萧山": "ZSHC",
    "萧山": "ZSHC",
    "青岛胶东": "ZSQD",
    "胶东": "ZSQD",
    "郑州新郑": "ZHCC",
    "新郑": "ZHCC",
    "长沙黄花": "ZGHA",
    "黄花": "ZGHA",
    "福州长乐": "ZSFZ",
    "长乐": "ZSFZ",
    "沈阳桃仙": "ZYTX",
    "桃仙": "ZYTX",
    "太原武宿": "ZBYN",
    "武宿": "ZBYN",
    "乌鲁木齐地窝堡": "ZWWW",
    "地窝堡": "ZWWW",
    "海口美兰": "ZJHK",
    "美兰": "ZJHK",
    "三亚凤凰": "ZJSY",
    "凤凰": "ZJSY",
    "合肥新桥": "ZSOF",
    "新桥": "ZSOF",
    "南昌昌北": "ZSCN",
    "昌北": "ZSCN",
    "贵阳龙洞堡": "ZUGY",
    "龙洞堡": "ZUGY",
    "桂林两江": "ZGKL",
    "两江": "ZGKL",
    "北海福成": "ZGBH",
    "福成": "ZGBH",
    "珠海金湾": "ZGSD",
    "金湾": "ZGSD",
    "湛江吴川": "ZGZJ",
    "吴川": "ZGZJ",
    "南通兴东": "ZSNT",
    "兴东": "ZSNT",
    "常州奔牛": "ZSCG",
    "奔牛": "ZSCG",
    "无锡硕放": "ZSWX",
    "硕放": "ZSWX",
    "盐城南洋": "ZSYN",
    "南洋": "ZSYN",
    "徐州观音": "ZSXZ",
    "观音": "ZSXZ",
    "连云港花果山": "ZSLG",
    "花果山": "ZSLG",
    "温州龙湾": "ZSWZ",
    "龙湾": "ZSWZ",
    "义乌": "ZSYW",
    "台州路桥": "ZSLQ",
    "路桥": "ZSLQ",
    "舟山普陀山": "ZSZS",
    "普陀山": "ZSZS",
    "烟台蓬莱": "ZSYT",
    "蓬莱": "ZSYT",
    "威海大水泊": "ZSWH",
    "大水泊": "ZSWH",
    "临沂启阳": "ZSLY",
    "启阳": "ZSLY",
    "潍坊": "ZSWF",
    "济宁曲阜": "ZSJG",
    "曲阜": "ZSJG",
    "日照山字河": "ZSRZ",
    "山字河": "ZSRZ",
    "洛阳北郊": "ZHLY",
    "北郊": "ZHLY",
    "南阳姜营": "ZHNY",
    "姜营": "ZHNY",
    "宜昌三峡": "ZHYC",
    "三峡": "ZHYC",
    "襄阳刘集": "ZHXF",
    "刘集": "ZHXF",
    "张家界荷花": "ZGDY",
    "荷花": "ZGDY",
    "常德桃花源": "ZGCD",
    "桃花源": "ZGCD",
    "衡阳南岳": "ZGHY",
    "南岳": "ZGHY",
    "南充高坪": "ZUNC",
    "高坪": "ZUNC",
    "绵阳南郊": "ZUMY",
    "南郊": "ZUMY",
    "泸州云龙": "ZULZ",
    "云龙": "ZULZ",
    "宜宾五粮液": "ZUYB",
    "五粮液": "ZUYB",
    "西昌青山": "ZUXC",
    "青山": "ZUXC",
    "九寨黄龙": "ZUJZ",
    "黄龙": "ZUJZ",
    "拉萨贡嘎": "ZULS",
    "贡嘎": "ZULS",
    "丽江三义": "ZPLJ",
    "三义": "ZPLJ",
    "大理凤仪": "ZPDL",
    "凤仪": "ZPDL",
    "西双版纳嘎洒": "ZPJH",
    "嘎洒": "ZPJH",
    "腾冲驼峰": "ZUTC",
    "驼峰": "ZUTC",
    "迪庆香格里拉": "ZPDQ",
    "香格里拉": "ZPDQ",
    "银川河东": "ZLIC",
    "河东": "ZLIC",
    "西宁曹家堡": "ZLXN",
    "曹家堡": "ZLXN",
    "格尔木": "ZLGM",
    "敦煌莫高": "ZLDH",
    "莫高": "ZLDH",
    "嘉峪关": "ZLJQ",
    "庆阳西峰": "ZLQY",
    "西峰": "ZLQY",
    "榆林榆阳": "ZLYL",
    "榆阳": "ZLYL",
    "延安南泥湾": "ZLYA",
    "南泥湾": "ZLYA",
    "包头东河": "ZBOW",
    "东河": "ZBOW",
    "鄂尔多斯伊金霍洛": "ZBDS",
    "伊金霍洛": "ZBDS",
    "赤峰玉龙": "ZBCF",
    "玉龙": "ZBCF",
    "通辽": "ZBTL",
    "海拉尔东山": "ZBLA",
    "东山": "ZBLA",
    "满洲里西郊": "ZBMZ",
    "西郊": "ZBMZ",
    "锡林浩特": "ZBXH",
    "大同云冈": "ZBDT",
    "云冈": "ZBDT",
    "运城张孝": "ZBYC",
    "张孝": "ZBYC",
    "长治王村": "ZBCZ",
    "王村": "ZBCZ",
    "大庆萨尔图": "ZYDQ",
    "萨尔图": "ZYDQ",
    "牡丹江海浪": "ZYMD",
    "海浪": "ZYMD",
    "佳木斯东郊": "ZYJM",
    "丹东浪头": "ZYDD",
    "浪头": "ZYDD",
    "延吉朝阳川": "ZYYJ",
    "朝阳川": "ZYYJ",
    "札幌新千岁": "RJCC",
    "新千岁": "RJCC",
    "东京成田": "RJAA",
    "成田": "RJAA",
    "东京羽田": "RJTT",
    "羽田": "RJTT",
    "大阪关西": "RJBB",
    "关西": "RJBB",
    "名古屋中部": "RJGG",
    "中部": "RJGG",
    "福冈": "RJFF",
    "冲绳那霸": "ROAH",
    "那霸": "ROAH",
    "首尔仁川": "RKSI",
    "仁川": "RKSI",
    "首尔金浦": "RKSS",
    "金浦": "RKSS",
    "济州": "RKPC",
    "釜山金海": "RKPK",
    "金海": "RKPK",
    "曼谷素旺那普": "VTBS",
    "曼谷素万那普": "VTBS",
    "素万那普": "VTBS",
    "素旺那普": "VTBS",
    "曼谷廊曼": "VTBD",
    "廊曼": "VTBD",
    "普吉": "VTSP",
    "清迈": "VTCC",
    "新加坡樟宜": "WSSS",
    "樟宜": "WSSS",
    "吉隆坡": "WMKK",
    "槟城": "WMKP",
    "雅加达苏加诺哈达": "WIII",
    "苏加诺哈达": "WIII",
    "巴厘岛登巴萨": "WADD",
    "登巴萨": "WADD",
    "马尼拉": "RPLL",
    "宿务": "RPVM",
    "胡志明": "VVTS",
    "河内内排": "VVNB",
    "内排": "VVNB",
    "岘港": "VVDN",
    "金边": "VDPP",
    "乌兰巴托成吉思汗": "ZMCK",
    "成吉思汗": "ZMCK",
    "乌兰巴托": "ZMCK",
    "香港": "VHHH",
    "香港赤鱲角": "VHHH",
    "赤鱲角": "VHHH",
    "澳门": "VMMC",
    "台北桃园": "RCTP",
    "桃园": "RCTP",
    "台北松山": "RCSS",
    "松山": "RCSS",
    "高雄": "RCKH",
}


AIRPORT_CN_TO_ICAO = {}
AIRPORT_ICAO_TO_CN = {}
AIRPORT_NAMES = []


KNOWN_PEOPLE = ["段洋硕"]


COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
    "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
    "俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮"
    "卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计"
    "伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜"
    "郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯昝管卢莫经房裘缪干"
    "解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊於惠甄曲"
    "家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班"
    "仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄"
    "印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭"
    "贡劳逄姬申扶堵冉宰郦雍璩桑桂濮牛寿通边扈燕冀郏浦尚农温别"
    "庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满"
    "弘匡国文寇广禄阙东沃利蔚越隆师巩厍聂晁勾敖融冷訾辛阚"
    "那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公官"
)

COMPOUND_SURNAMES = [
    "欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公羊",
    "赫连", "澹台", "公冶", "宗政", "濮阳", "淳于", "单于", "太叔",
    "申屠", "公孙", "仲孙", "轩辕", "令狐", "钟离", "宇文", "长孙",
    "慕容", "鲜于", "闾丘", "司徒", "司空", "亓官", "司寇", "仉督",
    "子车", "颛孙", "端木", "巫马", "公西", "漆雕", "乐正", "壤驷",
    "公良", "拓跋", "夹谷", "宰父", "谷梁", "段干", "百里", "东郭",
    "南门", "呼延", "羊舌", "微生", "梁丘", "左丘", "东门", "西门",
    "南宫",
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
DAY_SUMMARY_LINE_RE = re.compile(r"^(\d{2}月\d{2}日\s*周.)(.*)$")
LATIN_PERSON_RE = re.compile(r"[A-Z][A-Z\s\.\-']{1,80}\([^)]*\)")
ZH_TAGGED_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}[0-9A-Za-z]?\([^)]*\)")
ZH_NAME_WITH_ROLE_RE = re.compile(r"[\u4e00-\u9fff]{2,4}[0-9A-Za-z]?(?:\([A-Z]\))?")
SHORT_ROLE_RE = re.compile(r"\([A-Z]\)")
ROLE_PAREN_RE = re.compile(r"\([^)]*\)")


ROLE_WORDS = {"机长", "副驾驶", "乘务长", "随机人员", "加机组人员", "观察员"}

TRAINING_KEYWORDS = [
    "理论课", "模拟机", "训练", "复训", "检查", "熟练", "安保",
    "应急", "生存", "考试", "晋级", "课程", "地面课", "协同",
    "CRM", "EBT",
]

POSITIONING_KEYWORDS = ["置位"]
FERRY_KEYWORDS = ["摆渡"]
STOP_KEYWORDS = ["停飞", "Grounding", "grounding"]
ATTENDANCE_KEYWORDS = ["考勤"]
STANDBY_KEYWORDS = ["备份", "待命"]

DETAIL_SIGNAL_KEYWORDS = [
    "理论课",
    "模拟机",
    "教室",
    "春秋飞培",
    "人员名单",
    "机长",
    "副驾驶",
    "乘务长",
    "随机人员",
    "加机组人员",
    "航班动态",
    "签到",
    "地点",
    "候振",
]

TRANSPORT_HINT_WORDS = ["搭乘", "乘坐", "火车", "高铁", "动车", "去", "前往", "至", "返回"]

BAD_TITLE_WORDS = {
    "个起落",
    "90天3个起落",
    "90天三个起落",
    "三个起落",
    "3个起落",
}

GENERIC_TASK_WORDS = [
    "训练", "考勤", "摆渡", "置位", "航班", "备份", "待命", "停飞", "个起落",
]

TASK_TITLE_WORDS = {
    "理论课", "模拟机", "应急", "生存", "复训", "训练", "考勤",
    "检查", "定期", "熟练", "结合", "晋级", "考试", "安保",
    "程序", "停飞", "开会", "英语", "副驾驶", "机长", "乘务长",
    "随机人员", "加机组人员", "观察员", "检", "考", "协同",
    "签到", "劳动节", "立夏", "个起落", "Grounding",
}


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


def is_bad_title_text(text: str) -> bool:
    text = normalize_text(text)
    if not text:
        return False
    if text in BAD_TITLE_WORDS:
        return True
    if re.fullmatch(r"(90天)?[三3]个起落", text):
        return True
    return False


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


def load_airports_csv() -> dict:
    data = {}

    if not os.path.exists(AIRPORTS_CSV_FILE):
        return data

    try:
        with open(AIRPORTS_CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                icao = normalize_text(row.get("icao", "")).upper()
                cn_name = normalize_text(row.get("cn_name", ""))
                aliases_raw = normalize_text(row.get("aliases", ""))

                if not re.fullmatch(r"[A-Z]{4}", icao):
                    continue

                names = []
                if cn_name:
                    names.append(cn_name)

                if aliases_raw:
                    for alias in re.split(r"[|,，、/]+", aliases_raw):
                        alias = normalize_text(alias)
                        if alias:
                            names.append(alias)

                for name in names:
                    if name and not re.fullmatch(r"[A-Z]{4}", name):
                        data[name] = icao

        logger.info(f"读取 airports.csv：{len(data)} 个机场别名")
    except Exception as e:
        logger.warning(f"读取 airports.csv 失败，跳过：{e}")

    return data


def put_airport_mapping(mapping: dict, name: str, icao: str, source: str):
    name = normalize_text(name)
    icao = normalize_text(icao).upper()

    if not name or not re.fullmatch(r"[A-Z]{4}", icao):
        return

    if name in mapping and mapping[name] != icao:
        logger.warning(
            f"机场别名冲突：{name} 已是 {mapping[name]}，{source} 想设为 {icao}，保留原值"
        )
        return

    mapping[name] = icao


def rebuild_airport_indexes():
    global AIRPORT_CN_TO_ICAO, AIRPORT_ICAO_TO_CN, AIRPORT_NAMES

    merged = {}

    for name, icao in BASE_AIRPORT_CN_TO_ICAO.items():
        put_airport_mapping(merged, name, icao, "BASE")

    csv_data = load_airports_csv()
    for name, icao in csv_data.items():
        put_airport_mapping(merged, name, icao, "airports.csv")

    alias_data = load_airport_aliases()
    for icao, aliases in alias_data.items():
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            put_airport_mapping(merged, str(alias), icao, "airport_aliases.json")

    AIRPORT_CN_TO_ICAO = merged

    AIRPORT_ICAO_TO_CN = {}
    for name, icao in AIRPORT_CN_TO_ICAO.items():
        if icao not in AIRPORT_ICAO_TO_CN or len(name) > len(AIRPORT_ICAO_TO_CN[icao]):
            AIRPORT_ICAO_TO_CN[icao] = name

    AIRPORT_NAMES = sorted(AIRPORT_CN_TO_ICAO.keys(), key=len, reverse=True)

    save_text(
        "airport_index_debug.txt",
        "\n".join([f"{k}={v}" for k, v in sorted(AIRPORT_CN_TO_ICAO.items(), key=lambda x: x[0])]),
    )


def add_airport_alias(icao: str, alias: str):
    icao = normalize_text(icao).upper()
    alias = normalize_text(alias)

    if not re.fullmatch(r"[A-Z]{4}", icao):
        return
    if not alias or len(alias) < 2 or re.fullmatch(r"[A-Z]{4}", alias):
        return
    if alias in BASE_AIRPORT_CN_TO_ICAO:
        return

    current = AIRPORT_CN_TO_ICAO.get(alias)
    if current and current != icao:
        logger.warning(f"不写入机场别名冲突：{alias} 当前={current} 新={icao}")
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
        "0": ["0", "O"],
        "O": ["O", "0"],
        "1": ["1", "I", "L"],
        "I": ["I", "1", "L"],
        "L": ["L", "1", "I"],
        "5": ["5", "S"],
        "S": ["S", "5"],
        "8": ["8", "B"],
        "B": ["B", "8", "3"],
        "2": ["2", "Z"],
        "Z": ["Z", "2"],
        "6": ["6", "G"],
        "G": ["G", "6"],
        "3": ["3", "B"],
        "7": ["7", "T"],
        "T": ["T", "7"],
        "9": ["9", "G"],
        "4": ["4", "A"],
        "A": ["A", "4"],
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
                    logger.info(f"登录成功，验证码：{cand}")
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
            logger.info(f"打开任务页面，尝试 {i + 1}/3")
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

        logger.info(
            f"第 {round_no} 轮加载前：日期头 {len(headers_before)} 个，查看更多 {len(more_before)} 个"
        )

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

        logger.info(
            f"第 {round_no} 轮加载后：日期头 {len(headers_after)} 个，查看更多 {len(more_after)} 个"
        )

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


def click_day_toggle(page, header: str, strategy: int = 0) -> bool:
    try:
        row = page.locator(f"text={header}").first
        row.scroll_into_view_if_needed(timeout=5000)
        random_like_wait(page, 300, 200)

        info = row.evaluate(
            """
            (el, strategy) => {
                function rectInfo(r) {
                    return {
                        x: r.x,
                        y: r.y,
                        width: r.width,
                        height: r.height,
                        left: r.left,
                        right: r.right,
                        top: r.top,
                        bottom: r.bottom
                    };
                }

                let textRect = el.getBoundingClientRect();
                let node = el;

                for (let i = 0; i < 10; i++) {
                    if (!node) break;

                    let r = node.getBoundingClientRect();

                    if (r.width >= 350 && r.height >= 25) {
                        break;
                    }

                    if (!node.parentElement) break;
                    node = node.parentElement;
                }

                let r = node.getBoundingClientRect();

                let x = r.right - 24;
                let y = r.top + r.height / 2;

                if (strategy === 1) {
                    x = r.right - 70;
                    y = r.top + r.height / 2;
                } else if (strategy === 2) {
                    x = r.left + r.width / 2;
                    y = r.top + r.height / 2;
                } else if (strategy === 3) {
                    x = textRect.left + textRect.width / 2;
                    y = textRect.top + textRect.height / 2;
                } else if (strategy === 4) {
                    x = window.innerWidth - 38;
                    y = textRect.top + textRect.height / 2;
                }

                x = Math.max(5, Math.min(window.innerWidth - 5, x));
                y = Math.max(5, Math.min(window.innerHeight - 5, y));

                let target = document.elementFromPoint(x, y);

                if (target) {
                    target.click();
                } else {
                    node.click();
                }

                return {
                    ok: true,
                    strategy: strategy,
                    clickedX: x,
                    clickedY: y,
                    textRect: rectInfo(textRect),
                    rowRect: rectInfo(r),
                    targetTag: target ? target.tagName : "",
                    targetClass: target ? String(target.className || "") : "",
                    targetText: target ? String(target.innerText || target.textContent || "").slice(0, 80) : ""
                };
            }
            """,
            strategy,
        )

        save_text(
            f"click_{safe_name(header)}_strategy_{strategy}.json",
            json.dumps(info, ensure_ascii=False, indent=2),
        )

        random_like_wait(page, 1000, 500)
        return True

    except Exception as e:
        logger.warning(f"{header} JS 点击策略 {strategy} 失败：{e}")

    try:
        row = page.locator(f"text={header}").first
        box = row.bounding_box()

        if not box:
            return False

        viewport = page.viewport_size or {"width": 1400, "height": 1000}
        vw = viewport.get("width", 1400)

        y = box["y"] + box["height"] / 2

        points = [
            (vw - 45, y),
            (vw - 100, y),
            (box["x"] + box["width"] + 60, y),
            (box["x"] + box["width"] / 2, y),
        ]

        x, y = points[strategy % len(points)]
        x = max(5, min(vw - 5, x))

        page.mouse.click(x, y)
        random_like_wait(page, 1000, 500)
        return True

    except Exception as e:
        logger.warning(f"{header} 坐标点击策略 {strategy} 失败：{e}")
        return False


def expand_day(page, header: str, strategy: int = 0) -> bool:
    ok = click_day_toggle(page, header, strategy=strategy)

    if ok:
        random_like_wait(page, 1200, 600)

    return ok


def collapse_day(page, header: str):
    try:
        ok = click_day_toggle(page, header, strategy=0)
        if ok:
            random_like_wait(page, 700, 300)
    except Exception:
        pass


def get_day_block_by_body_text(page, header: str, next_header=None) -> str:
    try:
        body_text_all = normalize_text(page.locator("body").inner_text(timeout=8000))
    except Exception:
        body_text_all = normalize_text(page_text(page))

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


def get_day_block_by_dom(page, header: str, next_header=None) -> str:
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

                // 保留每一段 .cal-schedule 的完整文本。
                // 普通去重文本会把后续航段重复出现的机组名单吞掉，
                // 导致多个航段错误继承第一段人员/注册号。
                const segmentCards = [];
                const segmentSeen = new Set();

                for (const el of all) {
                    if (!visible(el)) continue;
                    if (!el.classList || !el.classList.contains("cal-schedule")) continue;

                    const r = el.getBoundingClientRect();
                    if (r.bottom < rowBottom - 3) continue;
                    if (r.top > nextTop - 5) continue;

                    const overlap = Math.min(r.right, regionRight) - Math.max(r.left, regionLeft);
                    if (overlap <= 20) continue;

                    const text = norm(el.innerText || el.textContent || "");
                    if (!text) continue;
                    if (!/9C\\d{3,4}[A-Z]?/.test(text)) continue;
                    if (!/\\d{2}:\\d{2}\\s*[-~～—–]+\\s*\\d{2}:\\d{2}/.test(text)) continue;

                    const key = `${Math.round(r.top)}|${text}`;
                    if (segmentSeen.has(key)) continue;
                    segmentSeen.add(key);

                    segmentCards.push({
                        top: r.top,
                        left: r.left,
                        text,
                        cls: String(el.className || "").slice(0, 100)
                    });
                }

                segmentCards.sort((a, b) => {
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

                let finalText = lines.join("\\n");

                if (segmentCards.length) {
                    const preserved = segmentCards
                        .map(x => "__SEGMENT_CARD__\\n" + x.text)
                        .join("\\n");
                    finalText = finalText ? finalText + "\\n" + preserved : preserved;
                }

                return {
                    ok: true,
                    reason: "ok",
                    text: finalText,
                    debug: {
                        selectedHeaderText: headerCandidates[0].text,
                        selectedHeaderScore: headerCandidates[0].score,
                        selectedHeaderRect: headerCandidates[0].rect,
                        rowRect: rectInfo(rowNode),
                        regionLeft,
                        regionRight,
                        nextTop,
                        segmentCards: segmentCards.slice(0, 12),
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

    return ""


def block_looks_polluted(day_block: str, header: str, fallback_text: str = "") -> bool:
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

    return False


def get_day_block(page, header: str, next_header=None, fallback_text: str = "") -> str:
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

        if SEGMENT_CARD_MARKER in dom_block:
            dom_score += 5000

        if "航班动态" in body_block:
            body_score += 500

        chosen = dom_block if dom_score >= body_score else body_block

        if block_looks_polluted(chosen, header, fallback_text=fallback_text):
            save_text(f"polluted_chosen_block_{safe_name(header)}.txt", chosen)
            return ""

        return chosen

    return ""


def detect_page_year(page) -> int:
    text = page_text(page)
    m = PAGE_YEAR_MONTH_RE.search(text)

    if m:
        return int(m.group(1))

    return datetime.now(SH_TZ).year


def is_day_header(line: str) -> bool:
    return DAY_HEADER_RE.match(line) is not None


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


def has_any_keyword(text: str, keywords: list) -> bool:
    return any(k in text for k in keywords)


def line_has_task_keyword(line: str) -> bool:
    line = normalize_text(line)
    keywords = (
        POSITIONING_KEYWORDS
        + FERRY_KEYWORDS
        + TRAINING_KEYWORDS
        + STOP_KEYWORDS
        + ATTENDANCE_KEYWORDS
        + STANDBY_KEYWORDS
    )
    return any(k in line for k in keywords)


def line_has_summary_task_signal(line: str) -> bool:
    line = normalize_text(line)

    if not line:
        return False

    if not TIME_RANGE_RE.search(line):
        return False

    keywords = (
        POSITIONING_KEYWORDS
        + FERRY_KEYWORDS
        + TRAINING_KEYWORDS
        + STOP_KEYWORDS
        + ATTENDANCE_KEYWORDS
        + STANDBY_KEYWORDS
        + ["航班"]
    )

    return any(k in line for k in keywords)


def get_day_summary_task_map(page) -> dict:
    text = page_text(page)
    result = {}

    for raw_line in text.splitlines():
        line = normalize_text(raw_line)

        if not line:
            continue

        m = DAY_SUMMARY_LINE_RE.match(line)

        if not m:
            continue

        header = normalize_text(m.group(1))
        tail = normalize_text(m.group(2))

        if not tail:
            continue

        if "查看更多" in tail:
            continue

        if line_has_summary_task_signal(tail):
            result[header] = tail

    save_text(
        "day_summary_fallback_map.txt",
        "\n".join([f"{k} => {v}" for k, v in result.items()]),
    )

    return result


def is_summary_like_line_for_header(line: str, header: str) -> bool:
    line = normalize_text(line)
    header = normalize_text(header)

    if not line:
        return False

    if header and line.startswith(header):
        tail = normalize_text(line[len(header):])
        return line_has_summary_task_signal(tail)

    return line_has_summary_task_signal(line)


def remove_summary_like_lines(lines: list, header: str, fallback_text: str = "") -> list:
    cleaned = []
    fallback_text = normalize_text(fallback_text)

    for line in lines:
        line = normalize_text(line)

        if not line:
            continue

        if is_summary_like_line_for_header(line, header):
            continue

        if fallback_text and line == fallback_text:
            continue

        if "查看更多" in line:
            continue

        if PURE_DATE_PREFIX_RE.match(line):
            continue

        cleaned.append(line)

    return cleaned


def day_block_has_real_detail(day_block: str, header: str, fallback_text: str = "") -> bool:
    day_block = normalize_text(day_block)

    if not day_block:
        return False

    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]

    if not lines:
        return False

    useful_lines = []

    for line in lines:
        if line == header:
            continue

        if header in line and is_summary_like_line_for_header(line, header):
            continue

        useful_lines.append(line)

    useful_lines = remove_summary_like_lines(useful_lines, header, fallback_text=fallback_text)

    if not useful_lines:
        return False

    joined = "\n".join(useful_lines)

    if any(k in joined for k in DETAIL_SIGNAL_KEYWORDS):
        return True

    if "航班动态" in joined:
        return True

    if FLIGHT_NO_RE.search(joined) and (
        REG_AND_MODEL_RE.search(joined)
        or REG_ONLY_RE.search(joined)
        or len(ICAO_RE.findall(joined)) >= 2
    ):
        return True

    if len(useful_lines) >= 2:
        has_text_detail = any(re.search(r"[\u4e00-\u9fffA-Za-z]", x) for x in useful_lines)
        has_time = any(TIME_RANGE_RE.search(x) for x in useful_lines)
        if has_text_detail and has_time:
            return True

    if len(useful_lines) == 1:
        one = useful_lines[0]
        if not line_has_summary_task_signal(one) and re.search(r"[\u4e00-\u9fffA-Za-z]", one):
            detail_words = (
                TRAINING_KEYWORDS
                + POSITIONING_KEYWORDS
                + FERRY_KEYWORDS
                + STOP_KEYWORDS
                + ATTENDANCE_KEYWORDS
                + STANDBY_KEYWORDS
            )
            if any(k in one for k in detail_words):
                return True

    return False


def cards_have_real_detail(cards: list, header: str, fallback_text: str = "") -> bool:
    if not cards:
        return False

    for card in cards:
        text = normalize_text(card.get("text", ""))
        if not text:
            continue

        if day_block_has_real_detail(text, header, fallback_text=fallback_text):
            return True

    return False


def wait_for_real_day_detail(page, header: str, next_header=None, fallback_text: str = "", max_wait_ms: int = 10000):
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

    return last_block, last_cards, has_real_detail


def expand_day_get_real_detail(page, header: str, next_header=None, fallback_text: str = "", retries: int = 5):
    best_block = ""
    best_cards = []
    expanded_final = False

    for attempt in range(1, retries + 1):
        strategy = (attempt - 1) % 5
        logger.info(f"展开 {header} 尝试 {attempt}/{retries}，点击策略 {strategy}")

        expanded = expand_day(page, header, strategy=strategy)

        if not expanded:
            logger.warning(f"{header} 点击展开失败，strategy={strategy}")
            random_like_wait(page, 800, 300)
            continue

        expanded_final = True

        try:
            page.screenshot(
                path=os.path.join(ARTIFACT_DIR, f"expand_{safe_name(header)}_attempt_{attempt}_strategy_{strategy}.png"),
                full_page=True,
            )
        except Exception:
            pass

        day_block, cards, has_real_detail = wait_for_real_day_detail(
            page,
            header,
            next_header=next_header,
            fallback_text=fallback_text,
            max_wait_ms=12000 + attempt * 2500,
        )

        save_text(
            f"expand_{safe_name(header)}_attempt_{attempt}_block.txt",
            day_block,
        )

        save_text(
            f"expand_{safe_name(header)}_attempt_{attempt}_cards.txt",
            "\n\n==========\n\n".join([f"[card]\n{c.get('text', '')}" for c in cards]),
        )

        if day_block:
            best_block = day_block
        if cards:
            best_cards = cards

        if has_real_detail:
            logger.info(f"{header} 已抓到真实详情")
            return True, best_block, best_cards, True

        logger.warning(f"{header} 本次只抓到摘要或空内容，准备换策略重试")

        random_like_wait(page, 800 + attempt * 250, 500)

    return expanded_final, best_block, best_cards, False


def classify_card_kind(card_text: str, day_header: str = "") -> str:
    text = normalize_text(card_text)

    if has_any_keyword(text, POSITIONING_KEYWORDS):
        return "positioning"

    if has_any_keyword(text, FERRY_KEYWORDS):
        return "ferry"

    if has_any_keyword(text, TRAINING_KEYWORDS):
        return "training"

    if has_any_keyword(text, STOP_KEYWORDS):
        return "stop"

    if has_any_keyword(text, ATTENDANCE_KEYWORDS):
        return "attendance"

    if has_any_keyword(text, STANDBY_KEYWORDS):
        return "standby"

    flight_no = FLIGHT_NO_RE.search(text)

    has_flight_structure = (
        "航班动态" in text
        or bool(REG_AND_MODEL_RE.search(text))
        or len(ICAO_RE.findall(text)) >= 2
    )

    if flight_no and has_flight_structure:
        return "flight"

    return "generic"


def task_type_from_kind(kind: str) -> str:
    return {
        "positioning": "置位",
        "ferry": "摆渡",
        "training": "训练",
        "flight": "航班",
        "stop": "停飞",
        "attendance": "考勤",
        "standby": "待命",
        "generic": "其他",
    }.get(kind, "其他")


def task_bucket(task_type: str) -> str:
    return {
        "航班": "flight",
        "置位": "positioning",
        "训练": "training",
        "摆渡": "ferry",
        "停飞": "other",
        "考勤": "other",
        "待命": "other",
        "备份": "other",
        "其他": "other",
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


def is_card_start_line(line: str, prev_line: str = "") -> bool:
    line = normalize_text(line)

    if not line:
        return False

    if is_old_style_header_line(line) or is_flight_line(line):
        return True

    if TIME_RANGE_RE.search(line) and line_has_task_keyword(line):
        return True

    if TIME_RANGE_RE.search(line) and ("Grounding" in line or "grounding" in line or "停飞" in line):
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

        cards.append({"text": "\n".join(chunk).strip()})
        current = []

    for i, line in enumerate(lines):
        prev = lines[i - 1] if i > 0 else ""
        is_start = is_card_start_line(line, prev)

        if is_start and current:
            flush_current()

        current.append(line)

    flush_current()

    return [c for c in cards if c["text"]]


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

            if re.fullmatch(r"[\u4e00-\u9fff]{2,10}", left):
                left_icao = AIRPORT_CN_TO_ICAO.get(left, "")
                if left_icao == dep_icao or (not dep_cn and not left_icao):
                    dep_cn = left

            if re.fullmatch(r"[\u4e00-\u9fff]{2,10}", right):
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

    if is_bad_title_text(token):
        return False

    if LATIN_PERSON_RE.fullmatch(token):
        return True

    if ZH_TAGGED_NAME_RE.fullmatch(token):
        return True

    if ZH_NAME_WITH_ROLE_RE.fullmatch(token):
        return True

    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}[0-9A-Za-z]?", token):
        return True

    return False


def is_non_person_name_noise(token: str) -> bool:
    token = normalize_text(token)

    if not token:
        return True

    # 非 R 的单字母标记先去掉，例如 衡佳远(B) -> 衡佳远
    token_no_non_r_tag = re.sub(r"\((?!R\))[A-Z]\)", "", token)
    plain = SHORT_ROLE_RE.sub("", token_no_non_r_tag)
    plain = normalize_text(plain)

    if not plain:
        return True

    if is_bad_title_text(plain):
        return True

    if plain in ROLE_WORDS or plain in TASK_TITLE_WORDS or plain in GENERIC_TASK_WORDS:
        return True

    if FLIGHT_NO_RE.fullmatch(plain):
        return True

    if REG_ONLY_RE.fullmatch(plain) or REG_MODEL_RE.fullmatch(plain):
        return True

    if MODEL_ONLY_RE.fullmatch(plain):
        return True

    if ICAO_RE.fullmatch(plain):
        return True

    if TIME_RANGE_RE.search(plain) or re.fullmatch(r"\d{2}:\d{2}", plain):
        return True

    if "航班动态" in plain:
        return True

    if plain in AIRPORT_CN_TO_ICAO:
        return True

    if plain in AIRPORT_ICAO_TO_CN:
        return True

    # 过滤机场中文名拼在一起的航线串，例如 上海浦东名古屋中部 / 名古屋中部上海浦东
    if re.fullmatch(r"[\u4e00-\u9fff]{4,40}", plain):
        matched_names = []
        temp = plain

        for airport_name in AIRPORT_NAMES:
            if airport_name and airport_name in temp:
                matched_names.append(airport_name)
                temp = temp.replace(airport_name, "", 1)

        if len(matched_names) >= 2 and not temp:
            return True

        # 如果包含一个已知机场名，且整体很长，也大概率是航线串，
        # 例如“上海浦东某某新机场”，不能拆成姓名。
        if len(matched_names) >= 1 and len(plain) >= 7:
            return True

    return False


def normalize_person_display_token(token: str) -> str:
    token = normalize_text(token)
    # 保留 (R)，去掉其它单字母标记，避免 衡佳远(B) 这种显示进人员名单。
    token = re.sub(r"\((?!R\))[A-Z]\)", "", token)
    return normalize_text(token)


def is_summary_only_card(card_text: str, day_header: str = "") -> bool:
    lines = [normalize_text(x) for x in normalize_text(card_text).splitlines() if normalize_text(x)]

    if len(lines) != 1:
        return False

    line = lines[0]

    if day_header and line.startswith(day_header):
        line = normalize_text(line[len(day_header):])

    if not line:
        return False

    # 摘要行一般是：航班 11:00- 17:10 / 训练 09:00-17:30
    if not line_has_summary_task_signal(line):
        return False

    # 只要有真实航班号、注册号、机型、航班动态，就不是摘要兜底。
    if FLIGHT_NO_RE.search(line):
        return False

    if REG_ONLY_RE.search(line) or REG_AND_MODEL_RE.search(line) or MODEL_ONLY_RE.search(line):
        return False

    if "航班动态" in line:
        return False

    return True

def normalize_people_output(items: list) -> list:
    normalized = []

    for x in items:
        x = normalize_person_display_token(x)

        if not x:
            continue

        if is_non_person_name_noise(x):
            continue

        normalized.append(x)

    # 如果已经有 田鸿飞(R)，就不要再显示无角色版 田鸿飞。
    tagged_bases = set()
    for x in normalized:
        if SHORT_ROLE_RE.search(x):
            base = normalize_text(SHORT_ROLE_RE.sub("", x))
            if base:
                tagged_bases.add(base)

    out = []
    seen = set()

    for x in normalized:
        base = normalize_text(SHORT_ROLE_RE.sub("", x))

        if base in tagged_bases and not SHORT_ROLE_RE.search(x):
            continue

        if x not in seen:
            out.append(x)
            seen.add(x)

    return out

def contains_suspicious_half_name(token: str) -> bool:
    token = normalize_text(token)

    m_role = SHORT_ROLE_RE.search(token)
    if m_role:
        token = token.replace(m_role.group(0), "")

    if len(token) <= 1:
        return True

    risky_prefixes = {
        name[:2]
        for name in KNOWN_PEOPLE
        if isinstance(name, str) and len(name) >= 3
    }

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

    if len(text) > 12:
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

        candidates.append((score_compact_split(tokens), tokens))

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

    if len(line) > 12:
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
    all_normal_zh = all(re.fullmatch(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?", x) for x in best)

    if has_anchor or has_role:
        return best

    if 2 <= len(best) <= 4 and all_normal_zh:
        pure_len = len(SHORT_ROLE_RE.sub("", line))
        if pure_len <= 8:
            return best

    return []


def get_surname_lengths_at(text: str, idx: int) -> list:
    lens = []

    for s in COMPOUND_SURNAMES:
        if text.startswith(s, idx):
            lens.append(len(s))

    if idx < len(text) and text[idx] in COMMON_SURNAMES:
        lens.append(1)

    return sorted(set(lens), reverse=True)


def split_chinese_flight_people_by_surname(text: str) -> list:
    text = standardize_people_text(text)
    text = SHORT_ROLE_RE.sub("", text)
    text = normalize_text(text)

    if not text:
        return []

    if is_bad_title_text(text):
        return []

    if not re.fullmatch(r"[\u4e00-\u9fff]{2,24}", text):
        return [text]

    if len(text) > 15:
        return [text]

    memo = {}

    def dfs(idx: int):
        if idx == len(text):
            return [[]]

        if idx in memo:
            return memo[idx]

        remaining = len(text) - idx

        if remaining == 1:
            return []

        surname_lengths = get_surname_lengths_at(text, idx)
        if not surname_lengths:
            return []

        results = []

        for surname_len in surname_lengths:
            candidate_name_lens = [surname_len + 2, surname_len + 1]

            if remaining == 4 and surname_len == 1:
                candidate_name_lens = [2, 3]

            for name_len in candidate_name_lens:
                if name_len > remaining:
                    continue
                if name_len < surname_len + 1:
                    continue

                rest = remaining - name_len
                if rest == 1:
                    continue

                name = text[idx:idx + name_len]

                if len(name) < 2 or len(name) > 4:
                    continue

                tails = dfs(idx + name_len)

                for tail in tails:
                    results.append([name] + tail)

        memo[idx] = results
        return results

    candidates = dfs(0)

    if not candidates:
        return [text]

    def score_candidate_names(names: list) -> int:
        score = 0

        for n in names:
            if n in KNOWN_PEOPLE:
                score += 20
            if len(n) == 3:
                score += 5
            elif len(n) == 2:
                score += 4
            elif len(n) == 4:
                score += 2

        if 2 <= len(names) <= 5:
            score += 5
        else:
            score -= 10

        if any(contains_suspicious_half_name(x) for x in names):
            score -= 50

        return score

    best = max(candidates, key=score_candidate_names)

    if len(best) <= 1:
        return [text]

    if any(contains_suspicious_half_name(x) for x in best):
        return [text]

    return best


def parse_people_line_conservatively(line: str):
    line = standardize_people_text(line)

    if not line:
        return "skip", []

    if is_bad_title_text(line):
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

    if LATIN_PERSON_RE.fullmatch(line) or ZH_TAGGED_NAME_RE.fullmatch(line):
        return "split", [line]

    if not has_clear_delimiters(line):
        if re.fullmatch(r"[\u4e00-\u9fff]{4,15}", line):
            surname_split = split_chinese_flight_people_by_surname(line)
            if surname_split and len(surname_split) > 1:
                return "split", surname_split

        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?", line):
            if contains_suspicious_half_name(line):
                return "keep", [line]
            return "split", [line]

        if re.fullmatch(r"[\u4e00-\u9fff()A-Z]{4,200}", line):
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



def split_compact_people_tokens(text: str) -> list:
    """
    拆分无分隔符的中文人员串，支持真实姓名后的字母/数字后缀：
    王健林官亮段洋硕 -> 王健林 / 官亮 / 段洋硕
    张磊A段洋硕 -> 张磊A / 段洋硕
    """
    text = standardize_people_text(text)
    text = re.sub(r"\s+", "", text)

    if not text:
        return []

    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}[0-9A-Za-z]?", text):
        return [text]

    if len(text) > 30:
        return [text]

    memo = {}

    def dfs(pos: int):
        if pos == len(text):
            return [[]]
        if pos in memo:
            return memo[pos]
        if not ("\u4e00" <= text[pos] <= "\u9fff"):
            return []

        results = []
        surname_lengths = get_surname_lengths_at(text, pos)

        for surname_len in surname_lengths:
            for chinese_len in (surname_len + 2, surname_len + 1):
                end = pos + chinese_len
                if end > len(text):
                    continue

                base = text[pos:end]
                if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", base):
                    continue

                token = base
                next_pos = end

                # 允许姓名后的真实字母/数字后缀，例如 张磊A、王磊1。
                if next_pos < len(text) and re.fullmatch(r"[0-9A-Za-z]", text[next_pos]):
                    token += text[next_pos]
                    next_pos += 1

                if len(text) - next_pos == 1:
                    continue

                for tail in dfs(next_pos):
                    results.append([token] + tail)

        memo[pos] = results
        return results

    candidates = dfs(0)
    if not candidates:
        return [text]

    def candidate_key(names: list):
        score = 0
        base_lengths = []

        for name in names:
            base = re.sub(r"[0-9A-Za-z]$", "", name)
            base_lengths.append(len(base))

            if base in KNOWN_PEOPLE:
                score += 30
            if len(base) == 3:
                score += 6
            elif len(base) == 2:
                score += 5
            elif len(base) == 4:
                score += 2

            if re.search(r"[0-9A-Za-z]$", name):
                score += 1

            if contains_suspicious_half_name(base):
                score -= 50

        if 2 <= len(names) <= 6:
            score += 5
        else:
            score -= 10

        # 同分时优先让靠前姓名更完整：
        # 王健林/官亮 优于 王健/林官亮。
        return score, tuple(base_lengths)

    best = max(candidates, key=candidate_key)

    if any(contains_suspicious_half_name(re.sub(r"[0-9A-Za-z]$", "", x)) for x in best):
        return [text]

    return best


def parse_compact_people_with_roles(line: str) -> list:
    """
    按角色括号切分人员串，角色只附着到括号前最后一个姓名。
    避免把“王健林段伟(R)”贪婪识别成“健林段伟(R)”。
    """
    line = standardize_people_text(line)
    if not line:
        return []

    markers = list(ROLE_PAREN_RE.finditer(line))
    if not markers:
        return split_compact_people_tokens(line)

    out = []
    cursor = 0

    for marker in markers:
        chunk = re.sub(r"\s+", "", line[cursor:marker.start()])
        tokens = split_compact_people_tokens(chunk) if chunk else []

        if tokens:
            tokens[-1] = tokens[-1] + marker.group(0)
            out.extend(tokens)

        cursor = marker.end()

    tail = re.sub(r"\s+", "", line[cursor:])
    if tail:
        out.extend(split_compact_people_tokens(tail))

    return normalize_people_output(out)


def parse_people_line_flight(line: str) -> list:
    line = standardize_people_text(line)

    if not line:
        return []

    if is_bad_title_text(line):
        return []

    # 角色括号内部可能含逗号，例如 (T2,R)/(P,B)；
    # 必须先按角色边界解析，不能先把括号里的逗号当作人员分隔符。
    if ROLE_PAREN_RE.search(line):
        return normalize_people_output(parse_compact_people_with_roles(line))

    if has_clear_delimiters(line):
        parts = split_by_clear_delimiters(line)
        valid = []

        for p in parts:
            p = normalize_text(p)
            if not p or is_bad_title_text(p):
                continue
            if looks_like_person_token(p):
                valid.append(p)

        return normalize_people_output(valid)

    return normalize_people_output(parse_compact_people_with_roles(line))


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

        if "航班动态" in line or "查看更多" in line or TIME_RANGE_RE.search(line):
            continue

        if re.fullmatch(r"\d{2}:\d{2}", line) or len(line) == 1:
            continue

        if is_non_person_name_noise(line):
            continue

        # 外籍姓名先单独提取。
        latin_tagged = []
        if not re.search(r"[\u4e00-\u9fff]", line):
            latin_tagged = LATIN_PERSON_RE.findall(line)

        if latin_tagged:
            for token in latin_tagged:
                token = normalize_person_display_token(token)
                if token and not is_non_person_name_noise(token):
                    people.append(token)

            line = normalize_text(LATIN_PERSON_RE.sub("", line))
            if not line:
                continue

        # 中文紧凑名单统一由角色边界解析，避免正则贪婪吞掉前一个姓名。
        result = parse_people_line_flight(line)
        if result:
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

    for keyword in ["去", "前往", "至", "返回"]:
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

    if is_bad_title_text(line):
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

        if is_bad_title_text(line):
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

        if is_title_like and not is_bad_title_text(line):
            extra_lines.append(line)

    people = normalize_people_output(people)
    extra_lines = normalize_people_output(extra_lines)

    return people, extra_lines


def should_block_new_dirty_grounding(item: dict) -> bool:
    title_text = normalize_text(item.get("title_text", ""))
    raw_card_text = normalize_text(item.get("raw_card_text", ""))
    people = item.get("people_lines", [])
    location = normalize_text(item.get("location", ""))
    extra_lines = item.get("extra_lines", [])

    if item.get("task_type") not in {"停飞", "考勤", "其他"}:
        return False

    grounding_like = (
        "Grounding" in title_text
        or "grounding" in title_text
        or "Grounding" in raw_card_text
        or "grounding" in raw_card_text
        or "停飞" in title_text
    )

    people_bad = (not people) or all(is_bad_title_text(p) for p in people)
    no_useful_location = (not location) or is_bad_title_text(location)
    no_useful_extra = not [x for x in extra_lines if not is_bad_title_text(x)]
    weak_title = title_text in {"停飞Grounding", "Grounding", "grounding", "停飞"} or is_bad_title_text(title_text)

    if grounding_like and people_bad and no_useful_location and no_useful_extra and weak_title:
        return True

    return False


def parse_generic_card(card_text: str, day_header: str, page_year: int, day_task_text: str, forced_kind: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]

    if not lines:
        return None

    date_info = extract_date(day_header, page_year)

    if not date_info:
        return None

    year, month, day_num = date_info

    task_type = task_type_from_kind(forced_kind)
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

            if suffix and not is_bad_title_text(suffix):
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

            if is_bad_title_text(candidate):
                continue

            if re.search(r"[\u4e00-\u9fffA-Za-z]", candidate):
                title_text = strip_time_from_title(candidate)
                consumed_idx.add(look_back)
                break

    if not title_text and time_line_prefix and not is_bad_title_text(time_line_prefix):
        title_text = strip_time_from_title(time_line_prefix)

    dep_icao_seq = [line for line in lines if ICAO_RE.fullmatch(line)]

    if len(dep_icao_seq) >= 2:
        dep = dep_icao_seq[0]
        arr = dep_icao_seq[-1]
        dep_cn = AIRPORT_ICAO_TO_CN.get(dep, "")
        arr_cn = AIRPORT_ICAO_TO_CN.get(arr, "")

    if forced_kind in {"ferry", "positioning"} and (not dep_cn or not arr_cn):
        for line in lines:
            if any(x in line for x in TRANSPORT_HINT_WORDS) or any(name in line for name in AIRPORT_NAMES):
                dep_cn2, arr_cn2 = _parse_ferry_route_from_description(line)
                dep_cn = dep_cn or dep_cn2
                arr_cn = arr_cn or arr_cn2

                if dep_cn or arr_cn:
                    break

    if dep and dep_cn:
        add_airport_alias(dep, dep_cn)

    if arr and arr_cn:
        add_airport_alias(arr, arr_cn)

    if forced_kind in {"ferry", "positioning"}:
        if dep_cn and arr_cn:
            title_text = f"{dep_cn}→{arr_cn}"
        elif dep and arr:
            title_text = f"{dep}→{arr}"
        elif not title_text:
            title_text = task_type

    if not title_text:
        for line in lines:
            line_clean = strip_time_from_title(line)

            if is_bad_title_text(line_clean):
                continue

            if (
                line_clean
                and line_clean not in TASK_TITLE_WORDS
                and not ICAO_RE.fullmatch(line_clean)
                and not MODEL_ONLY_RE.fullmatch(line_clean)
            ):
                title_text = line_clean
                break

    people_lines, extra_lines = extract_people_lines_generic(
        lines,
        consumed_idx,
        title_text=title_text,
        location=location,
    )

    if task_type in {"停飞", "考勤"}:
        people_lines = [p for p in people_lines if not is_bad_title_text(p)]

        if is_bad_title_text(title_text):
            title_text = task_type

    if not start_time or not end_time:
        return None

    start_dt, valid_start = make_datetime_safe(year, month, day_num, start_time)
    end_dt, valid_end = make_datetime_safe(year, month, day_num, end_time)

    if not valid_start or not valid_end:
        return None

    diff_minutes = (end_dt - start_dt).total_seconds() / 60

    if next_day or diff_minutes < 0:
        end_dt += timedelta(days=1)

    item = {
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
        "kind": forced_kind,
    }

    if should_block_new_dirty_grounding(item):
        logger.info(f"拦截旧错误样式新生成：{day_header} | {title_text}")
        return None

    return item


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
        checkin_place=checkin_place,
    )
    people_lines = extract_people_lines_flight(card_text)
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
        "task_type": "航班",
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
        "kind": "flight",
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

    if item["task_type"] in {"摆渡", "置位"}:
        if dep_cn and arr_cn:
            return f"{icon} {dep_cn}→{arr_cn}{suffix}"
        if dep and arr:
            return f"{icon} {dep}→{arr}{suffix}"

    if item["task_type"] == "停飞":
        clean_title = re.sub(
            r"\s*00:00\s*[~～\-–—]\s*(17:30|23:59)\s*$",
            "",
            title_text,
        ).strip()
        clean_title = clean_title.replace("Grounding", "").replace("grounding", "").strip()

        if clean_title and not is_bad_title_text(clean_title):
            return f"{icon} {clean_title}"

        return f"{icon} 停飞"

    if title_text and not is_bad_title_text(title_text):
        return f"{icon} {title_text}"

    return f"{icon} {item['task_type']}"


def build_description(item: dict) -> str:
    lines = [item["day_header"], f"类型：{item['task_type']}"]

    if item["flight_no"]:
        lines.append(f"航班：{item['flight_no']}")
    elif item.get("title_text") and not is_bad_title_text(item.get("title_text", "")):
        lines.append(f"事项：{item['title_text']}")

    if item["dep_cn"] and item["arr_cn"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"航线：{item['dep_cn']} → {item['arr_cn']}{cross}")
    elif item["dep"] and item["arr"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"航线：{item['dep']} → {item['arr']}{cross}")

    if item["location"] and not is_bad_title_text(item["location"]):
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

    clean_extra = [x for x in item["extra_lines"] if not is_bad_title_text(x)]
    if clean_extra:
        lines.append("")
        lines.append("说明：")
        for x in clean_extra:
            lines.append(f"• {x}")

    clean_people = normalize_people_output(item["people_lines"])
    if clean_people:
        lines.append("")
        lines.append("人员名单：")
        for p in clean_people:
            lines.append(f"• {p}")

    return "\n".join(lines)


def stable_uid_seed(item: dict) -> str:
    date_key = item["start_dt"].strftime("%Y-%m-%d")
    task_type = item["task_type"]
    flight_no = item.get("flight_no", "")
    time_key = f"{item.get('start_time', '')}-{item.get('end_time', '')}"
    route_key = f"{item.get('dep_cn', '')}-{item.get('arr_cn', '')}-{item.get('dep', '')}-{item.get('arr', '')}"
    loc_key = normalize_text(item.get("location", ""))
    reg_key = normalize_text(item.get("reg", ""))
    model_key = normalize_text(item.get("model", ""))

    stable_parts = [
        date_key,
        task_type,
        time_key,
        flight_no,
        route_key,
        loc_key,
        reg_key,
        model_key,
    ]

    if not flight_no and not route_key.replace("-", "") and not loc_key:
        stable_parts.append(normalize_text(item.get("title_text", "")))

    seed = "|".join(stable_parts)
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

    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid_base}@crew-calendar",
        f"DTSTAMP:{now_utc}",
        f"CREATED:{now_utc}",
        f"LAST-MODIFIED:{now_utc}",
        "SEQUENCE:1",
        f"SUMMARY:{escape_ics_text(title)}",
        f"DTSTART;TZID=Asia/Shanghai:{format_dt_local(item['start_dt'])}",
        f"DTEND;TZID=Asia/Shanghai:{format_dt_local(item['end_dt'])}",
        f"DESCRIPTION:{escape_ics_text(desc)}",
        f"X-CONTENT-SIGNATURE:{exact_content_signature(item)}",
    ]

    if item["location"] and not is_bad_title_text(item["location"]):
        lines.append(f"LOCATION:{escape_ics_text(item['location'])}")

    lines.extend(
        [
            "BEGIN:VALARM",
            f"TRIGGER:-PT{ALARM_MINUTES}M",
            f"DESCRIPTION:{escape_ics_text(alarm_desc)}",
            "ACTION:DISPLAY",
            "END:VALARM",
            "END:VEVENT",
        ]
    )

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
    text = text.replace("Grounding", "").replace("grounding", "")
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

    if "航班：" in block:
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

    if any(bad in block for bad in BAD_TITLE_WORDS):
        score -= 100

    if "Grounding" in block and ("00:00" in block):
        score -= 20

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
    if item.get("title_text") and not is_bad_title_text(item.get("title_text", "")):
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

    content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Crew Calendar//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Crew Calendar",
        "X-WR-TIMEZONE:Asia/Shanghai",
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
            pass

    if old_text == final_text:
        logger.info(f"{filename} 内容未变化")
        return False

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_text)

    logger.info(f"写入 {filename}: {len(ordered)} 个事件")
    return True



def split_concat_airport_route(text: str):
    """
    解析类似：上海浦东名古屋中部 / 乌兰巴托成吉思汗上海浦东。
    返回：dep_cn, arr_cn。核心原则：按页面里的航线文字拆，不按航班号排序。

    修复点：
    - 支持“乌兰巴托成吉思汗”。
    - 避免把“上海浦东乌兰巴托成吉思汗”误拆成“上海浦东→浦东”。
    - 只接受两个完整、不重叠的机场名。
    """
    text = normalize_text(text)
    text = TIME_RANGE_RE.sub("", text)
    # 修复：跨日航段行可能残留 (+1)，例如“上海浦东大连周水子 22:50-00:55(+1)”。
    # 如果不先去掉 (+1)，后面的纯中文航线匹配会失败，导致第三段 9C8981 被漏掉。
    text = text.replace("(+1)", "").replace("（+1）", "")
    text = FLIGHT_NO_RE.sub("", text)
    text = REG_AND_MODEL_RE.sub("", text)
    text = REG_ONLY_RE.sub("", text)
    text = MODEL_ONLY_RE.sub("", text)
    text = re.sub(r"[\s→\-—–~～:：]+", "", text)

    if not text or not re.fullmatch(r"[\u4e00-\u9fff]{4,40}", text):
        return "", ""

    # 第一优先级：完整前缀 + 完整后缀。
    # 例如：上海浦东 + 乌兰巴托成吉思汗。
    for dep_name in AIRPORT_NAMES:
        if not dep_name or not text.startswith(dep_name):
            continue
        rest = text[len(dep_name):]
        if not rest:
            continue
        for arr_name in AIRPORT_NAMES:
            if arr_name and rest == arr_name:
                return dep_name, arr_name

    # 第二优先级：枚举两个不重叠机场名，要求拼起来正好覆盖全文。
    # 这样可以避免“上海浦东...浦东”这种子串误判。
    candidates = []
    for dep_name in AIRPORT_NAMES:
        if not dep_name:
            continue
        dep_start = text.find(dep_name)
        if dep_start != 0:
            continue
        dep_end = dep_start + len(dep_name)
        for arr_name in AIRPORT_NAMES:
            if not arr_name:
                continue
            arr_start = text.find(arr_name, dep_end)
            if arr_start != dep_end:
                continue
            arr_end = arr_start + len(arr_name)
            if arr_end != len(text):
                continue
            candidates.append((len(dep_name) + len(arr_name), dep_name, arr_name))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1], candidates[0][2]

    # 第三优先级：已知机场 + 未知机场。
    # 这是为了以后遇到机场字典里暂时没有的新机场，也能按页面原文拆。
    # 例如：上海浦东某某新机场 -> 上海浦东 / 某某新机场；
    #       某某新机场上海浦东 -> 某某新机场 / 上海浦东。
    # 只在航线字符串本身非常干净时启用，避免把人员名单误当机场。
    if re.fullmatch(r"[\u4e00-\u9fff]{6,40}", text):
        bad_route_words = set(TRAINING_KEYWORDS + STOP_KEYWORDS + ATTENDANCE_KEYWORDS + STANDBY_KEYWORDS)
        if not any(w in text for w in bad_route_words):
            for dep_name in AIRPORT_NAMES:
                if not dep_name or not text.startswith(dep_name):
                    continue
                rest = normalize_text(text[len(dep_name):])
                if 2 <= len(rest) <= 20 and re.fullmatch(r"[\u4e00-\u9fff]{2,20}", rest):
                    if rest not in ROLE_WORDS and rest not in TASK_TITLE_WORDS:
                        return dep_name, rest

            for arr_name in AIRPORT_NAMES:
                if not arr_name or not text.endswith(arr_name):
                    continue
                prefix = normalize_text(text[:len(text) - len(arr_name)])
                if 2 <= len(prefix) <= 20 and re.fullmatch(r"[\u4e00-\u9fff]{2,20}", prefix):
                    if prefix not in ROLE_WORDS and prefix not in TASK_TITLE_WORDS:
                        return prefix, arr_name

    return "", ""


def extract_route_time_segments_from_day_block(day_block: str) -> list:
    """
    从整天 day_block 中提取多个航段：
    上海浦东名古屋中部 11:00-13:25
    名古屋中部上海浦东 14:25-17:10
    支持 1-4 段，也允许更多，按页面顺序返回。
    """
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    segments = []
    seen = set()

    for line in lines:
        if not TIME_RANGE_RE.search(line):
            continue

        if "航班动态" in line:
            continue

        if is_summary_only_card(line):
            continue

        if any(k in line for k in TRAINING_KEYWORDS + STOP_KEYWORDS + ATTENDANCE_KEYWORDS + STANDBY_KEYWORDS):
            continue

        # 去掉开头的航班号/机型注册号等噪音，只保留可能的航线文字。
        route_part = TIME_RANGE_RE.sub("", line)
        route_part = FLIGHT_NO_RE.sub("", route_part)
        route_part = REG_AND_MODEL_RE.sub("", route_part)
        route_part = REG_ONLY_RE.sub("", route_part)
        route_part = MODEL_ONLY_RE.sub("", route_part)
        route_part = normalize_text(route_part)

        dep_cn, arr_cn = split_concat_airport_route(route_part)
        if not dep_cn or not arr_cn:
            continue

        m = TIME_RANGE_RE.search(line)
        if not m:
            continue

        key = (dep_cn, arr_cn, m.group(1), m.group(2))
        if key in seen:
            continue
        seen.add(key)

        segments.append(
            {
                "dep_cn": dep_cn,
                "arr_cn": arr_cn,
                "dep": AIRPORT_CN_TO_ICAO.get(dep_cn, ""),
                "arr": AIRPORT_CN_TO_ICAO.get(arr_cn, ""),
                "start_time": m.group(1),
                "end_time": m.group(2),
                "raw_line": line,
            }
        )

    # 航段顺序以页面顺序为主；如果页面读取顺序偶发错乱，再用起飞时间兜底从早到晚排序。
    # Python 排序稳定：同一时间仍保持原页面顺序。
    def _time_key(seg):
        try:
            hh, mm = map(int, seg.get("start_time", "99:99").split(":"))
            return hh * 60 + mm
        except Exception:
            return 9999

    ordered_by_time = sorted(segments, key=_time_key)
    if [x.get("start_time") for x in ordered_by_time] != [x.get("start_time") for x in segments]:
        save_text("segments_reordered_by_time.txt", "\n".join([x.get("raw_line", "") for x in ordered_by_time]))
        return ordered_by_time

    return segments


def extract_flight_numbers_from_day_block(day_block: str) -> list:
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    out = []
    seen = set()

    for line in lines:
        # 优先取独立航班号行，避免描述里重复出现造成乱序。
        if is_flight_line(line) and line not in seen:
            out.append(line)
            seen.add(line)

    if out:
        return out

    for m in FLIGHT_NO_RE.finditer(day_block):
        fn = m.group(0)
        if fn not in seen:
            out.append(fn)
            seen.add(fn)

    return out




def extract_segment_checkins_from_day_block(day_block: str, segments: list) -> list:
    """
    多航段当天，逐段绑定自己附近的签到时间。
    规则：按页面行顺序扫描，遇到“HH:MM 地点 航班动态”记录为当前签到；
    遇到某段航线时间行时，把最近一次签到绑定给该航段。
    这样避免 9C8981 继承当天第一段 9C6391 的 07:55 签到。
    """
    lines = [normalize_text(x) for x in day_block.splitlines() if normalize_text(x)]
    out = [{"checkin_time": "", "checkin_place": ""} for _ in segments]
    assigned = set()

    current_time = ""
    current_place = ""

    def _parse_checkin_line(line: str):
        # 标准：07:55 上海浦东 航班动态 / 21:00 上海浦东 航班动态
        m = re.search(r"^(\d{2}:\d{2})(?:\s+([^\s]{2,30}))?\s+航班动态$", line)
        if not m:
            return "", ""

        hhmm = m.group(1)
        place = (m.group(2) or "").strip()

        if place in ["A319", "A320", "A321", "航班动态"]:
            place = ""

        if FLIGHT_NO_RE.fullmatch(place):
            place = ""

        return hhmm, place

    def _line_to_segment_key(line: str):
        if not TIME_RANGE_RE.search(line):
            return None

        if "航班动态" in line:
            return None

        if is_summary_only_card(line):
            return None

        route_part = TIME_RANGE_RE.sub("", line)
        route_part = FLIGHT_NO_RE.sub("", route_part)
        route_part = REG_AND_MODEL_RE.sub("", route_part)
        route_part = REG_ONLY_RE.sub("", route_part)
        route_part = MODEL_ONLY_RE.sub("", route_part)
        route_part = normalize_text(route_part)

        dep_cn, arr_cn = split_concat_airport_route(route_part)
        if not dep_cn or not arr_cn:
            return None

        m = TIME_RANGE_RE.search(line)
        if not m:
            return None

        return dep_cn, arr_cn, m.group(1), m.group(2)

    for line in lines:
        ci_time, ci_place = _parse_checkin_line(line)
        if ci_time:
            current_time = ci_time
            current_place = ci_place
            continue

        key = _line_to_segment_key(line)
        if not key:
            continue

        for idx, seg in enumerate(segments):
            if idx in assigned:
                continue

            seg_key = (
                seg.get("dep_cn", ""),
                seg.get("arr_cn", ""),
                seg.get("start_time", ""),
                seg.get("end_time", ""),
            )

            if key != seg_key:
                continue

            # 如果签到行没有地点，例如“11:00 航班动态”，用本航段起飞机场兜底。
            out[idx] = {
                "checkin_time": current_time,
                "checkin_place": current_place or seg.get("dep_cn", ""),
            }
            assigned.add(idx)
            break

    fallback_time, fallback_place = extract_checkin(day_block)

    for idx, seg in enumerate(segments):
        if not out[idx]["checkin_time"]:
            out[idx] = {
                "checkin_time": fallback_time,
                "checkin_place": fallback_place or seg.get("dep_cn", ""),
            }

    return out


def extract_preserved_segment_cards(day_block: str) -> list:
    """读取 DOM 阶段保留下来的每个独立航段卡片。"""
    if SEGMENT_CARD_MARKER not in day_block:
        return []

    parts = day_block.split(SEGMENT_CARD_MARKER)
    cards = []

    for part in parts[1:]:
        text = normalize_text(part)
        if not text:
            continue
        if not FLIGHT_NO_RE.search(text):
            continue
        if not TIME_RANGE_RE.search(text):
            continue
        cards.append(text)

    return cards


def extract_segment_details_from_day_block(day_block: str, flight_numbers: list) -> list:
    """
    为每个航班号提取同一张航段卡片里的签到、注册号、机型和人员名单。
    关键原则：不再把整天第一段的人员/注册号复制给后续所有航段。
    """
    cards = extract_preserved_segment_cards(day_block)
    by_flight = {}
    ordered = []

    for card in cards:
        flight_no = extract_flight_no(card)
        if not flight_no:
            continue

        reg, model = extract_reg_and_model(card)
        checkin_time, checkin_place = extract_checkin(card)
        people_lines = normalize_people_output(extract_people_lines_flight(card))
        card_segments = extract_route_time_segments_from_day_block(card)
        card_segment = card_segments[0] if card_segments else {}

        detail = {
            "flight_no": flight_no,
            "reg": reg,
            "model": model,
            "checkin_time": checkin_time,
            "checkin_place": checkin_place,
            "people_lines": people_lines,
            "dep_cn": card_segment.get("dep_cn", ""),
            "arr_cn": card_segment.get("arr_cn", ""),
            "start_time": card_segment.get("start_time", ""),
            "end_time": card_segment.get("end_time", ""),
            "raw_card_text": card,
        }

        # 同一航班号只取页面中第一张完整卡片。
        if flight_no not in by_flight:
            by_flight[flight_no] = detail
            ordered.append(detail)

    # 返回与 flight_numbers 严格对齐的列表。
    result = []
    used_ordered = set()

    for idx, flight_no in enumerate(flight_numbers):
        detail = by_flight.get(flight_no)

        if detail is None and idx < len(ordered):
            # 极端情况下航班号读取失败，才按页面航段顺序兜底。
            detail = ordered[idx]
            used_ordered.add(idx)

        result.append(detail or {})

    return result


def parse_multi_segment_flight_items(day_header: str, day_block: str, page_year: int) -> list:
    """
    通用多段航班解析。
    每一段的航班号、签到、注册号、机型和人员名单均从同一张航段卡片提取。
    """
    date_info = extract_date(day_header, page_year)
    if not date_info:
        return []

    year, month, day_num = date_info
    flight_numbers = extract_flight_numbers_from_day_block(day_block)
    segments = extract_route_time_segments_from_day_block(day_block)

    if len(flight_numbers) < 2 or len(segments) < 2:
        return []

    count = min(len(flight_numbers), len(segments))
    if count < 2:
        return []

    day_reg, day_model = extract_reg_and_model(day_block)
    day_people = normalize_people_output(extract_people_lines_flight(day_block))
    segment_checkins = extract_segment_checkins_from_day_block(day_block, segments)
    segment_details = extract_segment_details_from_day_block(day_block, flight_numbers)

    items = []

    for i in range(count):
        seg = segments[i]
        flight_no = flight_numbers[i]
        detail = segment_details[i] if i < len(segment_details) else {}

        start_dt, valid_start = make_datetime_safe(year, month, day_num, seg["start_time"])
        end_dt, valid_end = make_datetime_safe(year, month, day_num, seg["end_time"])

        if not valid_start or not valid_end:
            continue

        # 跨日只按当前航段判断，不能污染同一天其它航段。
        seg_next_day_marker = "(+1)" in seg.get("raw_line", "") or "（+1）" in seg.get("raw_line", "")
        if seg_next_day_marker or (end_dt - start_dt).total_seconds() < 0:
            end_dt += timedelta(days=1)

        fallback_checkin = segment_checkins[i] if i < len(segment_checkins) else {}

        checkin_time = detail.get("checkin_time", "") or fallback_checkin.get("checkin_time", "")
        checkin_place = (
            detail.get("checkin_place", "")
            or fallback_checkin.get("checkin_place", "")
            or seg["dep_cn"]
        )

        reg = detail.get("reg", "") or day_reg
        model = detail.get("model", "") or day_model
        people_lines = detail.get("people_lines") or day_people

        item = {
            "day_header": day_header,
            "task_type": "航班",
            "flight_no": flight_no,
            "title_text": "",
            "dep": seg["dep"],
            "arr": seg["arr"],
            "dep_cn": seg["dep_cn"],
            "arr_cn": seg["arr_cn"],
            "start_time": seg["start_time"],
            "end_time": seg["end_time"],
            "checkin_time": checkin_time,
            "checkin_place": checkin_place,
            "location": checkin_place or seg["dep_cn"],
            "model": model,
            "reg": reg,
            "people_lines": people_lines,
            "extra_lines": [],
            "start_dt": start_dt,
            "end_dt": end_dt,
            "raw_card_text": detail.get("raw_card_text") or normalize_text(day_block),
            "kind": "flight",
            "multi_segment": True,
        }
        items.append(item)

    return items


def card_belongs_to_multi_segment_flight(card_text: str) -> bool:
    text = normalize_text(card_text)
    if not text:
        return False

    if is_summary_only_card(text):
        return True

    if FLIGHT_NO_RE.search(text):
        return True

    if "航班动态" in text:
        return True

    if REG_AND_MODEL_RE.search(text) or REG_ONLY_RE.search(text) or MODEL_ONLY_RE.search(text):
        return True

    segments = extract_route_time_segments_from_day_block(text)
    if segments:
        return True

    return False

def build_summary_kind_by_time(cards: list, day_header: str) -> dict:
    """
    将“置位 09:55-12:00”这类摘要卡按时间绑定到真实详情卡。
    只做精确时间匹配，避免把同一天其他正常航班误分类。
    """
    mapping = {}

    for card in cards:
        card_text = card.get("text", "")

        if not is_summary_only_card(card_text, day_header):
            continue

        kind = classify_card_kind(card_text, day_header)

        if kind not in {"positioning", "ferry"}:
            continue

        start_time, end_time = extract_start_end_time(card_text)

        if start_time and end_time:
            mapping[(start_time, end_time)] = kind

    return mapping


def prepare_items(day_blocks, page_year: int) -> list:
    raw_items = []
    classification_log = []

    for day in day_blocks:
        day_header = day["day_header"]
        day_block = day["day_block"]
        cards = day["cards"]
        summary_kind_by_time = build_summary_kind_by_time(cards, day_header)

        # 页面有时同时返回“整块详情卡”和拆出的单航段卡。
        # 记录干净单航段卡，后面跳过同航班同时间的整块卡，避免重复和人员噪声。
        clean_segment_keys = set()
        for clean_card in cards:
            clean_text = clean_card.get("text", "")
            if SEGMENT_CARD_MARKER in clean_text:
                continue
            clean_flight_no = extract_flight_no(clean_text)
            clean_start, clean_end = extract_start_end_time(clean_text)
            if clean_flight_no and clean_start and clean_end:
                clean_segment_keys.add((clean_flight_no, clean_start, clean_end))

        multi_flight_items = parse_multi_segment_flight_items(day_header, day_block, page_year)

        if multi_flight_items:
            classification_log.append(
                f"{day_header} | MULTI_SEGMENT_FLIGHT | count={len(multi_flight_items)}\n"
                + "\n".join(
                    [
                        f"{build_title(item)} | {item['start_time']}-{item['end_time']}"
                        for item in multi_flight_items
                    ]
                )
                + "\n---"
            )
            raw_items.extend(multi_flight_items)

        # 如果同一天已经存在真实详情卡片，就跳过“航班 11:00-17:10”这类摘要兜底卡。
        # 如果已启用多段航班解析，则跳过属于航班详情的卡片，避免重复生成单段航班。
        day_has_real_detail_card = bool(multi_flight_items)
        if not day_has_real_detail_card:
            for c in cards:
                text = normalize_text(c.get("text", ""))
                if not text:
                    continue
                if is_summary_only_card(text, day_header):
                    continue
                k = classify_card_kind(text, day_header)
                if k in {"flight", "training", "positioning", "ferry", "standby", "attendance", "stop"}:
                    day_has_real_detail_card = True
                    break

        for idx, card in enumerate(cards, start=1):
            card_text = card["text"]
            kind = classify_card_kind(card_text, day_header)
            forced_summary_kind = None

            card_flight_no = extract_flight_no(card_text)
            card_start, card_end = extract_start_end_time(card_text)
            card_key = (card_flight_no, card_start, card_end)

            if SEGMENT_CARD_MARKER in card_text and card_key in clean_segment_keys:
                classification_log.append(
                    f"{day_header} | card#{idx} | kind={kind} | title=SKIPPED_COMPOSITE_DUPLICATE\n{card_text}\n---"
                )
                continue

            # 详情卡本身常包含“航班动态”，容易被识别为航班。
            # 若同一天存在时间完全一致的“置位/摆渡”摘要，则以摘要任务类型为准。
            if not is_summary_only_card(card_text, day_header) and kind == "flight":
                card_start, card_end = extract_start_end_time(card_text)
                forced_summary_kind = summary_kind_by_time.get((card_start, card_end))

                if forced_summary_kind in {"positioning", "ferry"}:
                    kind = forced_summary_kind

            if multi_flight_items and card_belongs_to_multi_segment_flight(card_text):
                classification_log.append(
                    f"{day_header} | card#{idx} | kind={kind} | title=SKIPPED_BY_MULTI_SEGMENT\n{card_text}\n---"
                )
                continue

            if day_has_real_detail_card and is_summary_only_card(card_text, day_header):
                classification_log.append(
                    f"{day_header} | card#{idx} | kind={kind} | title=SKIPPED_SUMMARY_DUPLICATE\n{card_text}\n---"
                )
                continue

            if kind == "flight":
                item = parse_flight_card(card_text, day_header, page_year, day_block)
            elif kind in {"positioning", "ferry"} and forced_summary_kind == kind:
                # 详情卡具有完整航班结构，只是任务类型来自同时间摘要。
                # 先按航班卡解析，保留航班号/航线/人员，再覆盖任务类型。
                item = parse_flight_card(card_text, day_header, page_year, day_block)

                if item:
                    item["task_type"] = task_type_from_kind(kind)
                    item["kind"] = kind
            else:
                item = parse_generic_card(
                    card_text,
                    day_header,
                    page_year,
                    day_block,
                    forced_kind=kind,
                )

            if item and card.get("summary_fallback"):
                item["summary_fallback"] = True

                if not item.get("extra_lines"):
                    item["extra_lines"] = []

                item["extra_lines"].append("来源：页面摘要行，未展开到详细任务卡片")

            if item:
                item["people_lines"] = normalize_people_output(item.get("people_lines", []))

            title = build_title(item) if item else "SKIPPED"
            fallback_mark = " | SUMMARY_FALLBACK" if card.get("summary_fallback") else ""

            classification_log.append(
                f"{day_header} | card#{idx} | kind={kind}{fallback_mark} | title={title}\n{card_text}\n---"
            )

            if item:
                raw_items.append(item)

    save_text("classification_log.txt", "\n\n".join(classification_log))

    best_map = {}

    for item in raw_items:
        key = exact_content_signature(item)
        q = event_quality(item)
        item["quality"] = q

        if key not in best_map or q > best_map[key]["quality"]:
            best_map[key] = item

    items = list(best_map.values())

    for item in items:
        item.pop("quality", None)

    items.sort(key=lambda x: (x["start_dt"], build_title(x)))
    return items

def build_version_tag() -> str:
    return datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M")


def merge_history_replace_scraped_dates(filename: str, bucket_items: list, scraped_dates: set, version_tag: str) -> list:
    existing_map = read_existing_events(filename)
    existing_blocks = list(existing_map.values())
    new_blocks = [build_vevent(item, version_tag=version_tag) for item in bucket_items]

    kept_old_blocks = []
    removed_count = 0

    for block in existing_blocks:
        event_date = extract_event_date_from_block(block)

        if event_date in scraped_dates:
            removed_count += 1
            continue

        kept_old_blocks.append(block)

    merged_blocks = kept_old_blocks + new_blocks
    merged_blocks = cleanup_duplicate_blocks(merged_blocks)

    logger.info(
        f"{filename}: scraped_dates={sorted(scraped_dates)} removed_old={removed_count} add_new={len(new_blocks)} final={len(merged_blocks)}"
    )

    return merged_blocks


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

    scraped_dates = {item["start_dt"].strftime("%Y%m%d") for item in total_items}

    save_text("scraped_dates.txt", "\n".join(sorted(scraped_dates)))

    save_text(
        "items_summary.txt",
        "\n".join(
            [
                f"{item['start_dt'].strftime('%Y-%m-%d %H:%M')} | {item['task_type']} | {build_title(item)}"
                for item in total_items
            ]
        ),
    )

    changed_root = False

    changed_root |= write_calendar_from_vevents(
        "flight.ics",
        merge_history_replace_scraped_dates("flight.ics", buckets["flight"], scraped_dates, version_tag),
    )

    changed_root |= write_calendar_from_vevents(
        "positioning.ics",
        merge_history_replace_scraped_dates("positioning.ics", buckets["positioning"], scraped_dates, version_tag),
    )

    changed_root |= write_calendar_from_vevents(
        "training.ics",
        merge_history_replace_scraped_dates("training.ics", buckets["training"], scraped_dates, version_tag),
    )

    changed_root |= write_calendar_from_vevents(
        "ferry.ics",
        merge_history_replace_scraped_dates("ferry.ics", buckets["ferry"], scraped_dates, version_tag),
    )

    changed_root |= write_calendar_from_vevents(
        "other.ics",
        merge_history_replace_scraped_dates("other.ics", buckets["other"], scraped_dates, version_tag),
    )

    changed_root |= write_calendar_from_vevents(
        "crew_schedule.ics",
        merge_history_replace_scraped_dates("crew_schedule.ics", total_items, scraped_dates, version_tag),
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
        [build_vevent(item, version_tag=version_tag) for item in total_items],
    )

    save_text("changed_root_flag.txt", str(changed_root))

    logger.info(
        f"本次抓到 {len(total_items)} 个任务；保留历史，只替换本次抓到日期；分类强约束已启用"
    )


def collect_day_blocks(page) -> list:
    load_all_visible_tasks(page)

    day_headers = get_day_headers(page)
    save_text("day_headers.txt", "\n".join(day_headers))

    summary_task_map = get_day_summary_task_map(page)

    result = []

    for idx, header in enumerate(day_headers):
        next_header = day_headers[idx + 1] if idx + 1 < len(day_headers) else None
        key = safe_name(header)

        expanded = False
        day_block = ""
        cards = []
        has_real_detail = False

        fallback_text = normalize_text(summary_task_map.get(header, ""))

        try:
            expanded, day_block, cards, has_real_detail = expand_day_get_real_detail(
                page,
                header,
                next_header=next_header,
                fallback_text=fallback_text,
                retries=5,
            )

            if has_real_detail:
                logger.info(f"日期 {header} 使用真实详情卡片")
            else:
                logger.warning(f"日期 {header} 未确认真实详情，检查是否需要摘要兜底")

            if not has_real_detail or not cards:
                if fallback_text:
                    logger.warning(f"日期 {header} 最终使用摘要行兜底：{fallback_text}")

                    fallback_cards = split_day_block_into_cards(
                        header,
                        f"{header}\n{fallback_text}",
                    )

                    if fallback_cards:
                        for c in fallback_cards:
                            c["summary_fallback"] = True
                        cards = fallback_cards
                    else:
                        cards = [
                            {
                                "text": fallback_text,
                                "summary_fallback": True,
                            }
                        ]

                    if not day_block:
                        day_block = f"{header}\n{fallback_text}"
                else:
                    logger.warning(f"日期 {header} 没有真实详情，也没有可用摘要兜底")
                    cards = []

            save_text(f"block_{key}.txt", day_block)

            save_text(
                f"cards_{key}.txt",
                "\n\n==========\n\n".join(
                    [
                        f"[card]{' SUMMARY_FALLBACK' if c.get('summary_fallback') else ''}\n{c['text']}"
                        for c in cards
                    ]
                ),
            )

            if cards:
                result.append(
                    {
                        "day_header": header,
                        "day_block": day_block,
                        "cards": cards,
                    }
                )

        except Exception as e:
            logger.error(f"处理日期 {header} 失败: {e}", exc_info=True)

            fallback_text = normalize_text(summary_task_map.get(header, ""))

            if fallback_text:
                logger.warning(f"日期 {header} 异常后使用摘要行兜底：{fallback_text}")

                cards = [
                    {
                        "text": fallback_text,
                        "summary_fallback": True,
                    }
                ]

                day_block = f"{header}\n{fallback_text}"

                save_text(f"block_{key}.txt", day_block)

                save_text(
                    f"cards_{key}.txt",
                    f"[card] SUMMARY_FALLBACK\n{fallback_text}",
                )

                result.append(
                    {
                        "day_header": header,
                        "day_block": day_block,
                        "cards": cards,
                    }
                )

        finally:
            if expanded:
                try:
                    collapse_day(page, header)
                except Exception:
                    pass

    logger.info(f"收集了 {len(result)} 个日期的数据")
    return result


def snapshot_existing_calendars():
    backups = []

    for name in [
        "crew_schedule.ics",
        "flight.ics",
        "ferry.ics",
        "training.ics",
        "positioning.ics",
        "other.ics",
    ]:
        if os.path.exists(name):
            backup_path = os.path.join(ARTIFACT_DIR, f"backup_{name}")
            shutil.copy(name, backup_path)
            backups.append(name)

    save_text("backed_up_files.txt", "\n".join(backups))


def run():
    logger.info("=" * 60)
    logger.info("开始执行航班日历爬虫")
    logger.info("代码版本: multi-task-v15-positioning-time-bound")
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

            page.screenshot(
                path=os.path.join(ARTIFACT_DIR, "after_login.png"),
                full_page=True,
            )
            save_text("after_login.txt", page_text(page))

            open_mission_page(page)

            page.screenshot(
                path=os.path.join(ARTIFACT_DIR, "mission_page_ready.png"),
                full_page=True,
            )
            save_text("mission_body_text.txt", page_text(page))

            page_year = detect_page_year(page)
            save_text("page_year.txt", str(page_year))
            logger.info(f"页面年份: {page_year}")

            day_blocks = collect_day_blocks(page)

            if not day_blocks:
                raise RuntimeError("未抓到任何任务块，停止写入，保护现有 ICS")

            create_multi_calendars_from_blocks(day_blocks, page_year)

            logger.info("=" * 60)
            logger.info("执行完成")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"执行出错: {e}", exc_info=True)
            raise

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
