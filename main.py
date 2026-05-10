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
    "ä¸æµ·è¹æ¡¥": "ZSSS",
    "è¹æ¡¥": "ZSSS",
    "ä¸æµ·æµ¦ä¸": "ZSPD",
    "æµ¦ä¸": "ZSPD",
    "è¥¿å®å¸é³": "ZLXY",
    "å¸é³": "ZLXY",
    "éåºæ±å": "ZUCK",
    "æ±å": "ZUCK",
    "å¤§è¿å¨æ°´å­": "ZYTL",
    "å¨æ°´å­": "ZYTL",
    "æ·±å³å®å®": "ZGSZ",
    "å®å®": "ZGSZ",
    "æµåé¥å¢": "ZSJN",
    "é¥å¢": "ZSJN",
    "åå°æ»¨å¤ªå¹³": "ZYHB",
    "å¤ªå¹³": "ZYHB",
    "æ·®å®æ¶æ°´": "ZSSH",
    "æ¶æ°´": "ZSSH",
    "å¼åæµ©ç¹ç½å¡": "ZBHH",
    "ç½å¡": "ZBHH",
    "é¿æ¥é¾å": "ZYCC",
    "é¾å": "ZYCC",
    "å°å·ä¸­å·": "ZLLL",
    "ä¸­å·": "ZLLL",
    "å¹¿å·ç½äº": "ZGGG",
    "ç½äº": "ZGGG",
    "æ­é³æ½®æ±": "ZGOW",
    "æ½®æ±": "ZGOW",
    "åå®å´å©": "ZGNN",
    "å´å©": "ZGNN",
    "æ¬å·æ³°å·": "ZSYZ",
    "æ¬æ³°": "ZSYZ",
    "å¦é¨é«å´": "ZSAM",
    "é«å´": "ZSAM",
    "æ³å·ææ±": "ZSQZ",
    "ææ±": "ZSQZ",
    "éè¾¹å¾·å´": "VDTI",
    "å¾·å´": "VDTI",
    "ç³å®¶åºæ­£å®": "ZBSJ",
    "æ­£å®": "ZBSJ",
    "å®æ³¢æ ç¤¾": "ZSNB",
    "æ ç¤¾": "ZSNB",
    "å¤©æ´¥æ»¨æµ·": "ZBTJ",
    "æ»¨æµ·": "ZBTJ",
    "ä¸è¥èå©": "ZSDY",
    "ä¸è¥": "ZSDY",
    "åäº¬é¦é½": "ZBAA",
    "é¦é½": "ZBAA",
    "åäº¬å¤§å´": "ZBAD",
    "å¤§å´": "ZBAD",
    "æé½å¤©åº": "ZUTF",
    "å¤©åº": "ZUTF",
    "æé½åæµ": "ZUUU",
    "åæµ": "ZUUU",
    "ææé¿æ°´": "ZPPP",
    "é¿æ°´": "ZPPP",
    "æ­¦æ±å¤©æ²³": "ZHHH",
    "å¤©æ²³": "ZHHH",
    "åäº¬ç¦å£": "ZSNJ",
    "ç¦å£": "ZSNJ",
    "æ­å·è§å±±": "ZSHC",
    "è§å±±": "ZSHC",
    "éå²è¶ä¸": "ZSQD",
    "è¶ä¸": "ZSQD",
    "éå·æ°é": "ZHCC",
    "æ°é": "ZHCC",
    "é¿æ²é»è±": "ZGHA",
    "é»è±": "ZGHA",
    "ç¦å·é¿ä¹": "ZSFZ",
    "é¿ä¹": "ZSFZ",
    "æ²é³æ¡ä»": "ZYTX",
    "æ¡ä»": "ZYTX",
    "å¤ªåæ­¦å®¿": "ZBYN",
    "æ­¦å®¿": "ZBYN",
    "ä¹é²æ¨é½å°çªå ¡": "ZWWW",
    "å°çªå ¡": "ZWWW",
    "æµ·å£ç¾å°": "ZJHK",
    "ç¾å°": "ZJHK",
    "ä¸äºå¤å°": "ZJSY",
    "å¤å°": "ZJSY",
    "åè¥æ°æ¡¥": "ZSOF",
    "æ°æ¡¥": "ZSOF",
    "åææå": "ZSCN",
    "æå": "ZSCN",
    "è´µé³é¾æ´å ¡": "ZUGY",
    "é¾æ´å ¡": "ZUGY",
    "æ¡æä¸¤æ±": "ZGKL",
    "ä¸¤æ±": "ZGKL",
    "åæµ·ç¦æ": "ZGBH",
    "ç¦æ": "ZGBH",
    "ç æµ·éæ¹¾": "ZGSD",
    "éæ¹¾": "ZGSD",
    "æ¹æ±å´å·": "ZGZJ",
    "å´å·": "ZGZJ",
    "åéå´ä¸": "ZSNT",
    "å´ä¸": "ZSNT",
    "å¸¸å·å¥ç": "ZSCG",
    "å¥ç": "ZSCG",
    "æ é¡ç¡æ¾": "ZSWX",
    "ç¡æ¾": "ZSWX",
    "çååæ´": "ZSYN",
    "åæ´": "ZSYN",
    "å¾å·è§é³": "ZSXZ",
    "è§é³": "ZSXZ",
    "è¿äºæ¸¯è±æå±±": "ZSLG",
    "è±æå±±": "ZSLG",
    "æ¸©å·é¾æ¹¾": "ZSWZ",
    "é¾æ¹¾": "ZSWZ",
    "ä¹ä¹": "ZSYW",
    "å°å·è·¯æ¡¥": "ZSLQ",
    "è·¯æ¡¥": "ZSLQ",
    "èå±±æ®éå±±": "ZSZS",
    "æ®éå±±": "ZSZS",
    "çå°è¬è±": "ZSYT",
    "è¬è±": "ZSYT",
    "å¨æµ·å¤§æ°´æ³": "ZSWH",
    "å¤§æ°´æ³": "ZSWH",
    "ä¸´æ²å¯é³": "ZSLY",
    "å¯é³": "ZSLY",
    "æ½å": "ZSWF",
    "æµå®æ²é": "ZSJG",
    "æ²é": "ZSJG",
    "æ¥ç§å±±å­æ²³": "ZSRZ",
    "å±±å­æ²³": "ZSRZ",
    "æ´é³åé": "ZHLY",
    "åé": "ZHLY",
    "åé³å§è¥": "ZHNY",
    "å§è¥": "ZHNY",
    "å®æä¸å³¡": "ZHYC",
    "ä¸å³¡": "ZHYC",
    "è¥é³åé": "ZHXF",
    "åé": "ZHXF",
    "å¼ å®¶çè·è±": "ZGDY",
    "è·è±": "ZGDY",
    "å¸¸å¾·æ¡è±æº": "ZGCD",
    "æ¡è±æº": "ZGCD",
    "è¡¡é³åå²³": "ZGHY",
    "åå²³": "ZGHY",
    "ååé«åª": "ZUNC",
    "é«åª": "ZUNC",
    "ç»µé³åé": "ZUMY",
    "åé": "ZUMY",
    "æ³¸å·äºé¾": "ZULZ",
    "äºé¾": "ZULZ",
    "å®å®¾äºç²®æ¶²": "ZUYB",
    "äºç²®æ¶²": "ZUYB",
    "è¥¿æéå±±": "ZUXC",
    "éå±±": "ZUXC",
    "ä¹å¯¨é»é¾": "ZUJZ",
    "é»é¾": "ZUJZ",
    "æè¨è´¡å": "ZULS",
    "è´¡å": "ZULS",
    "ä¸½æ±ä¸ä¹": "ZPLJ",
    "ä¸ä¹": "ZPLJ",
    "å¤§çå¤ä»ª": "ZPDL",
    "å¤ä»ª": "ZPDL",
    "è¥¿åççº³åæ´": "ZPJH",
    "åæ´": "ZPJH",
    "è¾å²é©¼å³°": "ZUTC",
    "é©¼å³°": "ZUTC",
    "è¿ªåºé¦æ ¼éæ": "ZPDQ",
    "é¦æ ¼éæ": "ZPDQ",
    "é¶å·æ²³ä¸": "ZLIC",
    "æ²³ä¸": "ZLIC",
    "è¥¿å®æ¹å®¶å ¡": "ZLXN",
    "æ¹å®¶å ¡": "ZLXN",
    "æ ¼å°æ¨": "ZLGM",
    "æ¦çè«é«": "ZLDH",
    "è«é«": "ZLDH",
    "åå³ªå³": "ZLJQ",
    "åºé³è¥¿å³°": "ZLQY",
    "è¥¿å³°": "ZLQY",
    "æ¦ææ¦é³": "ZLYL",
    "æ¦é³": "ZLYL",
    "å»¶å®åæ³¥æ¹¾": "ZLYA",
    "åæ³¥æ¹¾": "ZLYA",
    "åå¤´ä¸æ²³": "ZBOW",
    "ä¸æ²³": "ZBOW",
    "éå°å¤æ¯ä¼ééæ´": "ZBDS",
    "ä¼ééæ´": "ZBDS",
    "èµ¤å³°çé¾": "ZBCF",
    "çé¾": "ZBCF",
    "éè¾½": "ZBTL",
    "æµ·æå°ä¸å±±": "ZBLA",
    "ä¸å±±": "ZBLA",
    "æ»¡æ´²éè¥¿é": "ZBMZ",
    "è¥¿é": "ZBMZ",
    "é¡ææµ©ç¹": "ZBXH",
    "å¤§åäºå": "ZBDT",
    "äºå": "ZBDT",
    "è¿åå¼ å­": "ZBYC",
    "å¼ å­": "ZBYC",
    "é¿æ²»çæ": "ZBCZ",
    "çæ": "ZBCZ",
    "å¤§åºè¨å°å¾": "ZYDQ",
    "è¨å°å¾": "ZYDQ",
    "ç¡ä¸¹æ±æµ·æµª": "ZYMD",
    "æµ·æµª": "ZYMD",
    "ä½³æ¨æ¯ä¸é": "ZYJM",
    "ä¸¹ä¸æµªå¤´": "ZYDD",
    "æµªå¤´": "ZYDD",
    "å»¶åæé³å·": "ZYYJ",
    "æé³å·": "ZYYJ",
    "æ­å¹æ°åå²": "RJCC",
    "æ°åå²": "RJCC",
    "ä¸äº¬æç°": "RJAA",
    "æç°": "RJAA",
    "ä¸äº¬ç¾½ç°": "RJTT",
    "ç¾½ç°": "RJTT",
    "å¤§éªå³è¥¿": "RJBB",
    "å³è¥¿": "RJBB",
    "åå¤å±ä¸­é¨": "RJGG",
    "ä¸­é¨": "RJGG",
    "ç¦å": "RJFF",
    "å²ç»³é£é¸": "ROAH",
    "é£é¸": "ROAH",
    "é¦å°ä»å·": "RKSI",
    "ä»å·": "RKSI",
    "é¦å°éæµ¦": "RKSS",
    "éæµ¦": "RKSS",
    "æµå·": "RKPC",
    "éå±±éæµ·": "RKPK",
    "éæµ·": "RKPK",
    "æ¼è°·ç´ æºé£æ®": "VTBS",
    "æ¼è°·ç´ ä¸é£æ®": "VTBS",
    "ç´ ä¸é£æ®": "VTBS",
    "ç´ æºé£æ®": "VTBS",
    "æ¼è°·å»æ¼": "VTBD",
    "å»æ¼": "VTBD",
    "æ®å": "VTSP",
    "æ¸è¿": "VTCC",
    "æ°å å¡æ¨å®": "WSSS",
    "æ¨å®": "WSSS",
    "åéå¡": "WMKK",
    "æ§å": "WMKP",
    "éå è¾¾èå è¯ºåè¾¾": "WIII",
    "èå è¯ºåè¾¾": "WIII",
    "å·´åå²ç»å·´è¨": "WADD",
    "ç»å·´è¨": "WADD",
    "é©¬å°¼æ": "RPLL",
    "å®¿å¡": "RPVM",
    "è¡å¿æ": "VVTS",
    "æ²³ååæ": "VVNB",
    "åæ": "VVNB",
    "å²æ¸¯": "VVDN",
    "éè¾¹": "VDPP",
    "é¦æ¸¯": "VHHH",
    "é¦æ¸¯èµ¤é±²è§": "VHHH",
    "èµ¤é±²è§": "VHHH",
    "æ¾³é¨": "VMMC",
    "å°åæ¡å­": "RCTP",
    "æ¡å­": "RCTP",
    "å°åæ¾å±±": "RCSS",
    "æ¾å±±": "RCSS",
    "é«é": "RCKH",
}


AIRPORT_CN_TO_ICAO = {}
AIRPORT_ICAO_TO_CN = {}
AIRPORT_NAMES = []


KNOWN_PEOPLE = ["æ®µæ´ç¡"]


COMMON_SURNAMES = set(
    "èµµé±å­æå¨å´éçå¯éè¤å«èæ²é©æ¨æ±ç§¦å°¤è®¸ä½åæ½å¼ å­æ¹ä¸¥å"
    "éé­é¶å§æè°¢é¹å»ææ°´çª¦ç« äºèæ½èå¥èå½­éé²é¦æé©¬èå¤è±æ¹"
    "ä¿ä»»è¢æ³é²å²åè´¹å»å²èé·è´ºåªæ±¤æ»æ®·ç½æ¯éé¬å®å¸¸ä¹äºæ¶åç®"
    "åé½åº·ä¼ä½ååé¡¾å­å¹³é»åç©è§å°¹å§éµæ¹æ±ªç¥æ¯ç¦¹çç±³è´æè§è®¡"
    "ä¼ææ´è°å®åºççºªèå±é¡¹ç¥è£æ¢æé®èéµå¸­å­£éº»å¼ºè´¾è·¯å¨å±æ±ç«¥é¢"
    "é­æ¢çæåéå¾é±éªé«å¤è¡ç°è¡åéèä¸æ¯æ¯æç®¡å¢è«ç»æ¿è£ç¼ªå¹²"
    "è§£åºå®ä¸å®£ééåæ­æ´ªåè¯¸å·¦ç³å´åé¾ç¨é¢è£´éè£ç¿èç¾æ¼æ çæ²"
    "å®¶å°è®ç¾¿å¨é³æ±²é´ç³æ¾äºæ®µå¯å·«ä¹ç¦å·´å¼ç§éå±±è°·è½¦ä¾¯å®è¬å¨éç­"
    "ä»°ç§ä»²ä¼å®«å®ä»æ ¾æ´çé­åæç¥æ­¦ç¬¦åæ¯è©¹æé¾å¶å¹¸å¸é¶éé»èè"
    "å°å®¿ç½æè²é°ä»éç´¢å¸ç±èµåèºå± èæ± ä¹é´è¥è½èåé»èåç¿è°­"
    "è´¡å³éå§¬ç³æ¶å µåå®°é¦éç©æ¡æ¡æ¿®çå¯¿éè¾¹æçåéæµ¦å°åæ¸©å«"
    "åºææ´ç¿éåæè¿è¹ä¹ å®¦è¾é±¼å®¹åå¤æææå»åº¾ç»æ¨å±è¡¡æ­¥é½è¿æ»¡"
    "å¼å¡å½æå¯å¹¿ç¦éä¸æ²å©èè¶éå¸å·©åèæå¾æèå·è¨¾è¾é"
    "é£ç®é¥¶ç©ºæ¾æ¯æ²ä¹å»é é¡»ä¸°å·¢å³è¯ç¸æ¥åèçº¢æ¸¸ç«ºæé¯ççæ¡å¬"
)

COMPOUND_SURNAMES = [
    "æ¬§é³", "å¸é©¬", "ä¸å®", "è¯¸è", "ä¸æ¹", "çç«", "å°è¿", "å¬ç¾",
    "èµ«è¿", "æ¾¹å°", "å¬å¶", "å®æ¿", "æ¿®é³", "æ·³äº", "åäº", "å¤ªå",
    "ç³å± ", "å¬å­", "ä»²å­", "è½©è¾", "ä»¤ç", "éç¦»", "å®æ", "é¿å­",
    "æå®¹", "é²äº", "é¾ä¸", "å¸å¾", "å¸ç©º", "äºå®", "å¸å¯", "ä»ç£",
    "å­è½¦", "é¢å­", "ç«¯æ¨", "å·«é©¬", "å¬è¥¿", "æ¼é", "ä¹æ­£", "å£¤é©·",
    "å¬è¯", "æè·", "å¤¹è°·", "å®°ç¶", "è°·æ¢", "æ®µå¹²", "ç¾é", "ä¸é­",
    "åé¨", "å¼å»¶", "ç¾è", "å¾®ç", "æ¢ä¸", "å·¦ä¸", "ä¸é¨", "è¥¿é¨",
    "åå®«",
]


FLIGHT_NO_RE = re.compile(r"9C\d{3,4}[A-Z]?")
REG_MODEL_RE = re.compile(r"^B[0-9A-Z]{4,5}A(?:319|320|321)$")
REG_AND_MODEL_RE = re.compile(r"\b(B[0-9A-Z]{4,5})(A319|A320|A321)\b")
REG_ONLY_RE = re.compile(r"\bB[0-9A-Z]{4,5}\b")
MODEL_ONLY_RE = re.compile(r"\bA(?:319|320|321)\b")
TIME_RANGE_RE = re.compile(r"(\d{2}:\d{2})\s*[-~ï½ââ]+\s*(\d{2}:\d{2})")
PAGE_YEAR_MONTH_RE = re.compile(r"(\d{4})å¹´(\d{1,2})æ")
PURE_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
ICAO_RE = re.compile(r"\b[A-Z]{4}\b")
DAY_HEADER_RE = re.compile(r"^\d{2}æ\d{2}æ¥\s*å¨.")
DAY_SUMMARY_LINE_RE = re.compile(r"^(\d{2}æ\d{2}æ¥\s*å¨.)(.*)$")
LATIN_PERSON_RE = re.compile(r"[A-Z][A-Z\s\.\-']{1,80}\([^)]*\)")
ZH_TAGGED_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}\([^)]*\)")
ZH_NAME_WITH_ROLE_RE = re.compile(r"[\u4e00-\u9fff]{2,4}(?:\([A-Z]\))?")
SHORT_ROLE_RE = re.compile(r"\([A-Z]\)")


ROLE_WORDS = {"æºé¿", "å¯é©¾é©¶", "ä¹å¡é¿", "éæºäººå", "å æºç»äººå", "è§å¯å"}

TRAINING_KEYWORDS = [
    "çè®ºè¯¾", "æ¨¡ææº", "è®­ç»", "å¤è®­", "æ£æ¥", "çç»", "å®ä¿",
    "åºæ¥", "çå­", "èè¯", "æçº§", "è¯¾ç¨", "å°é¢è¯¾", "åå",
    "CRM", "EBT",
]

POSITIONING_KEYWORDS = ["ç½®ä½"]
FERRY_KEYWORDS = ["ææ¸¡"]
STOP_KEYWORDS = ["åé£", "Grounding", "grounding"]
ATTENDANCE_KEYWORDS = ["èå¤"]
STANDBY_KEYWORDS = ["å¤ä»½", "å¾å½"]

DETAIL_SIGNAL_KEYWORDS = [
    "çè®ºè¯¾",
    "æ¨¡ææº",
    "æå®¤",
    "æ¥ç§é£å¹",
    "äººååå",
    "æºé¿",
    "å¯é©¾é©¶",
    "ä¹å¡é¿",
    "éæºäººå",
    "å æºç»äººå",
    "èªç­å¨æ",
    "ç­¾å°",
    "å°ç¹",
    "åæ¯",
]

TRANSPORT_HINT_WORDS = ["æ­ä¹", "ä¹å", "ç«è½¦", "é«é", "å¨è½¦", "å»", "åå¾", "è³", "è¿å"]

BAD_TITLE_WORDS = {
    "ä¸ªèµ·è½",
    "90å¤©3ä¸ªèµ·è½",
    "90å¤©ä¸ä¸ªèµ·è½",
    "ä¸ä¸ªèµ·è½",
    "3ä¸ªèµ·è½",
}

GENERIC_TASK_WORDS = [
    "è®­ç»", "èå¤", "ææ¸¡", "ç½®ä½", "èªç­", "å¤ä»½", "å¾å½", "åé£", "ä¸ªèµ·è½",
]

TASK_TITLE_WORDS = {
    "çè®ºè¯¾", "æ¨¡ææº", "åºæ¥", "çå­", "å¤è®­", "è®­ç»", "èå¤",
    "æ£æ¥", "å®æ", "çç»", "ç»å", "æçº§", "èè¯", "å®ä¿",
    "ç¨åº", "åé£", "å¼ä¼", "è±è¯­", "å¯é©¾é©¶", "æºé¿", "ä¹å¡é¿",
    "éæºäººå", "å æºç»äººå", "è§å¯å", "æ£", "è", "åå",
    "ç­¾å°", "å³å¨è", "ç«å¤", "ä¸ªèµ·è½", "Grounding",
}


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).replace("\u00a0", " ").replace("\r", "")
    text = text.replace("ï¼", "(").replace("ï¼", ")")
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
        logger.warning(f"é¡µé¢ææ¬è¯»åå¤±è´¥: {type(e).__name__}: {str(e)[:200]}")
        return ""


def random_like_wait(page, base_ms: int, jitter_ms: int = 400):
    page.wait_for_timeout(base_ms + (hash(datetime.now().isoformat()) % max(1, jitter_ms)))


def is_bad_title_text(text: str) -> bool:
    text = normalize_text(text)
    if not text:
        return False
    if text in BAD_TITLE_WORDS:
        return True
    if re.fullmatch(r"(90å¤©)?[ä¸3]ä¸ªèµ·è½", text):
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
        logger.error(f"ä¿å­æºåºå«åå¤±è´¥: {e}")


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
                    for alias in re.split(r"[|,ï¼ã/]+", aliases_raw):
                        alias = normalize_text(alias)
                        if alias:
                            names.append(alias)

                for name in names:
                    if name and not re.fullmatch(r"[A-Z]{4}", name):
                        data[name] = icao

        logger.info(f"è¯»å airports.csvï¼{len(data)} ä¸ªæºåºå«å")
    except Exception as e:
        logger.warning(f"è¯»å airports.csv å¤±è´¥ï¼è·³è¿ï¼{e}")

    return data


def put_airport_mapping(mapping: dict, name: str, icao: str, source: str):
    name = normalize_text(name)
    icao = normalize_text(icao).upper()

    if not name or not re.fullmatch(r"[A-Z]{4}", icao):
        return

    if name in mapping and mapping[name] != icao:
        logger.warning(
            f"æºåºå«åå²çªï¼{name} å·²æ¯ {mapping[name]}ï¼{source} æ³è®¾ä¸º {icao}ï¼ä¿çåå¼"
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
        logger.warning(f"ä¸åå¥æºåºå«åå²çªï¼{alias} å½å={current} æ°={icao}")
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

    raise RuntimeError("æªæ¾å°éªè¯ç å¾ç")


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
        logger.warning(f"ddddocr è¯å«å¤±è´¥ï¼åé pytesseract: {e}")
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
        raise RuntimeError("ç»å½é¡µè¾å¥æ¡æ°éå¼å¸¸")

    inputs.nth(0).fill(USERNAME)
    inputs.nth(1).fill(PASSWORD)
    inputs.nth(2).fill(code)


def login(page, max_retries: int = 10):
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"ç»å½å°è¯ {attempt}/{max_retries}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            random_like_wait(page, 4500, 1200)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, f"login_page_{attempt}.png"), full_page=True)
            save_text(f"login_page_{attempt}.txt", page_text(page))
        except Exception as e:
            logger.error(f"ç»å½é¡µå è½½å¤±è´¥: {e}")
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

                if ("ç»ä¸è®¤è¯ä¸­å¿" not in body_text) and ("Login" not in body_text):
                    logger.info(f"ç»å½æåï¼éªè¯ç ï¼{cand}")
                    return

                try:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                    random_like_wait(page, 2200, 700)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"éªè¯ç  {cand} å°è¯å¤±è´¥: {e}")

    raise RuntimeError("å¤æ¬¡å°è¯åä»æ æ³ç»å½")


def open_mission_page(page):
    for i in range(3):
        try:
            logger.info(f"æå¼ä»»å¡é¡µé¢ï¼å°è¯ {i + 1}/3")
            page.goto(MISSION_URL, wait_until="domcontentloaded", timeout=90000)
            random_like_wait(page, 4500, 1200)

            try:
                page.locator("text=æçä»»å¡").first.click(timeout=5000)
                random_like_wait(page, 2600, 900)
            except Exception:
                pass

            body_text = page_text(page)

            if re.search(r"\d{2}æ\d{2}æ¥\s*å¨.", body_text):
                logger.info("ä»»å¡é¡µé¢å·²å è½½")
                return

        except Exception as e:
            logger.error(f"æå¼ä»»å¡é¡µé¢å¤±è´¥: {e}")
            if i == 2:
                raise

    raise RuntimeError("æªè½è¿å¥ä»»å¡åè¡¨é¡µ")


def get_day_headers(page) -> list:
    text = page_text(page)
    headers = []

    for line in text.splitlines():
        line = normalize_text(line)
        m = re.match(r"^(\d{2}æ\d{2}æ¥\s*å¨.)", line)
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
        if "æ¥çæ´å¤" in line:
            labels.append(line)

    return labels


def click_load_more(page) -> bool:
    try:
        loc = page.locator("text=æ¥çæ´å¤")
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
        logger.info(f"ç¹å»æ¥çæ´å¤å¤±è´¥: {e}")
        return False


def load_all_visible_tasks(page, max_rounds: int = LOAD_MORE_MAX_ROUNDS):
    prev_signature = None

    for round_no in range(1, max_rounds + 1):
        headers_before = get_day_headers(page)
        more_before = get_load_more_labels(page)

        save_text(f"load_round_{round_no}_headers_before.txt", "\n".join(headers_before))
        save_text(f"load_round_{round_no}_more_before.txt", "\n".join(more_before))

        logger.info(
            f"ç¬¬ {round_no} è½®å è½½åï¼æ¥æå¤´ {len(headers_before)} ä¸ªï¼æ¥çæ´å¤ {len(more_before)} ä¸ª"
        )

        signature_before = (
            len(headers_before),
            tuple(headers_before[-10:]),
            len(more_before),
            tuple(more_before[-5:]),
        )

        if not more_before:
            logger.info("æ²¡ææ¥çæ´å¤äº")
            return

        if not click_load_more(page):
            logger.info("æ¥çæ´å¤æ æ³ç»§ç»­ç¹å»")
            return

        headers_after = get_day_headers(page)
        more_after = get_load_more_labels(page)

        save_text(f"load_round_{round_no}_headers_after.txt", "\n".join(headers_after))
        save_text(f"load_round_{round_no}_more_after.txt", "\n".join(more_after))

        logger.info(
            f"ç¬¬ {round_no} è½®å è½½åï¼æ¥æå¤´ {len(headers_after)} ä¸ªï¼æ¥çæ´å¤ {len(more_after)} ä¸ª"
        )

        signature_after = (
            len(headers_after),
            tuple(headers_after[-10:]),
            len(more_after),
            tuple(more_after[-5:]),
        )

        if signature_after == signature_before or signature_after == prev_signature:
            logger.info("ç¹äºæ¥çæ´å¤ä½é¡µé¢ç­¾åæ²¡ç»§ç»­ååï¼åæ­¢æ©å±")
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
        logger.warning(f"{header} JS ç¹å»ç­ç¥ {strategy} å¤±è´¥ï¼{e}")

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
        logger.warning(f"{header} åæ ç¹å»ç­ç¥ {strategy} å¤±è´¥ï¼{e}")
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

        if "æ¥çæ´å¤" in line_stripped and re.search(r"\d{4}-\d{2}-\d{2}", line_stripped):
            break

        if DAY_HEADER_RE.match(line_stripped) and line_stripped != header:
            break

        result_lines.append(line)

    return "\n".join(result_lines).strip()


def get_day_block_by_dom(page, header: str, next_header=None) -> str:
    """
    ä¸¥æ ¼ç DOM è¯»åï¼
    åªè¯»åâå½åæ¥æè¡æå¨ä»»å¡åè¡¨åºåâä¸é¢ãä¸ä¸ä¸ªæ¥æå¤´ä¹åçå¯è§è¯¦æã
    ä¸åå¨é¡µé¢æ Y åæ å¤§èå´æ«ï¼é¿åæ Grounding / å¶å®æ¥æä¸²è¿å½åæ¥æã
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
                    const m = String(s || "").match(/\\d{2}æ\\d{2}æ¥\\s*å¨./g);
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

                    // æé¤å¨é¡µé¢å¤§å®¹å¨ï¼åå«å¤ªå¤æ¥æå¤´çä¸å¾ä¸è¦
                    if (countDateHeaders(text) >= 3) continue;

                    let score = 0;

                    if (text === header) score += 30;
                    if (text.startsWith(header)) score += 50;
                    if (/\\d{2}:\\d{2}\\s*[-~ï½ââ]+\\s*\\d{2}:\\d{2}/.test(text)) score += 30;
                    if (/(è®­ç»|èªç­|ç½®ä½|ææ¸¡|å¤ä»½|å¾å½|èå¤|åé£|Grounding)/.test(text)) score += 30;

                    // å³ä¾§ä»»å¡åè¡¨éå¸¸è¾å®½ï¼å·¦ä¾§æ¥åå°æ ¼å­è¾çª
                    if (r.width >= 300) score += 20;
                    if (r.left >= 250) score += 20;

                    // è¿å¤§çå®¹å¨æ£å
                    if (r.height > 180) score -= 40;
                    if (text.length > 300) score -= 40;

                    headerCandidates.push({el, text, score, rect: rectInfo(el)});
                }

                if (!headerCandidates.length) {
                    return {ok: false, reason: "header_not_found", text: "", debug: {}};
                }

                headerCandidates.sort((a, b) => b.score - a.score);
                const headerEl = headerCandidates[0].el;

                // åä¸æ¾âæ¥æä»»å¡è¡âå®¹å¨ï¼ä½ä¸è½æ¾å°æ´é¡µå¤§å®¹å¨
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

                // åªåè®¸è¯»åå½åä»»å¡åè¡¨æ¨ªååºåï¼é¿åè¯»å°å·¦ä¾§æ¥åæå¶å®é¢æ¿
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

                        // å¿é¡»åå½åä»»å¡åè¡¨æ¨ªååºåæäº¤é
                        const overlap = Math.min(r.right, regionRight) - Math.max(r.left, regionLeft);
                        if (overlap <= 20) continue;

                        let score = 0;
                        if (text.startsWith(nextHeader)) score += 50;
                        if (/\\d{2}:\\d{2}\\s*[-~ï½ââ]+\\s*\\d{2}:\\d{2}/.test(text)) score += 20;
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

                    // åªè¯»æ¥æè¡ä¸æ¹å°ä¸ä¸ä¸ªæ¥æå¤´ä¹å
                    if (r.bottom < rowBottom - 3) continue;
                    if (r.top > nextTop - 5) continue;

                    // å¿é¡»å¨åä¸ä¸ªä»»å¡åè¡¨æ¨ªååºå
                    const overlap = Math.min(r.right, regionRight) - Math.max(r.left, regionLeft);
                    if (overlap <= 20) continue;

                    const text = norm(el.innerText || el.textContent || "");
                    if (!text) continue;
                    if (text.length > 800) continue;
                    if (countDateHeaders(text) >= 2) continue;

                    // åªåæ´åå¶å­èç¹çææ¬ï¼é¿åç¶å®¹å¨éå¤åå¤§æ®µ
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
        logger.warning(f"{header} DOM ä¸¥æ ¼åºåè¯»åå¤±è´¥ï¼{e}")

    return ""


def block_looks_polluted(day_block: str, header: str, fallback_text: str = "") -> bool:
    """
    é²ä¸²å¡æ±¡æï¼
    å¦æå½åæ¥ææè¦æ¯è®­ç»/èªç­/ç½®ä½/ææ¸¡ï¼
    ä½ DOM è¯¦æéè¯»åºäº Grounding/åé£ï¼å¤å®ä¸ºæ±¡æåï¼ä¸åå¥ã
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

    date_header_count = len(re.findall(r"\d{2}æ\d{2}æ¥\s*å¨.", joined))
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

    # åä¸åéæ¢æè®­ç»ç»èåæ Groundingï¼éå¸¸æ¯ä¸²è¯»
    if block_has_grounding and block_has_training:
        return True

    # ä¸ä¸ªæ¥æåéåºç°è¿å¤ä¸åä»»å¡å³é®è¯ï¼å®¹ææ¯è¯»ä¸²
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

        if "èªç­å¨æ" in dom_block:
            dom_score += 500

        if "èªç­å¨æ" in body_block:
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
    return any(x in text for x in ["(+1)", "ï¼+1ï¼", "ï¼1", "+1", "æ¬¡æ¥", "ç¬¬äºå¤©", "ç¿æ¥"])


def strip_time_from_title(title: str) -> str:
    title = TIME_RANGE_RE.sub("", title).strip()
    title = re.sub(r"[\s~ï½\-ââ]+$", "", title).strip()
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
        + ["èªç­"]
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

        if "æ¥çæ´å¤" in tail:
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

        if "æ¥çæ´å¤" in line:
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

    if "èªç­å¨æ" in joined:
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
            logger.warning(f"ç­å¾ {header} è¯¦ææ¶è¯»åå¤±è´¥: {e}")

        random_like_wait(page, 800, 400)

    return last_block, last_cards, has_real_detail


def expand_day_get_real_detail(page, header: str, next_header=None, fallback_text: str = "", retries: int = 5):
    best_block = ""
    best_cards = []
    expanded_final = False

    for attempt in range(1, retries + 1):
        strategy = (attempt - 1) % 5
        logger.info(f"å±å¼ {header} å°è¯ {attempt}/{retries}ï¼ç¹å»ç­ç¥ {strategy}")

        expanded = expand_day(page, header, strategy=strategy)

        if not expanded:
            logger.warning(f"{header} ç¹å»å±å¼å¤±è´¥ï¼strategy={strategy}")
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
            logger.info(f"{header} å·²æå°çå®è¯¦æ")
            return True, best_block, best_cards, True

        logger.warning(f"{header} æ¬æ¬¡åªæå°æè¦æç©ºåå®¹ï¼åå¤æ¢ç­ç¥éè¯")

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
        "èªç­å¨æ" in text
        or bool(REG_AND_MODEL_RE.search(text))
        or len(ICAO_RE.findall(text)) >= 2
    )

    if flight_no and has_flight_structure:
        return "flight"

    return "generic"


def task_type_from_kind(kind: str) -> str:
    return {
        "positioning": "ç½®ä½",
        "ferry": "ææ¸¡",
        "training": "è®­ç»",
        "flight": "èªç­",
        "stop": "åé£",
        "attendance": "èå¤",
        "standby": "å¾å½",
        "generic": "å¶ä»",
    }.get(kind, "å¶ä»")


def task_bucket(task_type: str) -> str:
    return {
        "èªç­": "flight",
        "ç½®ä½": "positioning",
        "è®­ç»": "training",
        "ææ¸¡": "ferry",
        "åé£": "other",
        "èå¤": "other",
        "å¾å½": "other",
        "å¤ä»½": "other",
        "å¶ä»": "other",
    }.get(task_type, "other")


def extract_date(text: str, page_year: int):
    m = re.search(r"(\d{2})æ(\d{2})æ¥", text)

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
        if "æ¥çæ´å¤" in line:
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

    if TIME_RANGE_RE.search(line) and ("Grounding" in line or "grounding" in line or "åé£" in line):
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
        if "èªç­å¨æ" in line or MODEL_ONLY_RE.fullmatch(line):
            continue

        for sep in ["â", "ââ", "-", "â"]:
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
    m = re.search(r"(\d{2}:\d{2})\s*([^\s]{2,30})\s*èªç­å¨æ", card_text)

    if m:
        return m.group(1), m.group(2)

    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]

    for line in lines:
        if "èªç­å¨æ" not in line:
            continue

        m_old = re.search(r"(\d{2}:\d{2})\s+([^\s]{2,30})", line)

        if not m_old:
            continue

        hhmm = m_old.group(1)
        place = m_old.group(2)

        if f"{hhmm}-" in line or f"{hhmm}~" in line or f"{hhmm}ï½" in line:
            continue

        if place in ["A319", "A320", "A321", "èªç­å¨æ"]:
            continue

        if FLIGHT_NO_RE.fullmatch(place):
            continue

        return hhmm, place

    return "", ""


def extract_start_end_time(card_text: str):
    lines = [normalize_text(x) for x in card_text.splitlines() if normalize_text(x)]
    candidate_lines = []

    for line in lines:
        if "èªç­å¨æ" in line:
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

    text = text.replace("ï¼", "(").replace("ï¼", ")")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\([A-Z]\))", r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


def has_clear_delimiters(text: str) -> bool:
    text = standardize_people_text(text)

    if not text:
        return False

    return any(sep in text for sep in [" ", "ã", "ã", "ï¼", ",", "/", "\n", "\t"])


def split_by_clear_delimiters(text: str) -> list:
    text = standardize_people_text(text)

    if not text:
        return []

    parts = re.split(r"[\sããï¼,/]+", text)
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

    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", token):
        return True

    return False


def is_non_person_name_noise(token: str) -> bool:
    token = normalize_text(token)

    if not token:
        return True

    # é R çåå­æ¯æ è®°åå»æï¼ä¾å¦ è¡¡ä½³è¿(B) -> è¡¡ä½³è¿
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

    if "èªç­å¨æ" in plain:
        return True

    if plain in AIRPORT_CN_TO_ICAO:
        return True

    if plain in AIRPORT_ICAO_TO_CN:
        return True

    # è¿æ»¤æºåºä¸­æåæ¼å¨ä¸èµ·çèªçº¿ä¸²ï¼ä¾å¦ ä¸æµ·æµ¦ä¸åå¤å±ä¸­é¨ / åå¤å±ä¸­é¨ä¸æµ·æµ¦ä¸
    if re.fullmatch(r"[\u4e00-\u9fff]{4,20}", plain):
        matched_names = []
        temp = plain

        for airport_name in AIRPORT_NAMES:
            if airport_name and airport_name in temp:
                matched_names.append(airport_name)
                temp = temp.replace(airport_name, "", 1)

        if len(matched_names) >= 2 and not temp:
            return True

    return False


def normalize_person_display_token(token: str) -> str:
    token = normalize_text(token)
    # ä¿ç (R)ï¼å»æå¶å®åå­æ¯æ è®°ï¼é¿å è¡¡ä½³è¿(B) è¿ç§æ¾ç¤ºè¿äººåååã
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

    # æè¦è¡ä¸è¬æ¯ï¼èªç­ 11:00- 17:10 / è®­ç» 09:00-17:30
    if not line_has_summary_task_signal(line):
        return False

    # åªè¦æçå®èªç­å·ãæ³¨åå·ãæºåãèªç­å¨æï¼å°±ä¸æ¯æè¦ååºã
    if FLIGHT_NO_RE.search(line):
        return False

    if REG_ONLY_RE.search(line) or REG_AND_MODEL_RE.search(line) or MODEL_ONLY_RE.search(line):
        return False

    if "èªç­å¨æ" in line:
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

    # å¦æå·²ç»æ ç°é¸¿é£(R)ï¼å°±ä¸è¦åæ¾ç¤ºæ è§è²ç ç°é¸¿é£ã
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

    if is_day_header(line) or "æ¥çæ´å¤" in line:
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


def parse_people_line_flight(line: str) -> list:
    line = standardize_people_text(line)

    if not line:
        return []

    if is_bad_title_text(line):
        return []

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

    surname_split = split_chinese_flight_people_by_surname(line)
    return normalize_people_output(surname_split)


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

        if "èªç­å¨æ" in line or "æ¥çæ´å¤" in line or TIME_RANGE_RE.search(line):
            continue

        if re.fullmatch(r"\d{2}:\d{2}", line) or len(line) == 1:
            continue

        if is_non_person_name_noise(line):
            continue

        # ä¼åæåå¸¦è§è²æ è®°çäººåï¼ä¾å¦ ç°é¸¿é£(R)å¼ ææµ©(R)æ®µæ´ç¡
        tagged = ZH_TAGGED_NAME_RE.findall(line)
        if tagged:
            for t in tagged:
                t = normalize_person_display_token(t)
                if t and not is_non_person_name_noise(t):
                    people.append(t)

            rest = ZH_TAGGED_NAME_RE.sub("", line)
            rest = normalize_text(rest)
            if rest and not is_non_person_name_noise(rest):
                result = parse_people_line_flight(rest)
                if result:
                    people.extend(result)
            continue

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
            temp = temp.replace(name, "ã" * len(name), 1)

    found_airports.sort(key=lambda x: x[0])

    if len(found_airports) >= 2:
        return found_airports[0][1], found_airports[-1][1]

    for keyword in ["å»", "åå¾", "è³", "è¿å"]:
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

    if "å°ç¹" in line or "ä»»å¡" in line or "äºé¡¹" in line or "ç±»å" in line:
        return False

    if re.search(r"[ï¼:ãï¼ã]", line) and not has_clear_delimiters(line):
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

        if line in ROLE_WORDS or is_day_header(line) or "æ¥çæ´å¤" in line:
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

    if item.get("task_type") not in {"åé£", "èå¤", "å¶ä»"}:
        return False

    grounding_like = (
        "Grounding" in title_text
        or "grounding" in title_text
        or "Grounding" in raw_card_text
        or "grounding" in raw_card_text
        or "åé£" in title_text
    )

    people_bad = (not people) or all(is_bad_title_text(p) for p in people)
    no_useful_location = (not location) or is_bad_title_text(location)
    no_useful_extra = not [x for x in extra_lines if not is_bad_title_text(x)]
    weak_title = title_text in {"åé£Grounding", "Grounding", "grounding", "åé£"} or is_bad_title_text(title_text)

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
            title_text = f"{dep_cn}â{arr_cn}"
        elif dep and arr:
            title_text = f"{dep}â{arr}"
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

    if task_type in {"åé£", "èå¤"}:
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
        logger.info(f"æ¦æªæ§éè¯¯æ ·å¼æ°çæï¼{day_header} | {title_text}")
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
        "task_type": "èªç­",
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
        "èªç­": "âï¸",
        "ç½®ä½": "ð",
        "è®­ç»": "ð",
        "ææ¸¡": "ð",
        "å¤ä»½": "ð",
        "å¾å½": "ð",
        "èå¤": "ð",
        "åé£": "ð",
        "å¶ä»": "ð",
    }.get(task_type, "ð")


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
            return f"{icon} {flight_no} {dep_cn}â{arr_cn}{suffix}"
        if dep_cn and arr:
            return f"{icon} {flight_no} {dep_cn}â{arr}{suffix}"
        if dep and arr_cn:
            return f"{icon} {flight_no} {dep}â{arr_cn}{suffix}"
        if dep and arr:
            return f"{icon} {flight_no} {dep}-{arr}{suffix}"
        return f"{icon} {flight_no}"

    if item["task_type"] in {"ææ¸¡", "ç½®ä½"}:
        if dep_cn and arr_cn:
            return f"{icon} {dep_cn}â{arr_cn}{suffix}"
        if dep and arr:
            return f"{icon} {dep}â{arr}{suffix}"

    if item["task_type"] == "åé£":
        clean_title = re.sub(
            r"\s*00:00\s*[~ï½\-ââ]\s*(17:30|23:59)\s*$",
            "",
            title_text,
        ).strip()
        clean_title = clean_title.replace("Grounding", "").replace("grounding", "").strip()

        if clean_title and not is_bad_title_text(clean_title):
            return f"{icon} {clean_title}"

        return f"{icon} åé£"

    if title_text and not is_bad_title_text(title_text):
        return f"{icon} {title_text}"

    return f"{icon} {item['task_type']}"


def build_description(item: dict) -> str:
    lines = [item["day_header"], f"ç±»åï¼{item['task_type']}"]

    if item["flight_no"]:
        lines.append(f"èªç­ï¼{item['flight_no']}")
    elif item.get("title_text") and not is_bad_title_text(item.get("title_text", "")):
        lines.append(f"äºé¡¹ï¼{item['title_text']}")

    if item["dep_cn"] and item["arr_cn"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"èªçº¿ï¼{item['dep_cn']} â {item['arr_cn']}{cross}")
    elif item["dep"] and item["arr"]:
        cross = "(+1)" if item["end_dt"].date() > item["start_dt"].date() else ""
        lines.append(f"èªçº¿ï¼{item['dep']} â {item['arr']}{cross}")

    if item["location"] and not is_bad_title_text(item["location"]):
        lines.append(f"å°ç¹ï¼{item['location']}")

    if item["checkin_time"] and item["checkin_place"]:
        lines.append(f"ç­¾å°ï¼{item['checkin_time']}ï½{item['checkin_place']}")
    elif item["checkin_time"]:
        lines.append(f"ç­¾å°ï¼{item['checkin_time']}")

    lines.append(f"ä»»å¡ï¼{item['start_time']} - {item['end_time']}")

    if item["model"] and item["reg"]:
        lines.append(f"æºåï¼{item['model']}ï½æ³¨åå·ï¼{item['reg']}")
    elif item["model"]:
        lines.append(f"æºåï¼{item['model']}")
    elif item["reg"]:
        lines.append(f"æ³¨åå·ï¼{item['reg']}")

    clean_extra = [x for x in item["extra_lines"] if not is_bad_title_text(x)]
    if clean_extra:
        lines.append("")
        lines.append("è¯´æï¼")
        for x in clean_extra:
            lines.append(f"â¢ {x}")

    clean_people = normalize_people_output(item["people_lines"])
    if clean_people:
        lines.append("")
        lines.append("äººåååï¼")
        for p in clean_people:
            lines.append(f"â¢ {p}")

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
        desc = f"{desc}\n\nçæ¬ï¼{version_tag}"

    alarm_desc = f"{item['flight_no']} ç­¾å°æé" if item["flight_no"] else f"{item.get('title_text', 'ä»»å¡')} æé"
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
    text = re.sub(r"\s*00:00\s*[~ï½\-ââ]\s*(17:30|23:59)", "", text)
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

    if "èªç­ï¼" in block:
        score += 10
    if "å°ç¹ï¼" in block:
        score += 10
    if "èªçº¿ï¼" in block:
        score += 10
    if "ç­¾å°ï¼" in block:
        score += 10
    if "æºåï¼" in block:
        score += 10
    if "äººåååï¼" in block:
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
        logger.warning(f"è¯»åç°æäºä»¶å¤±è´¥: {e}")

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
        logger.info(f"{filename} åå®¹æªåå")
        return False

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_text)

    logger.info(f"åå¥ {filename}: {len(ordered)} ä¸ªäºä»¶")
    return True


def prepare_items(day_blocks, page_year: int) -> list:
    raw_items = []
    classification_log = []

    for day in day_blocks:
        day_header = day["day_header"]
        day_block = day["day_block"]
        cards = day["cards"]

        # å¦æåä¸å¤©å·²ç»å­å¨çå®è¯¦æå¡çï¼å°±è·³è¿âèªç­ 11:00-17:10âè¿ç±»æè¦ååºå¡ã
        # è¿æ ·å¯ä»¥é¿ååä¸å¤©åæ¶åºç°ï¼
        #   ð èªç­ 11:00-17:10
        #   âï¸ 9C8602 ä¸æµ·æµ¦ä¸âåå¤å±ä¸­é¨
        day_has_real_detail_card = False
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

            if day_has_real_detail_card and is_summary_only_card(card_text, day_header):
                classification_log.append(
                    f"{day_header} | card#{idx} | kind={kind} | title=SKIPPED_SUMMARY_DUPLICATE\n{card_text}\n---"
                )
                continue

            if kind == "flight":
                item = parse_flight_card(card_text, day_header, page_year, day_block)
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

                item["extra_lines"].append("æ¥æºï¼é¡µé¢æè¦è¡ï¼æªå±å¼å°è¯¦ç»ä»»å¡å¡ç")

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
        f"æ¬æ¬¡æå° {len(total_items)} ä¸ªä»»å¡ï¼ä¿çåå²ï¼åªæ¿æ¢æ¬æ¬¡æå°æ¥æï¼åç±»å¼ºçº¦æå·²å¯ç¨"
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
                logger.info(f"æ¥æ {header} ä½¿ç¨çå®è¯¦æå¡ç")
            else:
                logger.warning(f"æ¥æ {header} æªç¡®è®¤çå®è¯¦æï¼æ£æ¥æ¯å¦éè¦æè¦ååº")

            if not has_real_detail or not cards:
                if fallback_text:
                    logger.warning(f"æ¥æ {header} æç»ä½¿ç¨æè¦è¡ååºï¼{fallback_text}")

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
                    logger.warning(f"æ¥æ {header} æ²¡æçå®è¯¦æï¼ä¹æ²¡æå¯ç¨æè¦ååº")
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
            logger.error(f"å¤çæ¥æ {header} å¤±è´¥: {e}", exc_info=True)

            fallback_text = normalize_text(summary_task_map.get(header, ""))

            if fallback_text:
                logger.warning(f"æ¥æ {header} å¼å¸¸åä½¿ç¨æè¦è¡ååºï¼{fallback_text}")

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

    logger.info(f"æ¶éäº {len(result)} ä¸ªæ¥æçæ°æ®")
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
    logger.info("å¼å§æ§è¡èªç­æ¥åç¬è«")
    logger.info("=" * 60)

    if not USERNAME or not PASSWORD:
        raise RuntimeError("ç¼ºå°ç¯å¢åéï¼CREW_USERNAME / CREW_PASSWORD")

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
            logger.info(f"é¡µé¢å¹´ä»½: {page_year}")

            day_blocks = collect_day_blocks(page)

            if not day_blocks:
                raise RuntimeError("æªæå°ä»»ä½ä»»å¡åï¼åæ­¢åå¥ï¼ä¿æ¤ç°æ ICS")

            create_multi_calendars_from_blocks(day_blocks, page_year)

            logger.info("=" * 60)
            logger.info("æ§è¡å®æ")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"æ§è¡åºé: {e}", exc_info=True)
            raise

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
