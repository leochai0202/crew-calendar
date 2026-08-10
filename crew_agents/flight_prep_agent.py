from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crew_agents.common import (
    append_github_summary,
    atomic_write_json,
    atomic_write_text,
    load_json,
    now_beijing,
)
from crew_agents.ics_utils import (
    AmbiguousFlightSelectionError,
    CalendarEvent,
    FlightSelectionError,
    canonical_airport_name as normalize_ics_airport_name,
    extract_airport_mapping,
    foreign_crew_names,
    parse_ics,
    resolve_icao,
    select_continuous_flight_group,
    strip_crew_role_markers,
    update_airport_experience,
)
from crew_agents.weather import fetch_airport_weather

VERSION = "flight-prep-free-v15-final-group-format"
RISK_KEYWORDS = (
    "跑道", "滑行", "进近", "离场", "复飞", "盲降", "双截获", "高截获", "风切变",
    "乱流", "雷雨", "鸟击", "GPS", "地形", "气压", "灯光", "军航", "高度", "速度",
    "PAPI", "ILS", "下滑", "能量", "脱离", "机坪", "等待线", "强回波", "湿跑道",
    "高原", "标高", "下降率", "顺风", "侧风", "爬升梯度", "减速", "构型", "形态",
)
EXCLUDE_KEYWORDS = (
    "酒店", "住宿", "接送", "餐食", "电话", "地址", "联系人", "前台", "供应商",
    "车程", "车辆提供方", "业务联系", "接机地点", "送机地点",
)
MANUAL_HEADER_SUFFIX = "机场运行特点"
MANUAL_HEADER_MARKERS = (
    "机场运行特点",
    "威胁识别与缓解措施表",
    "威胁识别及缓解措施表",
    "威胁识别与缓解",
    "威胁识别及缓解",
)
MANUAL_GLOB_PATTERNS = (
    "airport_information*.txt",
    "*机场特点*.txt",
    "AirDropManual*.txt",
    "*.txt",
    "pdf/*.pdf",
)
MIN_PDF_MANUAL_TEXT_CHARS = 10_000
MAX_PDF_FAILED_PAGE_RATIO = 0.01
PDF_FOOTER_LINES = {
    "春秋航空股份有限公司飞行标准管理部飞行标准处",
}


# Curated wording is intentionally written from the operating crew's point of view.
# Source provenance is kept in code comments/metadata and is not printed into the group-ready text.
CURATED_TYPICAL_INCIDENTS: dict[str, list[str]] = {
    "新加坡樟宜": [
        "曾发生受外界因素影响导致飞越跑道入口高度偏高的事件。",
        "三跑道运行中曾出现临时更换跑道或进离场程序的情况。",
        "曾有ATC传递的FOLLOW GREEN灯光滑行指令异常反馈，存在滑行路线误判风险。",
        "午后热力对流容易形成雷雨，可能影响放行、滑行和离场间隔。",
    ],
    "上海浦东": [
        "曾发生低高度鸟击并造成雷达罩损伤事件。",
        "曾发生低高度失去目视参考后继续进近事件。",
        "曾发生进近阶段TA/RA事件。",
        "地面滑行路线复杂、热点较多，存在滑错路线和跑道侵入风险。",
    ],
    "西宁曹家堡": [
        "曾发生风切变警告事件。",
        "局方安全通告：多发刹车故障导致非正常位移。",
        "春、夏季乱流和风切变突出，容易造成不稳定进近或复飞。",
        "11号跑道下坡明显，进近和起飞阶段容易产生目视错觉及速度判断偏差。",
    ],
    "南昌昌北": [
        "夏季雷暴天气频发，易出现风切变。",
        "机场毗邻鄱阳湖，鸟类活动频繁，鸟击风险突出。",
        "机场周围空军机场较多，军民航活动频繁，易出现GPS干扰。",
        "进近阶段常用雷达引导，直飞可能导致剖面偏高，易引发不稳定进近。",
    ],
    "丽江三义": [
        "曾发生SINK RATE警告事件。",
        "曾发生风切变事件。",
        "曾发生重着陆事件。",
        "曾发生形态超过高度限制事件。",
    ],
}

PUDONG_2606_EFFECTIVE = date(2026, 6, 11)

CURATED_CORE_THREATS: dict[str, list[str]] = {
    "西宁曹家堡": [
        "西宁曹家堡为二类综合复杂高原机场，标高7166ft，高原高温条件下起飞性能余度和超轮速风险都要重点关注，起飞前认真核对性能、跑道、温度、风和修正项目。",
        "11号跑道起飞下坡明显，容易出现速度增长快和超轮速风险，PM要精准报出V1、VR，PF按正常带杆率操纵，不抢带也不延误抬轮。",
        "11号跑道进近下坡约-0.6%，容易产生目视错觉；西宁要求1300ft稳定进近，进近前明确稳定标准，若速度、构型、下降率或推力不稳定，及时复飞。",
        "春夏季乱流和风切变突出，尤其11号跑道盲降进近在FAF附近可能出现顺风转顶风造成乱流，进近前提前完成减速和形态，截获下滑道前保持形态2、速度160-170节。",
        "机场四周环山，跑道西南端有较高地形，进离场严格保持航迹，至少一侧ND打开地形显示，避免偏离航线和低高度大下降率。",
        "西宁多发刹车故障导致非正常位移，设置停留刹车前确认飞机完全停止，按程序设置并做好交叉检查。",
    ],
    "南昌昌北": [
        "南昌夏季雷暴天气频发，易出现风切变，进离场前必须看最新雷达图和天气趋势，绕飞提前申请，不贴近雷暴。",
        "机场毗邻鄱阳湖，鸟类活动频繁，进近和离场低高度阶段注意鸟击风险，起飞前明确鸟击后的返场和故障处置思路。",
        "机场周围空军机场较多，军民航活动频繁，易出现GPS干扰，进离场严格按程序飞行，发现导航异常及时交叉检查原始导航、航迹和ATC指令。",
        "进近常用雷达引导，直飞可能导致剖面偏高，特别是03号盲降从北侧进场时，提前申请下降和减速，不能等五边后段再集中放形态。",
        "西南侧有较高地形，西侧方向进港受地形影响大，进近时注意IAF点和CN104高度限制，至少一侧打开地形显示，防止下降早、下降率大。",
        "南昌当前通播复飞高度可能为1500米，复飞程序保持一边，进近准备时必须结合ATIS、航图和管制指令核对复飞高度，不确定就向ATC证实。",
    ],
}


@dataclass(frozen=True)
class BilingualFact:
    fact_id: str
    text_zh: str
    text_en: str
    airport: str = ""
    source_file: str = ""
    source: str = "CURATED"
    source_page: str = "N/A"
    source_heading: str = ""
    source_section: str = "通用运行要求"
    operational_phase: str = "general"
    airport_specific: bool = False
    category: str = "general"
    role_scope: tuple[str, ...] = ()
    importance: int = 50
    semantic_key: str = ""
    source_text_zh: str = ""
    operational_condition: tuple[str, ...] = ()
    applicability: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    mitigation: tuple[str, ...] = ()
    restriction: tuple[str, ...] = ()
    excluded_source_clauses: tuple[str, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()
    season_scope: tuple[int, ...] = ()
    flight_scope: tuple[str, ...] = ()
    route_scope: tuple[tuple[str, str], ...] = ()
    topic: str = ""
    source_fact_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    source_clauses: tuple[str, ...] = ()
    source_original_texts: tuple[str, ...] = ()
    render_role: str = ""

    # Compatibility aliases keep the rendering code and older tests readable while
    # the structured names above make provenance explicit.
    @property
    def key(self) -> str:
        return self.fact_id

    @property
    def zh(self) -> str:
        return self.text_zh

    @property
    def en(self) -> str:
        return self.text_en


@dataclass(frozen=True)
class SourceSemantics:
    operational_condition: tuple[str, ...] = ()
    applicability: tuple[str, ...] = ()
    risk: tuple[str, ...] = ()
    mitigation: tuple[str, ...] = ()
    restriction: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManualFactClause:
    text: str
    heading: str
    phase: str
    role_scope: tuple[str, ...]
    source_original_text: str
    excluded_sibling_clauses: tuple[str, ...] = ()
    excluded_sibling_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DutyContext:
    events: tuple[CalendarEvent, ...]

    @property
    def route(self) -> tuple[str, ...]:
        airports: list[str] = []
        seen: set[str] = set()
        for event in self.events:
            for airport in event.route:
                canonical = canonical_airport_name(airport)
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    airports.append(canonical)
        return tuple(airports)

    @property
    def role_map(self) -> dict[str, tuple[str, ...]]:
        roles: dict[str, set[str]] = {}
        for event in self.events:
            departure, arrival = event.route
            if departure:
                roles.setdefault(
                    canonical_airport_name(departure), set()
                ).add("departure")
            if arrival:
                roles.setdefault(
                    canonical_airport_name(arrival), set()
                ).add("arrival")
        role_order = {"departure": 0, "arrival": 1}
        return {
            airport: tuple(sorted(values, key=role_order.get))
            for airport, values in roles.items()
        }

    @property
    def uid(self) -> str:
        return "+".join(event.uid for event in self.events)

    @property
    def flight_number(self) -> str:
        return "/".join(
            unique(
                [event.flight_number for event in self.events if event.flight_number]
            )
        )

    @property
    def registration(self) -> str:
        return "/".join(
            unique(
                [event.registration for event in self.events if event.registration]
            )
        )

    @property
    def people(self) -> list[str]:
        return unique(
            [person for event in self.events for person in event.people]
        )

    @property
    def start(self) -> datetime:
        return self.events[0].start

    @property
    def end(self) -> datetime:
        return self.events[-1].end


FLIGHT_NUMBER_PARTS_RE = re.compile(
    r"^([A-Z0-9]*[A-Z])(\d{4})(?:[A-Z]+)?$",
    re.IGNORECASE,
)


def flight_number_parts(value: str) -> tuple[str, int] | None:
    """Return the carrier prefix and four-digit main number when unambiguous."""
    normalized = re.sub(r"\s+", "", value or "").upper()
    match = FLIGHT_NUMBER_PARTS_RE.fullmatch(normalized)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def flight_numbers_are_consecutive(first: str, second: str) -> bool:
    first_parts = flight_number_parts(first)
    second_parts = flight_number_parts(second)
    return bool(
        first_parts
        and second_parts
        and first_parts[0] == second_parts[0]
        and abs(first_parts[1] - second_parts[1]) == 1
    )


def split_flight_prep_groups_by_flight_number(
    flights: list[CalendarEvent],
) -> list[list[CalendarEvent]]:
    """Split one already-continuous duty into independently rendered prep reports."""
    if not flights:
        return []
    groups: list[list[CalendarEvent]] = [[flights[0]]]
    for event in flights[1:]:
        previous = groups[-1][-1]
        if flight_numbers_are_consecutive(previous.flight_number, event.flight_number):
            groups[-1].append(event)
        else:
            groups.append([event])
    return groups


AIRPORT_MANUAL_FILE = (
    "knowledge/pdf/"
    "AirDropManual-机场特点汇总(Airport Information)20260720-Manual.pdf"
)
SUPPLEMENT_FILE = "config/airport_supplements.json"

AIRPORT_SOURCE_LOCATIONS: dict[str, dict[str, str]] = {
    "新加坡樟宜": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "256-260",
        "source_heading": "新加坡机场运行特点 SINGAPORE(SIN/WSSS)",
    },
    "上海浦东": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "448-451",
        "source_heading": "上海/浦东机场运行特点 SHANGHAIPUDONG(PVG/ZSPD)",
    },
    "上海虹桥": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "414-416",
        "source_heading": "上海/虹桥机场运行特点 SHANGHAIHONGQIAO(SHA/ZSSS)",
    },
    "石家庄正定": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "339-342",
        "source_heading": "石家庄/正定机场运行特点 SHIJIAZHUANGZHENGDING(SJW/ZBSJ)",
    },
    "西宁曹家堡": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "660-663",
        "source_heading": "西宁/曹家堡机场运行特点 XININGCAOJIAPU(XNN/ZLXN)",
    },
    "南昌昌北": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "435-439",
        "source_heading": "南昌/昌北机场运行特点 NANCHANGCHANGBEI(KHN/ZSCN)",
    },
    "丽江三义": {
        "source_file": AIRPORT_MANUAL_FILE,
        "source_page": "795-799",
        "source_heading": "丽江/三义机场运行特点",
    },
}


AIRPORT_ENGLISH_NAMES = {
    "新加坡樟宜": "Singapore Changi",
    "上海浦东": "Shanghai Pudong",
    "上海虹桥": "Shanghai Hongqiao",
    "西宁曹家堡": "Xining Caojiabao",
    "南昌昌北": "Nanchang Changbei",
    "丽江三义": "Lijiang Sanyi",
}

PILOT_ENGLISH_NAMES = {
    "段洋硕": "Duan Yangshuo",
}

CURATED_TYPICAL_ENGLISH: dict[str, list[str]] = {
    "新加坡樟宜": [
        "An event has occurred in which external factors resulted in crossing the runway threshold too high.",
        "Temporary runway or arrival/departure procedure changes have occurred during three-runway operations.",
        "Incorrect ATC FOLLOW GREEN guidance has been reported, creating a risk of taxi-route misidentification.",
        "Afternoon thermal convection can produce thunderstorms that affect clearance, taxi, and departure spacing.",
    ],
    "上海浦东": [
        "A low-altitude bird strike has caused radome damage.",
        "An approach has continued after visual reference was lost at low altitude.",
        "TA/RA events have occurred during approach.",
        "Complex taxi routes and multiple hotspots create wrong-turn and runway-incursion risks.",
    ],
    "西宁曹家堡": [
        "A windshear warning event has occurred.",
        "A regulator safety notice identifies repeated abnormal aircraft movement associated with brake failures.",
        "Spring and summer turbulence and windshear have contributed to unstable approaches and go-arounds.",
        "The pronounced downslope on runway 11 can create visual illusions and speed-judgement errors during approach and departure.",
    ],
    "南昌昌北": [
        "Frequent summer thunderstorms can produce windshear.",
        "Bird activity associated with nearby Poyang Lake creates a significant bird-strike risk.",
        "Frequent military and civil operations around nearby air bases can be accompanied by GPS interference.",
        "Radar vectors and direct routings during approach can leave the aircraft high and lead to an unstable approach.",
    ],
    "丽江三义": [
        "A SINK RATE warning event has occurred.",
        "A windshear event has occurred.",
        "A hard-landing event has occurred.",
        "An event has occurred in which configuration was extended above the applicable altitude limit.",
    ],
}

SINGAPORE_DEPARTURE_FACTS = (
    BilingualFact(
        "wsss_irs_alignment",
        "新加坡属于低纬度机场，驾驶舱准备阶段确认完成IRS完全校准；同时核对跑道、SID、初始高度、第一航路点和高度速度限制。",
        "As Singapore is a low-latitude airport, confirm a full IRS alignment during cockpit preparation. Cross-check the runway, SID, initial altitude, first waypoint, and all altitude and speed constraints.",
    ),
    BilingualFact(
        "wsss_clearance",
        "如本次放行使用M771，PDC不适用。我们应通过语音取得并完整复诵放行，核实TOBT、申请巡航高度及DUDIS限制通过时间；G4机位通信质量差时，听不清必须再次证实。",
        "If the clearance uses M771, PDC is not available. We must obtain and fully read back the voice clearance, verify the TOBT, requested cruise level, and DUDIS crossing-time restriction, and request confirmation whenever reception at stand G4 is unclear.",
    ),
    BilingualFact(
        "wsss_ground",
        "滑行时我们应完整复诵路线，R、S滑行道不超过20kt；使用FOLLOW GREEN时，灯光中断、方向异常或与ATC指令不一致必须停止并证实。亮红色停止排灯前必须等待，只有同时收到ATC进入或穿越许可且停止排灯熄灭，才可进入或穿越跑道、滑行道。",
        "We must read back the complete taxi route and keep taxiways R and S at or below 20 kt. When using FOLLOW GREEN, stop and confirm if the lights end, indicate an unexpected direction, or conflict with the ATC clearance. Hold behind an illuminated red stop bar; enter or cross a runway or taxiway only after receiving ATC clearance and confirming that the stop-bar lights are extinguished.",
    ),
    BilingualFact(
        "wsss_sid",
        "我们应按实际跑道核对SID航图、爬升梯度和初始高度。20C跑道的MERSING9B在数据库中对应VMR9B，02C跑道的MERSING6A对应VMR6A；离场4000ft以下速度不得超过230kt。",
        "We must use the actual runway to cross-check the SID chart, climb gradient, and initial altitude. For runway 20C, MERSING9B corresponds to VMR9B in the database; for runway 02C, MERSING6A corresponds to VMR6A. Departure speed must not exceed 230 kt below 4000 ft.",
    ),
    BilingualFact(
        "wsss_initial_route",
        "起飞后如ATC指挥直飞MERSING并上升至FL120，我们应结合进港冲突控制上升率并核对后续DOLOX衔接。换频胡志明后，如管制询问CPDLC能力，我们应明确报告公司暂不具备CPDLC运行能力，并持续核对DUDIS限制。",
        "If ATC clears us direct MERSING and to climb to FL120 after departure, we must manage the climb rate for arrival traffic and verify the onward connection to DOLOX. After transfer to Ho Chi Minh Control, if asked about CPDLC capability, we must report that the company is not CPDLC capable and continue monitoring the DUDIS restriction.",
    ),
)

PUDONG_ARRIVAL_FACTS = (
    BilingualFact(
        "zspd_arrival_change_energy",
        "浦东进场程序较多且有时临时更改，非繁忙时段可能收到直飞。进场前我们应核对实际跑道、STAR、进近方式、第一相关航路点及全部高度速度限制；收到直飞、雷达引导或跑道变化后立即修改MCDU并重新评估剩余距离、下降剖面、减速和构型，不能稳定时复飞。",
        "Pudong has multiple arrival procedures that may change at short notice, and direct clearances may be issued outside busy periods. Before arrival, we must cross-check the actual runway, STAR, approach, first relevant waypoint, and all altitude and speed constraints. After any direct clearance, radar vector, or runway change, update the MCDU and reassess the remaining distance, descent profile, deceleration, and configuration; go around if the approach cannot be stabilized.",
    ),
    BilingualFact(
        "zspd_thunderstorm",
        "浦东夏季雷雨可能伴随低云、低能见、湿跑道和风切变。我们应全程合理使用气象雷达，提前评估绕飞、等待、着陆性能和备降油量；出现风切变警告或状态不稳定时按程序复飞。",
        "Summer thunderstorms at Pudong may bring low cloud, reduced visibility, a wet runway, and windshear. We must use the weather radar appropriately throughout the flight and assess deviation, holding, landing performance, and diversion fuel early; execute the prescribed go-around for a windshear warning or an unstable condition.",
    ),
    BilingualFact(
        "zspd_tcas",
        "浦东进近阶段曾多次触发TA/RA。接近目标高度最后2000ft且有邻近航空器时，我们应合理控制升降率并持续监控冲突趋势；发生RA时严格执行现行程序。",
        "Multiple TA/RA events have occurred during approach to Pudong. Within the last 2000 ft before the cleared altitude, when nearby traffic is present, we must manage the vertical rate and monitor the conflict trend; comply strictly with the current RA procedure if an RA occurs.",
    ),
    BilingualFact(
        "zspd_bird",
        "浦东东侧海岸鸟类活动与低高度进近航迹可能重叠。我们应关注ATIS、ATC和机场鸟情通报，加强低高度外部观察；发现鸟群或发生鸟击后，根据飞机状态执行程序并及时报告。",
        "Bird activity along the coast east of Pudong may overlap the low-altitude approach path. We must monitor ATIS, ATC, and airport bird advisories and maintain an effective external scan at low altitude; after sighting a flock or sustaining a bird strike, apply the appropriate procedure for the aircraft condition and report promptly.",
    ),
    BilingualFact(
        "zspd_runway_occupancy",
        "浦东通常要求落地后占跑道时间不大于50秒；预计不能做到时，应不晚于接地前5分钟通知ATC。",
        "Pudong normally requires runway occupancy after landing not to exceed 50 seconds. If we expect that this cannot be achieved, advise ATC no later than 5 minutes before touchdown.",
    ),
    BilingualFact(
        "zspd_adgs_entry",
        "进入设有ADGS的机位时，如引导指示有疑问，或人工引导机位的地面接机人员未就位，我们应立即停止滑行、通知ATC，并保持发动机运转等待处置。",
        "When entering a stand equipped with ADGS, if the guidance is doubtful or the ground reception personnel are not in position at a manually guided stand, we must stop, notify ATC, and keep the engines running while awaiting further action.",
    ),
)

PUDONG_DEPARTURE_FACTS = (
    BilingualFact(
        "zspd_departure_procedure",
        "浦东2606期程序已经调整。驾驶舱准备阶段我们应核对实际跑道、SID、跑道过渡、离场公共段、第一航路点及全部高度速度限制，PF和PM独立检查MCDU，防止新旧程序混淆。",
        "Pudong procedures changed in cycle 2606. During cockpit preparation, we must cross-check the actual runway, SID, runway transition, common departure segment, first waypoint, and all altitude and speed constraints, with independent PF and PM verification of the MCDU to prevent old/new procedure confusion.",
    ),
    BilingualFact(
        "zspd_departure_ground",
        "浦东推出时可能收到“推出开车”或“推出到位报告”两类指令，我们应准确区分并完整复诵。滑行中如发现地面滑行引导车，应按机场细则关闭滑行灯并跟随引导车滑行。",
        "At Pudong, the apron may issue either a push-and-start clearance or an instruction to report after pushback. We must distinguish and read back the instruction accurately. If a ground follow-me vehicle is encountered during taxi, switch off the taxi light and follow the vehicle as required by the airport rules.",
    ),
    BilingualFact(
        "zspd_departure_traffic",
        "浦东空域航流密集。我们应严格执行初始高度、速度和航向指令，收到直飞或离场变化后重新核对MCDU和初始航路衔接；接近目标高度最后2000ft有邻近航空器时合理控制升降率，并按现行程序处置TA/RA。",
        "Pudong terminal traffic is dense. We must comply with initial altitude, speed, and heading instructions and recheck the MCDU and initial route connection after a direct clearance or departure change. Within the last 2000 ft before the target altitude, manage vertical rate for nearby traffic and apply the current TA/RA procedure.",
    ),
    BilingualFact(
        "zspd_departure_weather_bird",
        "浦东夏季雷雨可能伴随低云、湿跑道和风切变，东侧海岸鸟类活动也可能与低高度离场航迹重叠。我们应全程合理使用气象雷达，提前制定绕飞和返场预案，并关注ATIS、ATC和机场鸟情通报。",
        "Summer thunderstorms at Pudong may bring low cloud, a wet runway, and windshear, while coastal bird activity east of the airport may overlap the low-altitude departure path. We must use the weather radar appropriately throughout the flight, prepare deviation and return plans early, and monitor ATIS, ATC, and airport bird advisories.",
    ),
    BilingualFact(
        "zspd_departure_navigation",
        "如实际涉及16L、17R、34R或35L跑道，我们应使用最新有效导航标准和航图勘误；执行VOR 17L或VOR 35R相关程序时，重点核对导航数据库修正内容和高度限制。",
        "If operations involve runways 16L, 17R, 34R, or 35L, we must use the latest valid navigation criteria and chart corrections. For procedures associated with VOR 17L or VOR 35R, cross-check navigation-database corrections and altitude constraints.",
    ),
)

CURATED_CORE_ENGLISH: dict[str, list[str]] = {
    "西宁曹家堡": [
        "Xining Caojiabao is a Category II complex high-altitude airport at 7166 ft. In high-and-hot conditions, we must verify performance, runway, temperature, wind, and corrections, with particular attention to takeoff margin and tire overspeed.",
        "Runway 11 has a pronounced takeoff downslope and can produce rapid acceleration and tire-overspeed risk. The PM must call V1 and VR accurately, and the PF must rotate at the normal rate without anticipating or delaying rotation.",
        "Runway 11 has an approach downslope of about -0.6%, which can create a visual illusion. Xining requires a stabilized approach by 1300 ft; if speed, configuration, descent rate, or thrust is unstable, we must go around.",
        "Spring and summer turbulence and windshear are significant. On the runway 11 ILS, a tailwind-to-headwind change near the FAF may create turbulence; complete deceleration and configuration early, and maintain Config 2 at 160-170 kt before glideslope capture.",
        "The airport is surrounded by terrain, with higher terrain southwest of the runway. We must remain on the published track and keep terrain displayed on at least one ND, avoiding lateral deviation and a high descent rate at low altitude.",
        "Brake failures have caused abnormal aircraft movement at Xining. Before setting the parking brake, confirm that the aircraft is completely stopped, apply the procedure, and complete a cross-check.",
    ],
    "南昌昌北": [
        "Summer thunderstorms and windshear are frequent at Nanchang. Before arrival or departure, we must review the latest radar image and trend, request deviations early, and remain clear of thunderstorms.",
        "Poyang Lake creates significant bird activity. During low-altitude arrival and departure, we must monitor the bird-strike risk and brief the return and malfunction plan before takeoff.",
        "Nearby military airfields produce frequent military and civil activity and possible GPS interference. We must follow the published procedure and cross-check raw navigation, track, and ATC instructions after any navigation anomaly.",
        "Radar vectors and direct routings can leave the aircraft high on approach. For the runway 03 ILS from the north, request descent and deceleration early rather than delaying configuration until late final.",
        "Higher terrain lies southwest of the airport, and arrivals from the west are terrain-sensitive. We must comply with the IAF and CN104 altitude constraints and keep terrain displayed on at least one ND.",
        "The current Nanchang ATIS may specify a missed-approach altitude of 1500 m with runway heading initially. During approach preparation, cross-check the missed-approach altitude against ATIS, the chart, and ATC, and confirm any uncertainty.",
    ],
}

LIJIANG_CORE_FACTS = (
    BilingualFact(
        "zplj_terrain",
        "丽江机场标高7358ft，四周地形复杂。我们应严格按照公布程序飞行，持续监控航迹、高度、最低安全高度和导航精度；接受雷达引导、直飞或天气绕飞前，必须确认地形间隔。",
        "Lijiang Airport elevation is 7358 ft and the surrounding terrain is complex. We must follow the published procedure and monitor track, altitude, minimum safe altitude, and navigation accuracy; before accepting radar vectors, a direct clearance, or a weather deviation, confirm terrain clearance.",
    ),
    BilingualFact(
        "zplj_descent",
        "丽江进近可能下降偏晚、剖面偏高。我们应提前计划下降、减速和构型，结合剩余距离、顺风、地速和下降率及时申请；尽量在低于5700m后选择形态，不能稳定时复飞。",
        "Descent clearance into Lijiang may be late and the profile may remain high. We must plan descent, deceleration, and configuration early and make timely requests using remaining distance, tailwind, groundspeed, and descent rate; select configuration below 5700 m whenever possible and go around if the approach cannot be stabilized.",
    ),
    BilingualFact(
        "zplj_runway20",
        "20号跑道相关进近下降梯度较大，五边可能有顺风。我们应提前建立着陆构型，持续监控下降率、速度、推力和垂直偏差；未在规定高度达到稳定标准时复飞。",
        "Approaches associated with runway 20 have a steep descent gradient and may have a tailwind on final. We must establish landing configuration early and monitor descent rate, speed, thrust, and vertical deviation; go around if stabilization criteria are not met by the required altitude.",
    ),
    BilingualFact(
        "zplj_rain",
        "丽江5月至9月处于雨季。我们应评估降水、低云、风切变、湿跑道、顺风和着陆距离，并根据跑道状况、风、重量和制动效应明确复飞、等待或备降预案。",
        "Lijiang is in its rainy season from May through September. We must assess precipitation, low cloud, windshear, wet-runway conditions, tailwind, and landing distance, and define go-around, holding, or diversion plans using runway condition, wind, weight, and braking action.",
    ),
    BilingualFact(
        "zplj_navigation",
        "丽江进近区域实施ADS-B管制，GPS可能不稳定。我们应监控GPS状态、导航精度、位置和航迹；出现GPS PRIMARY LOST或导航性能下降时，及时报告ATC并准备使用其他导航方式。",
        "ADS-B control is used in the Lijiang approach area, and GPS may be unstable. We must monitor GPS status, navigation accuracy, position, and track; after GPS PRIMARY LOST or degraded navigation performance, report promptly to ATC and prepare to use other navigation sources.",
    ),
)

FACT_PROVENANCE: dict[str, dict[str, object]] = {
    "wsss_irs_alignment": {
        "airport": "新加坡樟宜",
        "source": "PDF",
        "source_section": "20260720手册第258页／特殊运行要求：低纬度机场IRS完全校准",
        "operational_phase": "preparation",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 100,
    },
    "wsss_clearance": {
        "airport": "新加坡樟宜",
        "source": "PDF",
        "source_section": "20260720手册第256-257页／放行与PDC、DUDIS限制",
        "operational_phase": "clearance",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 90,
    },
    "wsss_ground": {
        "airport": "新加坡樟宜",
        "source": "PDF",
        "source_section": "20260720手册第256-260页／地面、FOLLOW GREEN与停止排灯",
        "operational_phase": "ground",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure", "arrival"),
        "importance": 95,
    },
    "wsss_sid": {
        "airport": "新加坡樟宜",
        "source": "PDF",
        "source_section": "20260720手册第257页／离场SID与速度限制",
        "operational_phase": "departure",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 95,
    },
    "wsss_initial_route": {
        "airport": "新加坡樟宜",
        "source": "PDF",
        "source_section": "20260720手册第258-259页／初始航路与CPDLC能力报告",
        "operational_phase": "initial_climb",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 90,
    },
    "zspd_arrival_change_energy": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第450-451页／进场程序、临时更改与直飞",
        "operational_phase": "arrival",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("arrival",),
        "importance": 95,
    },
    "zspd_thunderstorm": {
        "airport": "上海浦东",
        "source": "supplement",
        "source_file": SUPPLEMENT_FILE,
        "source_page": "N/A",
        "source_heading": "上海浦东",
        "source_section": "airport_supplements.json／上海浦东／core_threats／夏季雷雨",
        "operational_phase": "weather",
        "airport_specific": False,
        "category": "core",
        "role_scope": ("departure", "arrival"),
        "importance": 88,
    },
    "zspd_tcas": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第448、451页／其他威胁：进近TA/RA",
        "operational_phase": "approach",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("arrival",),
        "importance": 92,
    },
    "zspd_bird": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第448页／其他威胁：东侧海岸鸟类活动",
        "operational_phase": "approach",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure", "arrival"),
        "importance": 90,
    },
    "zspd_runway_occupancy": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_page": "448",
        "source_heading": "上海/浦东机场运行特点",
        "source_section": "二、核心威胁／2.道面特点",
        "operational_phase": "landing",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("arrival",),
        "importance": 82,
        "semantic_key": "zspd_runway_occupancy",
    },
    "zspd_adgs_entry": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_page": "448",
        "source_heading": "上海/浦东机场运行特点",
        "source_section": "二、核心威胁／4.其他威胁／第(3)项",
        "operational_phase": "ground",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("arrival",),
        "importance": 99,
        "semantic_key": "zspd_adgs_entry",
    },
    "zspd_departure_procedure": {
        "airport": "上海浦东",
        "source": "CURATED",
        "source_section": "浦东人工精选／2606离场程序核对",
        "operational_phase": "preparation",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 92,
    },
    "zspd_departure_ground": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第448-449页／指挥特点与地面滑行引导车",
        "operational_phase": "ground",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 90,
    },
    "zspd_departure_traffic": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第448、451页／进近TA/RA",
        "operational_phase": "approach",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("arrival",),
        "importance": 80,
    },
    "zspd_departure_weather_bird": {
        "airport": "上海浦东",
        "source": "PDF",
        "source_section": "20260720手册第448页／东侧海岸鸟情；补充知识库／夏季雷雨",
        "operational_phase": "weather",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 88,
    },
    "zspd_departure_navigation": {
        "airport": "上海浦东",
        "source": "CURATED",
        "source_section": "浦东人工精选／导航标准与航图勘误",
        "operational_phase": "departure",
        "airport_specific": True,
        "category": "core",
        "role_scope": ("departure",),
        "importance": 85,
    },
    "zplj_terrain": {
        "airport": "丽江三义",
        "source": "CURATED",
        "source_section": "丽江人工精选／高原地形",
        "operational_phase": "terrain",
        "airport_specific": True,
        "category": "core",
        "importance": 96,
    },
    "zplj_descent": {
        "airport": "丽江三义",
        "source": "CURATED",
        "source_section": "丽江人工精选／下降剖面",
        "operational_phase": "arrival",
        "airport_specific": True,
        "category": "core",
        "importance": 88,
    },
    "zplj_runway20": {
        "airport": "丽江三义",
        "source": "CURATED",
        "source_section": "丽江人工精选／20号跑道进近",
        "operational_phase": "approach",
        "airport_specific": True,
        "category": "core",
        "importance": 90,
    },
    "zplj_rain": {
        "airport": "丽江三义",
        "source": "CURATED",
        "source_section": "丽江人工精选／雨季运行",
        "operational_phase": "weather",
        "airport_specific": True,
        "category": "core",
        "importance": 84,
    },
    "zplj_navigation": {
        "airport": "丽江三义",
        "source": "CURATED",
        "source_section": "丽江人工精选／ADS-B与GPS",
        "operational_phase": "navigation",
        "airport_specific": True,
        "category": "core",
        "importance": 94,
    },
}

FACT_SOURCE_PAGES = {
    "wsss_irs_alignment": "258",
    "wsss_clearance": "256-257",
    "wsss_ground": "256-260",
    "wsss_sid": "257",
    "wsss_initial_route": "258-259",
    "zspd_arrival_change_energy": "450-451",
    "zspd_tcas": "448,451",
    "zspd_bird": "448",
    "zspd_runway_occupancy": "448",
    "zspd_adgs_entry": "448",
    "zspd_departure_procedure": "450",
    "zspd_departure_ground": "448-449",
    "zspd_departure_traffic": "448,451",
    "zspd_departure_weather_bird": "448",
    "zspd_departure_navigation": "450-451",
    "zplj_terrain": "795-799",
    "zplj_descent": "795-799",
    "zplj_runway20": "795-799",
    "zplj_rain": "795-799",
    "zplj_navigation": "795-799",
}

CURATED_CORE_PHASES: dict[str, tuple[str, ...]] = {
    "西宁曹家堡": (
        "preparation",
        "departure",
        "approach",
        "weather",
        "terrain",
        "ground",
    ),
    "南昌昌北": (
        "weather",
        "approach",
        "navigation",
        "arrival",
        "terrain",
        "approach",
    ),
}

CURATED_CORE_SOURCE_PAGES: dict[str, tuple[str, ...]] = {
    "西宁曹家堡": ("661-663", "661-662", "662", "660", "660,663", "660"),
    "南昌昌北": ("435", "435", "435", "435,437-438", "435,437-438", "435"),
}

SOURCE_PRIORITY = {"CURATED": 0, "supplement": 1, "PDF": 2, "TXT": 3}
SOURCE_BUILD_PRIORITY = {"PDF": 0, "TXT": 0, "supplement": 1, "CURATED": 2}
SEASON_MONTHS: dict[str, tuple[int, ...]] = {
    "春季": (3, 4, 5),
    "夏季": (6, 7, 8),
    "秋季": (9, 10, 11),
    "冬季": (12, 1, 2),
    "冬春季": (12, 1, 2, 3, 4, 5),
    "春夏季": (3, 4, 5, 6, 7, 8),
    "夏秋季": (6, 7, 8, 9, 10, 11),
}
SEASON_LABELS = tuple(sorted(SEASON_MONTHS, key=len, reverse=True))
SEASON_LABEL_RE = re.compile("|".join(map(re.escape, SEASON_LABELS)))
MONTH_SCOPE_RE = re.compile(
    r"(?<!\d)(?P<start>1[0-2]|[1-9])\s*"
    r"(?:—|–|-|至|到|~|～)\s*"
    r"(?P<end>1[0-2]|[1-9])\s*月"
)
SINGLE_MONTH_SCOPE_RE = re.compile(r"(?<!\d)(?P<month>1[0-2]|[1-9])\s*月")

CORE_TOPIC_ORDER = (
    "preparation",
    "ground",
    "departure",
    "arrival",
    "approach",
    "terrain",
    "performance",
    "weather",
    "special",
)
ROLE_TOPIC_PRIORITY = {
    "departure": (
        "preparation",
        "ground",
        "departure",
        "performance",
        "weather",
        "terrain",
        "special",
        "arrival",
        "approach",
    ),
    "arrival": (
        "arrival",
        "approach",
        "terrain",
        "weather",
        "ground",
        "special",
        "performance",
        "preparation",
        "departure",
    ),
    "transit": (
        "arrival",
        "approach",
        "ground",
        "departure",
        "preparation",
        "terrain",
        "performance",
        "weather",
        "special",
    ),
}
ROLE_PHASE_PRIORITY = {
    "departure": {
        "preparation": 0,
        "clearance": 1,
        "ground": 2,
        "departure": 3,
        "initial_climb": 4,
        "navigation": 5,
        "weather": 6,
        "terrain": 7,
        "arrival": 20,
        "approach": 21,
        "landing_ground": 22,
    },
    "arrival": {
        "arrival": 0,
        "approach": 1,
        "weather": 2,
        "terrain": 3,
        "landing": 4,
        "landing_ground": 5,
        "ground": 6,
        "navigation": 7,
        "preparation": 8,
        "clearance": 20,
        "departure": 21,
        "initial_climb": 22,
    },
    "transit": {
        "preparation": 0,
        "clearance": 1,
        "ground": 2,
        "departure": 3,
        "initial_climb": 4,
        "arrival": 5,
        "approach": 6,
        "weather": 7,
        "terrain": 8,
        "landing": 9,
        "landing_ground": 10,
        "navigation": 11,
        "unspecified": 12,
    },
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate rule-based flight preparation text without API.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--days-ahead", type=int, default=1)
    parser.add_argument("--flight-number", default="")
    parser.add_argument("--departure", default="")
    parser.add_argument("--arrival", default="")
    parser.add_argument(
        "--generate-english",
        choices=("auto", "yes", "no"),
        default="auto",
    )
    return parser.parse_args()


def determine_target_date(target_date: str, days_ahead: int) -> date:
    if target_date:
        return date.fromisoformat(target_date)
    return (now_beijing() + timedelta(days=days_ahead)).date()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        item = normalize_text(item)
        key = re.sub(r"[\s，。；、:：()（）]", "", item)
        if item and key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def format_date_cn(value: str) -> str:
    try:
        d = date.fromisoformat(value)
        return f"{d.month}月{d.day}日"
    except Exception:
        return value


def format_date_cn_padded(value: str) -> str:
    try:
        d = date.fromisoformat(value)
        return f"{d.month:02d}月{d.day:02d}日"
    except Exception:
        return value


def format_profile_date_cn(value: str) -> str:
    value = (value or "").strip()
    match = re.fullmatch(r"0?(\d{1,2})月0?(\d{1,2})日", value)
    if match:
        return f"{int(match.group(1))}月{int(match.group(2))}日"
    return format_date_cn(value)


def profile_intro(profile: dict, aircraft_types: list[str]) -> str:
    name = profile.get("name", "")
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    level = profile.get("technical_level", "")
    promotion = profile.get("promotion_date", "")
    parts = [f"我是{unit}{role}{name}" if name else f"{unit}{role}".strip()]
    if level:
        parts.append(f"目前技术级别为{level}")
    if promotion:
        parts.append(f"晋级日期{promotion}")

    if profile.get("stage_hours") is not None:
        parts.append(f"本阶段经历时间{profile['stage_hours']}小时")
    if profile.get("stage_landings") is not None:
        parts.append(f"起落{profile['stage_landings']}个")
    sim_suffix = "（含模拟机）" if profile.get("simulation_included") else ""
    if profile.get("landings_90_days") is not None:
        parts.append(f"近90天起落数{profile['landings_90_days']}个{sim_suffix}")
    if profile.get("landings_30_days") is not None:
        parts.append(f"近一个月起落{profile['landings_30_days']}个{sim_suffix}")
    if profile.get("duty_day"):
        parts.append(f"明日为本人本次值勤期第{profile['duty_day']}天")
    if aircraft_types:
        parts.append(f"本次执飞机型{'/'.join(aircraft_types)}")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        text = f"上次操纵落地机场为{last['airport']}"
        if last.get("date"):
            text += format_date_cn(last["date"])
        parts.append(text)
    return "，".join(p for p in parts if p) + "。"


def experience_records(experience: dict, airports: list[str], target: date) -> list[dict]:
    records: list[dict] = []
    airport_map = experience.get("airports") or {}
    rolling_days = int(experience.get("rolling_days") or 90)
    cutoff = target - timedelta(days=rolling_days)
    for airport in airports:
        canonical = canonical_airport_name(airport)
        record = airport_map.get(canonical)
        last = record.get("last_operated", "") if isinstance(record, dict) else ""
        within = False
        if last:
            try:
                within = date.fromisoformat(last) >= cutoff
            except Exception:
                within = False
        records.append({"airport": canonical, "last": last, "within": within})
    return records


def experience_text(records: list[dict]) -> str:
    operated = []
    not_operated = []
    for rec in records:
        if rec["within"]:
            suffix = f"（最近{format_date_cn(rec['last'])}）" if rec["last"] else ""
            operated.append(f"{rec['airport']}{suffix}")
        else:
            not_operated.append(rec["airport"])
    lines = []
    if operated:
        lines.append("近3个月内已运行过本次航线涉及的：" + "、".join(operated) + "。")
    if not_operated:
        lines.append("近3个月内未记录运行过本次航线涉及的：" + "、".join(not_operated) + "。")
    return "\n".join(lines)


def strip_terminal_punct(value: str) -> str:
    return (value or "").strip().rstrip("。；;，, .")


def feedback_text(profile: dict) -> str:
    feedback = profile.get("recent_feedback") or {}
    pf = strip_terminal_punct(feedback.get("PF", ""))
    pm = strip_terminal_punct(feedback.get("PM", ""))
    if not pf and not pm:
        return ""

    parts = []
    if pf:
        parts.append(f"上一次作为PF教员评价：{pf}")
    if pm:
        parts.append(f"作为PM机长评价：{pm}")
    heading = "上一次飞行中机长/教员对我优缺点的评价（作为PF/PM各取最近一次）："
    return heading + "\n" + "；".join(parts).rstrip("；") + "。"




def flight_lines(flights: list[CalendarEvent]) -> list[str]:
    lines = []
    for idx, event in enumerate(flights, start=1):
        dep, arr = event.route
        time_text = f"{event.start:%H:%M}-{event.end:%H:%M}"
        cross = "（跨日）" if event.end.date() > event.start.date() else ""
        extra = []
        if event.checkin:
            extra.append(f"签到{event.checkin}")
        if event.aircraft_type:
            extra.append(f"机型{event.aircraft_type}")
        if event.registration:
            extra.append(f"注册号{event.registration}")
        tail = "；" + "，".join(extra) if extra else ""
        lines.append(f"{idx}. {event.flight_number} {dep}→{arr}，{time_text}{cross}{tail}。")
    return lines


AIRPORT_SHORT_NAMES = {
    "上海浦东": "浦东",
    "上海虹桥": "虹桥",
    "丽江三义": "丽江",
    "揭阳潮汕": "揭阳",
    "扬州泰州": "扬州",
    "长春龙嘉": "长春",
    "深圳宝安": "深圳",
    "济南遥墙": "济南",
    "大连周水子": "大连",
    "沈阳桃仙": "沈阳",
    "兰州中川": "兰州",
    "威海大水泊": "威海",
    "乌兰巴托成吉思汗": "乌兰巴托",
    "釜山金海": "釜山",
    "成都双流": "成都双流",
    "名古屋中部": "名古屋",
    "济州": "济州",
    "济州国际": "济州",
    "西宁曹家堡": "西宁曹家堡",
    "西宁": "西宁曹家堡",
    "南昌昌北": "南昌昌北",
    "南昌": "南昌昌北",
}


def short_airport_name(airport: str) -> str:
    if airport in AIRPORT_SHORT_NAMES:
        return AIRPORT_SHORT_NAMES[airport]
    return airport.replace("国际机场", "").replace("机场", "").strip()


def airport_with_suffix(airport: str) -> str:
    name = canonical_airport_name(airport).strip()
    if not name:
        return ""
    return name.removesuffix("国际机场").removesuffix("机场") + "机场"


def personal_intro(profile: dict, records: list[dict], aircraft_types: list[str]) -> str:
    name = profile.get("name", "")
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    parts = [f"我是{unit}{role}{name}" if name else f"{unit}{role}".strip()]
    if profile.get("technical_level"):
        parts.append(f"目前技术级别{profile['technical_level']}")
    if profile.get("promotion_date"):
        parts.append(f"晋级日期{profile['promotion_date']}")
    if profile.get("stage_hours") is not None:
        parts.append(f"本阶段经历时间{profile['stage_hours']}小时")
    if profile.get("stage_landings") is not None:
        parts.append(f"起落{profile['stage_landings']}个")
    sim_suffix = "（含模拟机）" if profile.get("simulation_included") else ""
    if profile.get("landings_90_days") is not None:
        parts.append(f"近90天起落数{profile['landings_90_days']}个{sim_suffix}")
    if profile.get("landings_30_days") is not None:
        parts.append(f"近一个月起落{profile['landings_30_days']}个{sim_suffix}")
    if profile.get("duty_day"):
        parts.append(f"明日为本人本次值勤期第{profile['duty_day']}天")
    if aircraft_types:
        parts.append(f"本次执飞机型{'/'.join(aircraft_types)}")

    operated = [r for r in records if r.get("within")]
    not_operated = [r for r in records if not r.get("within")]
    if not_operated:
        parts.append("近3个月未运行过" + "、".join(airport_with_suffix(r['airport']) for r in not_operated))
    if operated:
        for rec in operated:
            if rec.get("last"):
                parts.append(f"{airport_with_suffix(rec['airport'])}上次运行时间为{format_date_cn(rec['last'])}")
            else:
                parts.append(f"近3个月已运行过{airport_with_suffix(rec['airport'])}")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        last_text = f"上次操纵落地机场为{last['airport']}"
        if last.get("date"):
            last_text += format_date_cn(last["date"])
        parts.append(last_text)
    return "，".join(p for p in parts if p) + "。"


WX_CODES = {
    "-RA": "小雨", "RA": "降雨", "+RA": "大雨", "SHRA": "阵雨",
    "BR": "轻雾", "FG": "雾", "HZ": "霾", "TS": "雷暴", "TSRA": "雷雨",
    "DZ": "毛毛雨", "SN": "降雪", "-SN": "小雪", "FZFG": "冻雾",
}



def decode_weather_report(raw: str) -> list[str]:
    raw = normalize_text(raw).upper()
    if not raw:
        return []

    tokens = [token.strip("=,") for token in raw.split()]
    token_set = set(tokens)
    out: list[str] = []

    if "CAVOK" in token_set:
        out.append("CAVOK")
    metric_visibility = [
        int(token)
        for token in tokens
        if re.fullmatch(r"\d{4}", token)
    ]
    if metric_visibility:
        visibility = min(metric_visibility)
        if visibility == 9999:
            out.append("能见度10公里以上")
        elif visibility < 5000:
            out.append(f"能见度{visibility}米")

    statute_match = re.search(
        r"(?<!\S)(P?\d+(?:/\d+)?|\d+\s+\d+/\d+)SM(?!\S)",
        raw,
    )
    if statute_match:
        value = statute_match.group(1)
        more_than = value.startswith("P")
        value = value.removeprefix("P")
        miles = 0.0
        for part in value.split():
            if "/" in part:
                numerator, denominator = part.split("/", 1)
                miles += int(numerator) / int(denominator)
            else:
                miles += float(part)
        metres = round(miles * 1609.344)
        if more_than or miles >= 6:
            out.append("能见度10公里以上")
        elif metres < 5000:
            out.append(f"能见度约{metres}米")

    phenomena = [
        ("+TSRA", "强雷雨"), ("TSRA", "雷雨"), ("TS", "雷暴"),
        ("+SHRA", "强阵雨"), ("SHRA", "阵雨"),
        ("+RA", "大雨"), ("-RA", "小雨"), ("RA", "降雨"),
        ("FZFG", "冻雾"), ("FG", "雾"), ("BR", "轻雾"),
        ("HZ", "霾"), ("DZ", "毛毛雨"), ("-SN", "小雪"), ("SN", "降雪"),
    ]
    for code, label in phenomena:
        if code in token_set and label not in out:
            out.append(label)

    # Avoid broad duplicates when a more specific precipitation description exists.
    if any(x in out for x in ("小雨", "大雨", "阵雨", "强阵雨", "雷雨", "强雷雨")):
        out = [x for x in out if x != "降雨"]
    if any(x in out for x in ("雷雨", "强雷雨")):
        out = [x for x in out if x != "雷暴"]

    cloud_matches = re.findall(r"\b(FEW|SCT|BKN|OVC)(\d{3})\b", raw)
    if cloud_matches:
        order = {"OVC": 4, "BKN": 3, "SCT": 2, "FEW": 1}
        cover, height = sorted(cloud_matches, key=lambda x: (int(x[1]), -order[x[0]]))[0]
        feet = int(height) * 100
        if cover in ("BKN", "OVC") and feet <= 2000:
            cloud_cn = {"BKN": "多云", "OVC": "阴天"}[cover]
            out.append(f"{cloud_cn}，云底约{feet}英尺")

    if re.search(r"\bWS(?:\s+RWY\d{2}[LRC]?)?\b|WIND\s+SHEAR", raw):
        out.append("存在风切变提示")
    return unique(out)


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _day_hour_candidates(day: int, hour: int, reference: datetime) -> list[datetime]:
    ref = reference.astimezone(timezone.utc)
    candidates: list[datetime] = []
    for offset in (-1, 0, 1):
        year, month = _shift_month(ref.year, ref.month, offset)
        try:
            candidates.append(datetime(year, month, day, hour, tzinfo=timezone.utc))
        except ValueError:
            continue
    return candidates


def _nearest_day_hour(day: int, hour: int, reference: datetime) -> datetime | None:
    candidates = _day_hour_candidates(day, hour, reference)
    if not candidates:
        return None
    ref = reference.astimezone(timezone.utc)
    return min(candidates, key=lambda value: abs((value - ref).total_seconds()))


def parse_taf_validity(raw: str, reference: datetime) -> tuple[datetime, datetime] | None:
    match = re.search(r"\b(\d{2})(\d{2})/(\d{2})(\d{2})\b", (raw or "").upper())
    if not match:
        return None
    start_day, start_hour, end_day, end_hour = map(int, match.groups())
    start = _nearest_day_hour(start_day, start_hour, reference)
    if start is None:
        return None
    end_candidates = _day_hour_candidates(end_day, end_hour, start)
    end_candidates.extend(_day_hour_candidates(end_day, end_hour, start + timedelta(days=20)))
    end_candidates = [value for value in end_candidates if value > start]
    if not end_candidates:
        return None
    end = min(end_candidates)
    return start, end


TAF_CHANGE_MARKER_RE = re.compile(
    r"\b(?:FM\d{6}|BECMG|TEMPO|PROB(?:30|40)(?:\s+TEMPO)?)\b"
)


def _taf_period(
    text: str,
    reference: datetime,
) -> tuple[datetime, datetime] | None:
    match = re.search(r"\b(\d{2})(\d{2})/(\d{2})(\d{2})\b", text)
    if not match:
        return None
    start_day, start_hour, end_day, end_hour = map(int, match.groups())
    start = _nearest_day_hour(start_day, start_hour, reference)
    if start is None:
        return None
    end_candidates = [
        candidate
        for candidate in _day_hour_candidates(end_day, end_hour, start)
        if candidate > start
    ]
    return (start, min(end_candidates)) if end_candidates else None


def _taf_fm_time(marker: str, reference: datetime) -> datetime | None:
    match = re.fullmatch(r"FM(\d{2})(\d{2})(\d{2})", marker)
    if not match:
        return None
    day, hour, minute = map(int, match.groups())
    candidates = []
    for candidate in _day_hour_candidates(day, hour, reference):
        candidates.append(candidate.replace(minute=minute))
    if not candidates:
        return None
    ref = reference.astimezone(timezone.utc)
    return min(candidates, key=lambda value: abs((value - ref).total_seconds()))


def _taf_components_for_time(
    raw: str,
    operational_time: datetime,
) -> list[tuple[str, str]]:
    report = normalize_text(raw).upper()
    validity = parse_taf_validity(report, operational_time)
    moment = operational_time.astimezone(timezone.utc)
    if not validity or not (validity[0] <= moment <= validity[1]):
        return []

    markers = list(TAF_CHANGE_MARKER_RE.finditer(report))
    if not markers:
        return [("", report)]

    persistent = [report[: markers[0].start()].strip()]
    temporary: list[tuple[str, str]] = []
    for index, marker_match in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(report)
        marker = marker_match.group(0)
        body = report[marker_match.end() : end].strip()
        group_text = f"{marker} {body}".strip()
        if marker.startswith("FM"):
            effective = _taf_fm_time(marker, operational_time)
            if effective and moment >= effective:
                persistent = [body]
        elif marker == "BECMG":
            period = _taf_period(group_text, operational_time)
            if period and period[0] <= moment < period[1]:
                # During the transition, retain both states so risk extraction is
                # conservative. After the transition, the new state replaces the
                # old state and obsolete restrictions are no longer reported.
                persistent.append(body)
            elif period and moment >= period[1]:
                persistent = [body]
        else:
            period = _taf_period(group_text, operational_time)
            if period and period[0] <= moment <= period[1]:
                temporary.append((marker, body))
    return [("", part) for part in persistent if part] + temporary


def taf_text_for_time(raw: str, operational_time: datetime) -> str:
    return " ".join(
        f"{qualifier} {body}".strip()
        for qualifier, body in _taf_components_for_time(raw, operational_time)
        if body
    )


def decode_taf_for_time(raw: str, operational_time: datetime) -> list[str]:
    decoded: list[str] = []
    for qualifier, body in _taf_components_for_time(raw, operational_time):
        items = decode_weather_report(body)
        if qualifier.startswith("PROB30"):
            prefix = "30%概率短时" if "TEMPO" in qualifier else "30%概率"
            items = [prefix + item for item in items]
        elif qualifier.startswith("PROB40"):
            prefix = "40%概率短时" if "TEMPO" in qualifier else "40%概率"
            items = [prefix + item for item in items]
        decoded.extend(items)
    return unique(decoded)


def parse_metar_observation(raw: str, reference: datetime) -> datetime | None:
    match = re.search(r"\b(\d{2})(\d{2})(\d{2})Z\b", (raw or "").upper())
    if not match:
        return None
    day, hour, minute = map(int, match.groups())
    candidates: list[datetime] = []
    ref = reference.astimezone(timezone.utc)
    for offset in (-1, 0, 1):
        year, month = _shift_month(ref.year, ref.month, offset)
        try:
            candidates.append(datetime(year, month, day, hour, minute, tzinfo=timezone.utc))
        except ValueError:
            continue
    return min(candidates, key=lambda value: abs((value - ref).total_seconds())) if candidates else None


def relevant_airport_times(flights: list[CalendarEvent]) -> dict[str, list[datetime]]:
    result: dict[str, list[datetime]] = {}
    for event in flights:
        dep, arr = event.route
        if dep:
            result.setdefault(dep, []).append(event.start)
        if arr:
            result.setdefault(arr, []).append(event.end)
    return result


def weather_risk_sentence(
    airports: list[str],
    icao_map: dict[str, str],
    timeout: int,
    target: date | None = None,
    flights: list[CalendarEvent] | None = None,
) -> tuple[str, list[str], dict[str, dict]]:
    sentences: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, dict] = {}
    now = now_beijing()
    relevant_map = relevant_airport_times(flights or [])
    for airport in airports:
        icao = icao_map.get(airport, "")
        result = fetch_airport_weather(icao, timeout=timeout)
        relevant = relevant_map.get(airport, [])
        reference = relevant[0] if relevant else datetime.combine(target or now.date(), datetime.min.time(), tzinfo=now.tzinfo)
        relevant_utc = [value.astimezone(timezone.utc) for value in relevant]
        short = airport_with_suffix(airport)

        taf_period = parse_taf_validity(result.taf, reference)
        covered_times = [
            value
            for value in relevant
            if taf_period
            and taf_period[0] <= value.astimezone(timezone.utc) <= taf_period[1]
        ]
        decoded_by_time = [
            {
                "time": value.isoformat(),
                "decoded": decode_taf_for_time(result.taf, value),
            }
            for value in covered_times
        ]

        metar_time = parse_metar_observation(result.metar, now)
        metar_relevant = bool(
            result.metar
            and metar_time
            and relevant_utc
            and all(value <= now.astimezone(timezone.utc) for value in relevant_utc)
            and max(abs((value - now.astimezone(timezone.utc)).total_seconds()) for value in relevant_utc) <= 3 * 3600
            and abs((now.astimezone(timezone.utc) - metar_time).total_seconds()) <= 3 * 3600
        )

        source = "OUTSIDE_VALID_WINDOW"
        decoded: list[str] = []
        if relevant and len(covered_times) == len(relevant):
            source = "TAF"
            decoded = unique(
                [
                    item
                    for period in decoded_by_time
                    for item in period["decoded"]
                ]
            )
            if decoded:
                sentences.append(
                    short
                    + "航班时段TAF提示"
                    + "、".join(decoded[:4])
                    + "，最终以航前最新报文、放行资料及ATIS为准"
                )
            else:
                sentences.append(
                    short
                    + "已取得覆盖各运行时刻的TAF，"
                    "未识别出需特别提示的天气现象，"
                    "最终以航前最新报文、放行资料及ATIS为准"
                )
        elif metar_relevant:
            source = "METAR"
            decoded = decode_weather_report(result.metar)
            if decoded:
                sentences.append(short + "当前METAR显示" + "、".join(decoded[:4]) + "，最终以航前最新报文、放行资料及ATIS为准")
            else:
                sentences.append(short + "当前METAR未识别出需特别提示的天气现象，最终以航前最新报文、放行资料及ATIS为准")
        else:
            sentences.append(
                short + "航班时段天气以航前最新TAF/METAR及放行资料为准"
            )

        if result.error:
            warnings.append(f"{airport}天气获取提示：{result.error}")
        metadata[airport] = {
            "icao": icao,
            "source_used": source,
            "taf_validity_utc": [x.isoformat() for x in taf_period] if taf_period else [],
            "relevant_times": [x.isoformat() for x in relevant],
            "taf_decoded_by_time": decoded_by_time,
            "decoded": decoded,
            "fetch_error": result.error,
        }

    return "。".join(sentences) + ("。" if sentences else ""), warnings, metadata

def expand_incident_items(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        raw = strip_terminal_punct(item)
        if "曾发生" in raw and any(k in raw for k in ("SINK RATE", "风切变", "重着陆", "形态超高度")):
            for token in ("SINK RATE", "风切变", "重着陆", "形态超高度限制"):
                if token in raw:
                    suffix = "警告事件" if token == "SINK RATE" else "事件"
                    out.append(f"该机场曾发生{token}{suffix}。")
        else:
            out.append(item)
    return unique(out)


def seasonal_clean(item: str, month: int) -> str:
    text = strip_terminal_punct(item)
    if 5 <= month <= 9:
        text = re.sub(r"1\s*-\s*4\s*月[^；。]*[；。]?", "", text).strip("；。 ")
    elif month in (10, 11, 12, 1, 2, 3):
        text = re.sub(r"5\s*-\s*9\s*月[^；。]*[；。]?", "", text).strip("；。 ")
    return text + ("。" if text else "")


def build_typical_items(risks: list[str], threats: list[str], month: int, max_items: int = 5) -> list[str]:
    # 典型不安全事件必须是真正事件或人工整理过的事件。
    # 不允许把机场特点表格里的“进场天气方面/离场机场方面”等分类字段当事件输出。
    items = expand_incident_items(risks)
    excluded_prefixes = (
        "机场分类", "高原机场", "指挥特点", "地形", "气象特点", "特殊复杂程序",
        "进场天气方面", "离场天气方面", "进场机场方面", "离场机场方面",
        "进场飞行程序方面", "离场飞行程序方面", "进场环境和地形方面", "离场环境和地形方面",
        "进场ATC方面", "离场ATC方面",
    )
    cleaned: list[str] = []
    for item in items:
        text = professionalize_incident(item) if "professionalize_incident" in globals() else item
        bare = strip_terminal_punct(text)
        if not bare or bare.startswith(excluded_prefixes) or FALSE_INCIDENT_LABEL_RE.match(bare):
            continue
        if any(label in bare for label in ("缓解措施", "威胁类别", "典型威胁")):
            continue
        cleaned.append(text)

    # 只有在没有明确事件时，才从威胁里抽“事件化”的内容；仍然过滤表格字段。
    if len(cleaned) < 2:
        for item in threats:
            bare = strip_terminal_punct(item)
            if bare.startswith(excluded_prefixes) or FALSE_INCIDENT_LABEL_RE.match(bare):
                continue
            if any(word in item for word in ("曾发生", "多发", "导致", "警告", "风切变", "SINK RATE", "重着陆", "鸟击", "滑错", "跑道侵入", "复飞")):
                cleaned.append(seasonal_clean(item, month))
    return unique([x for x in cleaned if x])[:max_items]


def natural_core_item(item: str, month: int) -> str:
    text = strip_terminal_punct(seasonal_clean(item, month))
    text = re.sub(r"[（(][^）)]*(?:参考|详见|EFB|航图汇总)[^）)]*[）)]", "", text)
    text = re.sub(r"(?:请)?参考\s*(?:EFB|航图|机场特点)[^；。]*", "", text)
    text = re.sub(r"详见[^；。]*", "", text)
    replacements = [
        (r"^机场分类[:：]", "该机场为"),
        (r"^高原机场[:：]", "属于"),
        (r"^指挥特点[:：]", "管制指挥方面，"),
        (r"^地形[:：]", "地形方面，"),
        (r"^气象特点[:：]", "气象方面，"),
        (r"^道面特点[:：]", "道面方面，"),
        (r"^其他威胁[:：]", ""),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    text = text.replace("建议机组", "我们应").replace("请机组", "我们应").replace("机组注意", "我们应注意")
    text = re.sub(r"\s+", " ", text).strip("；。 ")
    return text


def core_paragraph(airport: str, items: list[str], month: int) -> str:
    cleaned = unique([natural_core_item(x, month) for x in items if natural_core_item(x, month)])[:5]
    return f"{short_airport_name(airport)}：" + "；".join(cleaned) + "。"


def compact_weather(value: str, max_len: int = 420) -> str:
    value = normalize_text(value)
    return value if len(value) <= max_len else value[:max_len].rstrip() + "……"


def weather_section(airports: list[str], icao_map: dict[str, str], timeout: int) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []
    for airport in airports:
        icao = icao_map.get(airport, "")
        result = fetch_airport_weather(icao, timeout=timeout)
        parts = []
        if result.metar:
            parts.append("METAR：" + compact_weather(result.metar))
        if result.taf:
            parts.append("TAF：" + compact_weather(result.taf))
        if parts:
            lines.append(f"{airport}（{icao or 'ICAO待确认'}）：" + "；".join(parts) + "。")
        else:
            lines.append(f"{airport}：暂未获取到有效METAR/TAF，以航前最新报文、放行资料及ATIS为准。")
        if result.error:
            warnings.append(f"{airport}天气获取提示：{result.error}")
    return lines, warnings



def compact_key(value: str) -> str:
    value = (value or "").upper()
    value = re.sub(r"\s+", "", value)
    value = value.replace("／", "/").replace("（", "(").replace("）", ")")
    value = re.sub(r"[·•，。；、:：_\-—()（）\[\]【】]", "", value)
    return value


def is_repeated_pdf_line(value: str) -> bool:
    compact = compact_key(value)
    if compact.startswith("非受控文件仅供参考"):
        return True
    if re.fullmatch(r"版本号20\d{6}", compact):
        return True
    if compact.startswith("版本号20") and "修改日期" in compact:
        return True
    if compact.startswith("修改日期20"):
        return True
    if re.fullmatch(r"\d+/\d+", compact):
        return True
    if re.fullmatch(r"第?\d+页(?:共\d+页)?", compact):
        return True
    return compact in {compact_key(line) for line in PDF_FOOTER_LINES}


def normalize_pdf_page(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            lines.append("")
            continue
        if is_repeated_pdf_line(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


@lru_cache(maxsize=2)
def extract_pdf_text(path_value: str) -> tuple[str, tuple[int, ...]]:
    if PdfReader is None:
        raise RuntimeError("pypdf 未安装，无法读取 PDF 机场手册")

    reader = PdfReader(path_value)
    if reader.is_encrypted:
        raise RuntimeError("PDF 机场手册已加密")

    extracted_pages: list[str] = []
    failed_pages: list[int] = []
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:
            failed_pages.append(page_no)
            continue
        normalized = normalize_pdf_page(raw)
        if normalized:
            extracted_pages.append(normalized)

    allowed_failures = max(3, int(len(reader.pages) * MAX_PDF_FAILED_PAGE_RATIO))
    if len(failed_pages) > allowed_failures:
        raise RuntimeError(
            f"PDF 文本提取失败页数过多：{len(failed_pages)}/{len(reader.pages)}"
        )

    text = "\n\n".join(extracted_pages)
    if len(text) < MIN_PDF_MANUAL_TEXT_CHARS:
        raise RuntimeError("PDF 提取文本异常偏短")
    return text, tuple(failed_pages)


def read_manual_text(path: Path) -> tuple[str, list[str]]:
    if path.suffix.lower() == ".pdf":
        text, failed_pages = extract_pdf_text(str(path.resolve()))
        warnings = (
            [f"PDF机场手册有{len(failed_pages)}页未能提取，已跳过异常页"]
            if failed_pages
            else []
        )
        return text, warnings
    return path.read_text(encoding="utf-8", errors="replace"), []


def manual_information_type(path: Path | None) -> str:
    if not path:
        return ""
    return "PDF" if path.suffix.lower() == ".pdf" else "TXT"


def manual_version(path: Path, text: str | None = None) -> int:
    versions = [int(x) for x in re.findall(r"(20\d{6})", path.name)]
    if text is None and path.suffix.lower() == ".txt":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:12000]
        except Exception:
            text = ""
    if text:
        versions.extend(
            int(x)
            for x in re.findall(
                r"版本号\s*[:：]?\s*(20\d{6})",
                text[:12000],
            )
        )
    return max(versions, default=0)


def find_airport_manual_candidates(knowledge_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for pattern in MANUAL_GLOB_PATTERNS:
        candidates.extend(knowledge_dir.glob(pattern))
    unique_paths = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file()))

    relevant: list[Path] = []
    for path in unique_paths:
        if path.suffix.lower() == ".pdf":
            if "机场特点" in path.name or path.name.startswith("AirDropManual"):
                relevant.append(path)
            continue
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:200000]
        except Exception:
            continue
        if "机场运行特点" not in compact_key(sample) and "机场特点" not in path.name:
            continue
        relevant.append(path)

    relevant.sort(
        key=lambda path: (
            manual_version(path),
            path.suffix.lower() == ".pdf",
            path.stat().st_mtime,
        ),
        reverse=True,
    )
    return relevant


def find_latest_airport_manual(knowledge_dir: Path) -> Path | None:
    candidates = find_airport_manual_candidates(knowledge_dir)
    return candidates[0] if candidates else None


def airport_manual_candidate_chain(knowledge_dir: Path) -> list[Path]:
    candidates = find_airport_manual_candidates(knowledge_dir)
    if not candidates:
        return []
    preferred = candidates[0]
    if preferred.suffix.lower() != ".pdf":
        return candidates
    preferred_version = manual_version(preferred)
    return [
        path
        for path in candidates
        if manual_version(path) == preferred_version
    ]


def _find_manual_header_marker(value: str) -> tuple[int, str]:
    key = compact_key(value)
    found: list[tuple[int, str]] = []
    for marker in MANUAL_HEADER_MARKERS:
        pos = key.find(compact_key(marker))
        if pos >= 0:
            found.append((pos, marker))
    return min(found, default=(-1, ""), key=lambda item: item[0])


def is_manual_airport_header(line: str) -> bool:
    """Recognize both narrative airport chapters and threat-table chapters.

    Supported examples include:
    - 上海 / 浦东 机场运行特点
    - 济州机场运行特点 JIZHOU(CJU/RKPC)
    - 大连周水子机场（DLC/ZYTL）威胁识别与缓解措施表
    - 沈阳桃仙机场（SHE/ZYTX）威胁识别及缓解措施表

    The detector remains generic and does not special-case any airport.
    """
    raw = normalize_text(line)
    key = compact_key(raw)
    pos, marker = _find_manual_header_marker(raw)
    if pos < 2 or pos > 70:
        return False
    if not 6 <= len(key) <= 180:
        return False
    if any(word in key for word in ("汇总", "目录", "有效性完善", "安全问题的意识", "请机组积极", "东北机场威胁识别表")):
        return False
    if any(mark in raw for mark in ("。", "，", "；", "：")):
        return False
    prefix = key[:pos]
    if len(prefix) > 70:
        return False
    # For narrative titles such as “上海/浦东机场运行特点”, the word
    # “机场” belongs to the marker itself. Threat-table titles, however,
    # carry “机场” in the airport-name prefix.
    if "威胁识别" in compact_key(marker) and "机场" not in prefix:
        return False
    return bool(marker)


def _header_prefix_text(header: str) -> str:
    normalized = normalize_text(header).replace("（", "(").replace("）", ")")
    marker_pos, _ = _find_manual_header_marker(normalized)
    compact_marker_pos = marker_pos
    # Work on compact form for consistent OCR spacing, then remove code pairs
    # and residual Latin text from the Chinese airport name.
    key = compact_key(normalized)
    if compact_marker_pos >= 0:
        key = key[:compact_marker_pos]
    key = re.sub(r"[A-Z0-9]{3,4}/[A-Z0-9]{3,4}", "", key)
    key = re.sub(r"[A-Z0-9]+", "", key)
    return key.strip("/")


def clean_header_airport_name(line: str) -> str:
    key = _header_prefix_text(line).replace("/", "")
    return key.removesuffix("国际机场").removesuffix("机场")


def _header_name_aliases(header: str) -> tuple[str, list[str], list[str]]:
    """Build generic strong/weak Chinese aliases from all supported headers."""
    prefix = _header_prefix_text(header)
    parts = [p for p in prefix.split("/") if p]
    combined = "".join(parts) or prefix.replace("/", "")

    strong: set[str] = {combined}
    weak: set[str] = set()
    for value in list(strong):
        for ending in ("国际机场", "机场", "国际"):
            if value.endswith(ending) and len(value) > len(ending) + 1:
                strong.add(value[: -len(ending)])

    for part in parts:
        cleaned = part.removesuffix("国际机场").removesuffix("机场").removesuffix("国际")
        if len(cleaned) >= 2 and cleaned not in strong:
            weak.add(cleaned)

    name_key = clean_header_airport_name(header) or (max(strong, key=len) if strong else combined)
    return name_key, sorted(strong, key=len, reverse=True), sorted(weak, key=len, reverse=True)

def _extract_airport_codes(probe: str) -> tuple[str, str]:
    """Extract IATA/ICAO regardless of order or bracket width."""
    normalized = probe.upper().replace("（", "(").replace("）", ")").replace("／", "/")
    pairs = re.findall(r"(?<![A-Z0-9])([A-Z0-9]{3,4})\s*/\s*([A-Z0-9]{3,4})(?![A-Z0-9])", normalized)
    for left, right in pairs:
        if len(left) == 3 and len(right) == 4:
            return left, right
        if len(left) == 4 and len(right) == 3:
            return right, left
    # Fallback for OCR output where codes are separated rather than paired.
    tokens = re.findall(r"(?<![A-Z0-9])([A-Z]{3,4})(?![A-Z0-9])", normalized)
    iata = next((x for x in tokens if len(x) == 3), "")
    icao = next((x for x in tokens if len(x) == 4 and x not in {"ONLY", "WITH"}), "")
    return iata, icao


def build_manual_index(text: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    headers = [i for i, line in enumerate(lines) if is_manual_airport_header(line)]
    sections: list[dict] = []
    for pos, start_idx in enumerate(headers):
        end_idx = headers[pos + 1] if pos + 1 < len(headers) else len(lines)
        header = lines[start_idx].strip()
        body_lines = lines[start_idx:end_idx]
        # Some international chapters put IATA/ICAO after the Chinese title;
        # others put it in the following few lines. Scan a wider but bounded
        # header area and infer code type by length, not by order.
        probe = "\n".join(body_lines[:24])
        iata, icao = _extract_airport_codes(probe)
        name_key, strong_aliases, weak_aliases = _header_name_aliases(header)
        sections.append(
            {
                "header": header,
                "section_type": "threat_table" if "威胁识别" in compact_key(header) else "narrative",
                "name_key": name_key,
                "aliases": strong_aliases + weak_aliases,
                "strong_aliases": strong_aliases,
                "weak_aliases": weak_aliases,
                "iata": iata,
                "icao": icao,
                "lines": body_lines,
            }
        )
    return sections


def _manual_match_scores(index: list[dict], airport: str, icao: str) -> list[tuple[int, dict]]:
    airport_key = compact_key(airport).replace("/", "")
    for ending in ("国际机场", "机场"):
        if airport_key.endswith(ending):
            airport_key = airport_key[: -len(ending)]
            break

    requested_icao = (icao or "").upper().strip()
    weak_frequency: dict[str, int] = {}
    for section in index:
        for alias in section.get("weak_aliases", []):
            weak_frequency[alias] = weak_frequency.get(alias, 0) + 1

    scored: list[tuple[int, dict]] = []
    for section in index:
        score = 150 if section.get("section_type") == "threat_table" else 0
        section_icao = str(section.get("icao", "")).upper()
        if requested_icao and section_icao == requested_icao:
            score += 2000
        elif requested_icao and section_icao and section_icao != requested_icao:
            # A conflicting ICAO is a strong negative signal.
            score -= 1200

        name_key = str(section.get("name_key", ""))
        if airport_key == name_key:
            score += 1000
        elif airport_key and name_key and (airport_key in name_key or name_key in airport_key):
            score += 600 + min(len(airport_key), len(name_key))

        for alias in section.get("strong_aliases", []):
            if airport_key == alias:
                score += 800
            elif len(alias) >= 3 and (alias in airport_key or airport_key in alias):
                score += 350 + min(len(alias), len(airport_key))

        for alias in section.get("weak_aliases", []):
            if weak_frequency.get(alias, 0) != 1:
                continue
            if airport_key == alias:
                score += 220
            elif len(alias) >= 3 and (alias in airport_key or airport_key in alias):
                score += 80 + min(len(alias), len(airport_key))

        if score > 0:
            scored.append((score, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def match_manual_sections(index: list[dict], airport: str, icao: str) -> list[dict]:
    """Return all high-confidence chapters for one airport.

    The manual often contains both a structured threat table and a later
    narrative airport chapter. We merge both instead of forcing one format to
    carry all information.
    """
    scored = _manual_match_scores(index, airport, icao)
    if not scored:
        return []
    best = scored[0][0]
    requested_icao = (icao or "").upper().strip()
    matches: list[dict] = []
    for score, section in scored:
        same_icao = requested_icao and str(section.get("icao", "")).upper() == requested_icao
        if score >= best - 650 and (same_icao or not requested_icao):
            matches.append(section)
        if len(matches) >= 3:
            break
    if matches or not requested_icao:
        return matches

    # An independently maintained ICAO mapping can lag behind the airport
    # manual. If the requested code has no chapter, allow only an exact,
    # unique airport-name match as a conservative fallback. Weak aliases and
    # partial names are deliberately insufficient here.
    airport_key = compact_key(airport).replace("/", "")
    for ending in ("国际机场", "机场"):
        if airport_key.endswith(ending):
            airport_key = airport_key[: -len(ending)]
            break
    name_scored = _manual_match_scores(index, airport, "")
    exact_name_matches = [
        section
        for _score, section in name_scored
        if airport_key == str(section.get("name_key", ""))
        or airport_key in set(section.get("strong_aliases", []))
    ]
    if len(exact_name_matches) == 1:
        return exact_name_matches
    return matches


def match_manual_section(index: list[dict], airport: str, icao: str) -> dict | None:
    matches = match_manual_sections(index, airport, icao)
    return matches[0] if matches else None


def is_boilerplate_line(line: str) -> bool:
    compact = compact_key(line)
    if not compact:
        return True
    if compact.startswith("非受控文件") or "FORREFERENCEONLY" in compact:
        return True
    if compact.startswith("版本号") or compact.startswith("修改日期"):
        return True
    if re.fullmatch(r"\d+/\d+", compact):
        return True
    if compact.startswith("更新日期") or compact.startswith("责任中队"):
        return True
    if compact.endswith("机场运行特点"):
        return True
    if re.fullmatch(r"[A-Z0-9/]+", compact):
        return True
    return False


def heading_kind(line: str) -> str:
    key = compact_key(line)
    if "典型不安全事件详述" in key:
        return "details"
    if "典型不安全事件" in key:
        return "typical"
    if "核心威胁" in key:
        return "core"
    if "运行特点" in key:
        return "operations"
    if "特殊运行要求" in key or "特殊要求" in key:
        return "special"
    return ""


def clean_manual_item(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(
        r"^(?:[一二三四五六七八九十]+[、.．，,:：]|[（(]?\d+[）).、，,:：]\s*)+",
        "",
        value,
    )
    value = value.strip("；;，,。 ")
    value = re.sub(r"\s+([，。；：、）])", r"\1", value)
    value = re.sub(r"([（])\s+", r"\1", value)
    if not value:
        return ""
    if len(value) > 360:
        cut = max(value.rfind("。", 0, 360), value.rfind("；", 0, 360))
        value = value[: cut + 1 if cut >= 100 else 360].rstrip("，； ") + "……"
    elif not value.endswith(("。", "！", "？", "……")):
        value += "。"
    return value


def lines_to_numbered_items(lines: list[str], max_items: int) -> list[str]:
    items: list[str] = []
    current = ""
    number_re = re.compile(r"^\s*(?:[（(]?\d+[）).、，,:：]|[一二三四五六七八九十]+[、.．，,:：])\s*")
    sub_re = re.compile(r"^\s*[（(]\d+[）)]\s*")
    for raw in lines:
        if is_boilerplate_line(raw):
            continue
        line = normalize_text(raw)
        if not line or heading_kind(line):
            continue
        if any(word in line for word in EXCLUDE_KEYWORDS):
            continue

        starts_number = bool(number_re.match(line))
        starts_sub = bool(sub_re.match(line))
        if starts_number and not starts_sub:
            if current:
                cleaned = clean_manual_item(current)
                if cleaned:
                    items.append(cleaned)
            current = number_re.sub("", line, count=1)
        else:
            if current:
                current += ("" if re.search(r"[\u4e00-\u9fff，、（(]$", current) else " ") + line
            else:
                current = sub_re.sub("", line, count=1)

        if len(items) >= max_items:
            break

    if current and len(items) < max_items:
        cleaned = clean_manual_item(current)
        if cleaned:
            items.append(cleaned)
    return unique(items)[:max_items]


OPERATION_SUBSECTION_RE = re.compile(
    r"^[（(]?[一二三四五六七八九十]+[）)]\s*"
    r"(?P<section>地面|离场|航路|进场)\s*[:：]?\s*$"
)
OPERATION_SECTION_PHASES = {
    "地面": "ground",
    "离场": "departure",
    "进场": "arrival",
}
OPERATION_PHASE_LABELS = {
    "ground": "地面",
    "departure": "离场",
    "arrival": "进场",
}


def extract_operational_section_items(
    lines: list[str],
    max_items: int,
) -> list[str]:
    """Extract facts under explicit 地面/离场/进场 manual subsections.

    The phase comes only from the source subsection heading.  This avoids
    inventing a phase from prose while making narrative operating facts
    available to the existing role-selection layer.
    """
    seen_content_heading = False
    in_operations = False
    current_phase = ""
    phase_lines: dict[str, list[str]] = {
        "ground": [],
        "departure": [],
        "arrival": [],
    }
    for raw in lines:
        kind = heading_kind(raw)
        if kind in {"typical", "core"}:
            seen_content_heading = True
        if kind == "operations" and seen_content_heading:
            in_operations = True
            current_phase = ""
            continue
        if not in_operations:
            continue
        if kind in {"details", "special"}:
            break
        subsection = OPERATION_SUBSECTION_RE.match(normalize_text(raw))
        if subsection:
            current_phase = OPERATION_SECTION_PHASES.get(
                subsection.group("section"), ""
            )
            continue
        if current_phase:
            phase_lines[current_phase].append(raw)

    items: list[str] = []
    for phase in ("ground", "departure", "arrival"):
        label = OPERATION_PHASE_LABELS[phase]
        for item in lines_to_numbered_items(phase_lines[phase], max_items):
            items.append(f"{label}：{item}")
    return unique(items)[:max_items]


TABLE_CATEGORIES = ("天气", "环境和地形", "机场", "飞行程序", "ATC")
FALSE_INCIDENT_LABEL_RE = re.compile(r"^(?:进场|离场)?(?:天气|机场|飞行程序|环境和地形|ATC)方面[，,:：]")
ACTION_PREFIXES = (
    "提前", "严格", "关注", "保持", "执行", "按照", "按", "使用", "确认", "控制", "准确",
    "听清", "防范", "仅在", "遇", "做好", "申请", "密切", "注意", "谨慎", "及时", "主动",
    "减速", "避免", "不要", "人工", "监控", "遵守", "建议", "参考", "切勿", "可提前", "应",
    "正常", "联系", "选择", "设置", "核对", "预留", "询问", "报告", "获取", "降低", "预防",
)


def _table_clean_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    structural = {
        "威胁类别", "典型威胁", "缓解措施", "离场阶段", "进场阶段",
        *(compact_key(x) for x in TABLE_CATEGORIES),
    }
    for raw in lines:
        line = normalize_text(raw)
        if not line:
            continue
        compact = compact_key(line)
        if compact in structural:
            out.append(compact)
            continue
        # The manual repeats each Chinese threat table in English. Once the
        # translation starts, stop rather than allowing it to pollute the last
        # Chinese ATC/procedure cell.
        latin_ratio = sum(ch.isascii() and ch.isalpha() for ch in line) / max(1, len(line))
        if latin_ratio > 0.45 and re.search(r"\b(?:AIRPORT|THREAT|DEPARTURE|ARRIVAL|MITIGATION)\b", line.upper()):
            break
        if is_boilerplate_line(line):
            continue
        out.append(line)
    return out


def _action_start(value: str) -> bool:
    cleaned = normalize_text(value)
    cleaned = re.sub(r"^(?:[（(]?\d+[）).、，,:：]\s*)+", "", cleaned)
    compact = compact_key(cleaned)
    return any(compact.startswith(compact_key(prefix)) for prefix in ACTION_PREFIXES)


def _split_threat_mitigation(parts: list[str]) -> tuple[str, str]:
    if len(parts) < 2:
        return (normalize_text("".join(parts)), "")
    for idx in range(1, len(parts)):
        if _action_start(parts[idx]):
            control_start = idx
            if idx > 1 and re.search(r"(?:时|期间|阶段)$", normalize_text(parts[idx - 1])):
                control_start = idx - 1
            return normalize_text("".join(parts[:control_start])), normalize_text("".join(parts[control_start:]))

    joined = normalize_text("".join(parts))
    action_pattern = "|".join(sorted((re.escape(x) for x in ACTION_PREFIXES), key=len, reverse=True))
    pattern = re.compile(rf"(?:[；。]|(?<=\d)[.、])?\s*(?:[（(]?\d+[）).、，,:：]\s*)?(?=({action_pattern}))")
    for match in pattern.finditer(joined):
        if match.start() >= max(6, len(joined) // 4):
            return joined[:match.start()].strip("；。 "), joined[match.start():].strip("；。 ")
    split = max(1, len(parts) // 2)
    return normalize_text("".join(parts[:split])), normalize_text("".join(parts[split:]))



def extract_threat_table_entries(section: dict) -> list[dict]:
    """Parse Chinese threat-identification tables into phase/category records.

    This parser is used for every airport chapter that follows the standard
    离场/进场—威胁类别—典型威胁—缓解措施 layout. It is deliberately
    generic; no airport names or runway numbers are hard-coded.
    """
    lines = _table_clean_lines(list(section.get("lines") or []))
    if not any("威胁类别" in compact_key(x) for x in lines):
        return []

    records: list[dict] = []
    phase = ""
    i = 0
    while i < len(lines):
        key = compact_key(lines[i])
        if key == "离场阶段":
            phase = "离场"
            i += 1
            continue
        if key == "进场阶段":
            phase = "进场"
            i += 1
            continue
        if key not in {compact_key(x) for x in TABLE_CATEGORIES}:
            i += 1
            continue

        category = next(x for x in TABLE_CATEGORIES if compact_key(x) == key)
        i += 1
        block: list[str] = []
        while i < len(lines):
            next_key = compact_key(lines[i])
            if next_key in {compact_key(x) for x in TABLE_CATEGORIES} or next_key in {"离场阶段", "进场阶段"}:
                break
            if next_key not in {"威胁类别", "典型威胁", "缓解措施"}:
                block.append(lines[i])
            i += 1

        block = [x for x in block if x and not heading_kind(x)]
        if not block:
            continue
        threat, mitigation = _split_threat_mitigation(block)
        threat = strip_terminal_punct(threat)
        mitigation = strip_terminal_punct(mitigation)
        if threat:
            records.append({
                "phase": phase or "运行",
                "category": category,
                "threat": threat,
                "mitigation": mitigation,
            })
    return records


def table_risk_items(records: list[dict], max_items: int) -> list[str]:
    priorities = {"天气": 0, "机场": 1, "飞行程序": 2, "环境和地形": 3, "ATC": 4}
    ordered = sorted(records, key=lambda r: (priorities.get(r["category"], 9), 0 if r["phase"] == "进场" else 1))
    result: list[str] = []
    for record in ordered:
        text = f"{record['phase']}{record['category']}方面，{record['threat']}"
        result.append(clean_manual_item(text))
    return unique(result)[:max_items]


def table_core_items(records: list[dict], max_items: int) -> list[str]:
    # Combine departure/arrival records by category so a short group-ready
    # version still covers both phases instead of listing only departure items.
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["category"], []).append(record)
    priorities = ("天气", "机场", "飞行程序", "环境和地形", "ATC")
    result: list[str] = []
    for category in priorities:
        entries = grouped.get(category, [])
        if not entries:
            continue
        fragments: list[str] = []
        controls: list[str] = []
        for entry in entries:
            threat_text = entry["threat"]
            phase = entry["phase"]
            fragments.append(threat_text if threat_text.startswith(phase) else f"{phase}{threat_text}")
            if entry.get("mitigation"):
                controls.append(entry["mitigation"])
        threat_text = "；".join(unique(fragments))
        control_text = "；".join(unique(controls))
        text = f"{category}方面，{threat_text}"
        if control_text:
            text += f"。我们应{control_text}"
        result.append(clean_manual_item(text))
    return unique(result)[:max_items]


def extract_manual_lists(section: dict, max_items: int) -> tuple[list[str], list[str]]:
    lines = list(section.get("lines") or [])
    typical_lines: list[str] = []
    core_lines: list[str] = []
    mode = ""
    for raw in lines:
        kind = heading_kind(raw)
        if kind in ("typical", "details"):
            mode = "typical"
            continue
        if kind == "core":
            mode = "core"
            continue
        if kind in ("operations", "special"):
            if mode in ("typical", "core"):
                mode = ""
            continue
        if mode == "typical":
            typical_lines.append(raw)
        elif mode == "core":
            core_lines.append(raw)

    typical = lines_to_numbered_items(typical_lines, max_items)
    core = lines_to_numbered_items(core_lines, max_items)
    operational = extract_operational_section_items(lines, max_items)
    core = unique([*core, *operational])[:max_items]

    table_records = extract_threat_table_entries(section)
    # 机场特点表格用于生成核心威胁，不能直接当“典型不安全事件”。
    # 否则会输出“进场天气方面/离场机场方面”这种字段标题。
    if not core and table_records:
        core = table_core_items(table_records, max_items)

    if not typical:
        whole_candidates: list[str] = []
        for raw in lines:
            line = normalize_text(raw)
            if is_boilerplate_line(line) or heading_kind(line):
                continue
            if any(word in line for word in EXCLUDE_KEYWORDS):
                continue
            if any(word in line for word in RISK_KEYWORDS):
                item = clean_manual_item(line)
                if item:
                    whole_candidates.append(item)
        typical = unique(whole_candidates)[:max_items]
    if not core:
        # Some narrative chapters use detailed “运行特点” subsections without
        # a standalone “核心威胁” heading. Reuse the strongest operational
        # lines rather than falling back to empty or generic placeholder text.
        core_candidates: list[str] = []
        for raw in lines:
            line = normalize_text(raw)
            if is_boilerplate_line(line) or heading_kind(line):
                continue
            if any(word in line for word in EXCLUDE_KEYWORDS):
                continue
            if any(word in line for word in RISK_KEYWORDS):
                item = clean_manual_item(line)
                if item:
                    core_candidates.append(item)
        core = sorted(unique(core_candidates), key=_core_item_score, reverse=True)[:max_items]
    return typical, core


def manual_airport_data(
    knowledge_dir: Path,
    airports: list[str],
    icao_map: dict[str, str],
    max_items: int,
) -> tuple[dict[str, dict], str, int, str, list[str]]:
    failures: list[str] = []
    for source in airport_manual_candidate_chain(knowledge_dir):
        try:
            text, source_warnings = read_manual_text(source)
            index = build_manual_index(text)
            if not index:
                raise ValueError("未识别到机场知识章节")

            result: dict[str, dict] = {}
            for airport in airports:
                sections = match_manual_sections(index, airport, icao_map.get(airport, ""))
                if not sections:
                    continue
                typical: list[str] = []
                core: list[str] = []
                for section in sections:
                    section_typical, section_core = extract_manual_lists(section, max_items)
                    typical = unique([*typical, *section_typical])[:max_items]
                    core = unique([*core, *section_core])[:max_items]
                result[airport] = {
                    "typical_incidents": typical,
                    "core_threats": core,
                    "matched_header": " + ".join(str(s.get("header", "")) for s in sections),
                    "matched_icao": next((str(s.get("icao", "")) for s in sections if s.get("icao")), ""),
                }

            if not result:
                raise ValueError("未匹配本次航班涉及机场")

            warnings = [*failures, *source_warnings]
            if failures:
                warnings.append(f"已安全回退使用机场知识源：{source.name}")
            return (
                result,
                str(source),
                manual_version(source, text),
                manual_information_type(source),
                warnings,
            )
        except Exception as exc:
            failures.append(
                f"机场知识源不可用：{source.name}：{type(exc).__name__}: {exc}"
            )

    return {}, "", 0, "", failures


def supplements_for_airport(supplements: dict, airport: str) -> tuple[dict, str]:
    airport_data = supplements.get("airports", supplements)
    for name, value in airport_data.items():
        aliases = value.get("aliases", []) if isinstance(value, dict) else []
        if name == airport or name in airport or airport in name or any(a and (a in airport or airport in a) for a in aliases):
            return value if isinstance(value, dict) else {}, name
    return {}, ""


SOURCE_HEADING_RE = re.compile(
    r"^(指挥特点|注意事项|气象特点|道面特点|其他威胁|运行特点|地面|离场|进场)"
    r"\s*[:：]?\s*"
)
SOURCE_SENTENCE_RE = re.compile(r"[^。！？!?]+[。！？!?]")
SOURCE_INCOMPLETE_END_RE = re.compile(
    r"(?:[，、：:；;]|请机|后面就|关于.+(?:进近方式|程序|速)|的|及|和|或)$"
)


def _source_clause_has_substance(value: str) -> bool:
    text = normalize_text(value)
    text = SOURCE_HEADING_RE.sub("", text)
    text = re.sub(r"^[（(]?\d+[）).、]?\s*", "", text)
    text = re.sub(r"[\s。；;，,：:（）()]+", "", text)
    return len(text) >= 4 and not SOURCE_INCOMPLETE_END_RE.search(text)


def _source_clause_identifiers(value: str) -> set[str]:
    text = normalize_text(value).upper()
    identifiers = set(re.findall(r"(?<![A-Z0-9])[A-Z]{1,5}\d{1,4}(?![A-Z0-9])", text))
    identifiers.update(re.findall(r"(?<!\d)\d{2}(?=\s*号(?:跑道)?)", text))
    return identifiers


def _source_clause_phase(value: str, heading: str) -> str:
    if heading == "地面":
        return "ground"
    if heading == "离场":
        return "departure"
    if heading == "进场":
        return "arrival"
    if heading == "气象特点":
        return "weather"
    if any(token in value for token in ("进近", "着陆", "落地", "五边", "下滑道", "盲降", "ILS")):
        return "approach"
    if any(token in value for token in ("起飞", "离场", "初始爬升")):
        return "departure"
    if any(token in value for token in ("滑行", "等待道口", "机位", "推出")):
        return "ground"
    if any(token in value for token in ("地形", "CFIT", "MSA")):
        return "terrain"
    if any(token in value for token in ("雷暴", "风切变", "大风", "结冰")):
        return "weather"
    return "unspecified"


def split_source_record_clauses(value: str) -> list[ManualFactClause]:
    """Split only complete source sentences while preserving full provenance.

    A clause inherits a preceding explicit role only when it is a complete control
    sentence or shares a concrete runway/taxiway/procedure identifier. This lets a
    mixed table record retain its departure half without treating its arrival half
    as departure content.
    """
    source_original = normalize_text(value)
    text = source_original
    heading = ""
    heading_match = SOURCE_HEADING_RE.match(text)
    if heading_match:
        heading = heading_match.group(1)
        text = text[heading_match.end() :].strip()

    numbered_pieces = re.split(r"(?=[（(]\d+[）)])", text)
    raw_clauses: list[str] = []
    broken_clauses: list[str] = []
    for piece in numbered_pieces:
        piece = re.sub(r"^[（(]\d+[）)]\s*", "", piece).strip()
        if not piece:
            continue
        sentence_matches = list(SOURCE_SENTENCE_RE.finditer(piece))
        complete = [match.group(0).strip() for match in sentence_matches]
        remainder = (
            piece[sentence_matches[-1].end() :].strip(" ；")
            if sentence_matches
            else ""
        )
        if complete:
            raw_clauses.extend(complete)
            if remainder:
                if _source_clause_has_substance(remainder):
                    raw_clauses.append(strip_terminal_punct(remainder) + "。")
                else:
                    broken_clauses.append(remainder)
        elif _source_clause_has_substance(piece):
            raw_clauses.append(strip_terminal_punct(piece) + "。")
        else:
            broken_clauses.append(piece)

    independently_supported: list[str] = []
    for clause in raw_clauses:
        pdc_match = re.match(r"^(?P<context>.+?)，(?P<pdc>有PDC)[。.]$", clause)
        if pdc_match and _source_clause_has_substance(pdc_match.group("context")):
            independently_supported.extend(
                [
                    strip_terminal_punct(pdc_match.group("context")) + "。",
                    pdc_match.group("pdc") + "。",
                ]
            )
        else:
            independently_supported.append(clause)

    clauses: list[tuple[str, str, tuple[str, ...]]] = []
    previous_phase = ""
    previous_roles: tuple[str, ...] = ()
    previous_identifiers: set[str] = set()
    for text_clause in independently_supported:
        phase = _source_clause_phase(text_clause, heading)
        roles = explicit_role_scope(text_clause, phase)
        identifiers = _source_clause_identifiers(text_clause)
        can_inherit = bool(
            previous_roles
            and (
                (identifiers and previous_identifiers.intersection(identifiers))
                or re.match(
                    r"^(?:机组|建议|注意|应|需|必须|不得|严禁|未经|可以|同时|随后|然后)",
                    text_clause,
                )
            )
        )
        if not roles and can_inherit:
            roles = previous_roles
            if phase == "unspecified":
                phase = previous_phase
        clauses.append((text_clause, phase, roles))
        if roles:
            previous_roles = roles
            previous_phase = phase
        if identifiers:
            previous_identifiers.update(identifiers)

    output: list[ManualFactClause] = []
    for index, (text_clause, phase, roles) in enumerate(clauses):
        excluded = [
            clause
            for other_index, (clause, _, _) in enumerate(clauses)
            if other_index != index
        ]
        reasons = ["同一来源记录中的其他完整运行子句" for _ in excluded]
        excluded.extend(broken_clauses)
        reasons.extend("broken_or_incomplete_source" for _ in broken_clauses)
        output.append(
            ManualFactClause(
                text=text_clause,
                heading=heading,
                phase=phase,
                role_scope=roles,
                source_original_text=source_original,
                excluded_sibling_clauses=tuple(excluded),
                excluded_sibling_reasons=tuple(reasons),
            )
        )
    return output


def split_manual_fact_item(value: str) -> list[tuple[str, str, str]]:
    return [
        (clause.text, clause.heading, clause.phase)
        for clause in split_source_record_clauses(value)
    ]


def explicit_role_scope(text: str, phase: str) -> tuple[str, ...]:
    """Derive role scope only from an explicit source phase or both-role phrase."""
    compact = compact_key(text)
    if any(
        marker in compact
        for marker in ("进/离场", "进、离场", "进离场", "进场和离场", "进场及离场")
    ):
        return ("departure", "arrival")
    if phase in {"departure", "initial_climb", "clearance"}:
        return ("departure",)
    if phase in {"arrival", "approach", "landing", "landing_ground"}:
        return ("arrival",)
    if phase in {"weather", "terrain", "navigation", "special", "unspecified"}:
        has_departure = any(
            marker in compact for marker in ("起飞", "离场", "初始爬升")
        )
        has_arrival = any(
            marker in compact
            for marker in ("进场", "进近", "着陆", "落地", "五边", "下滑道")
        )
        if has_departure != has_arrival:
            return ("departure",) if has_departure else ("arrival",)
    if phase == "ground":
        departure_markers = (
            "PDC",
            "放行",
            "推出",
            "开车",
            "起飞前",
            "起飞地面指挥",
            "甩冰",
            "除/防冰",
        )
        arrival_markers = (
            "落地后",
            "脱离跑道",
            "滑入",
            "进位",
            "泊位引导",
            "ADGS",
        )
        roles: list[str] = []
        if any(marker.upper() in compact.upper() for marker in departure_markers):
            roles.append("departure")
        if any(marker.upper() in compact.upper() for marker in arrival_markers):
            roles.append("arrival")
        return tuple(roles)
    return ()


def operation_subsection_importance(text: str) -> int:
    """Keep narrative operation subsections as conservative gap-fill facts."""
    compact = compact_key(text)
    if compact.startswith(("机场标高", "现场/签派频率", "常用程序")):
        return 25
    if compact.startswith("除/防冰能力"):
        return 30
    return 55


def airport_risks(
    repo: Path,
    airports: list[str],
    icao_map: dict[str, str],
    max_items: int,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[dict[str, object]]],
    list[str],
    str,
    int,
    str,
]:
    supplements = load_json(repo / "config" / "airport_supplements.json", {}) or {}
    manual_data, manual_source, manual_ver, manual_type, source_warnings = manual_airport_data(
        repo / "knowledge", airports, icao_map, max_items=max_items
    )

    risks: dict[str, list[str]] = {}
    threats: dict[str, list[str]] = {}
    source_records: dict[str, list[dict[str, object]]] = {}
    warnings: list[str] = list(source_warnings)

    for airport in airports:
        supplement, matched_name = supplements_for_airport(supplements, airport)
        manual = manual_data.get(airport, {})

        manual_risks = list(manual.get("typical_incidents") or [])
        manual_threats = list(manual.get("core_threats") or [])
        structured_risks = list(supplement.get("typical_incidents") or [])
        structured_threats = list(supplement.get("core_threats") or [])
        manual_section = str(manual.get("matched_header") or airport)
        records: list[dict[str, object]] = []

        def add_records(
            items: list[str],
            *,
            source_file: str,
            source: str,
            source_page: str,
            source_heading: str,
            source_section: str,
            category: str,
        ) -> None:
            for item in items:
                source_original = normalize_text(item)
                source_record_id = (
                    f"{canonical_airport_name(airport)}:{category}:"
                    f"{hashlib.sha256(source_original.encode('utf-8')).hexdigest()[:16]}"
                )
                split_items = (
                    [
                        ManualFactClause(
                            text=strip_terminal_punct(item) + "。",
                            heading="",
                            phase="incident",
                            role_scope=(),
                            source_original_text=source_original,
                        )
                    ]
                    if category == "typical"
                    else split_source_record_clauses(item)
                )
                if not split_items:
                    records.append(
                        {
                            "airport": canonical_airport_name(airport),
                            "source_file": source_file,
                            "source": source,
                            "source_page": source_page,
                            "source_heading": source_heading,
                            "source_section": source_section,
                            "operational_phase": "unspecified",
                            "role_scope": (),
                            "operation_subsection": False,
                            "importance": 0,
                            "airport_specific": True,
                            "category": category,
                            "text_zh": "",
                            "text_en": "",
                            "source_original_text": source_original,
                            "source_record_id": source_record_id,
                            "pre_excluded_reason": "清洗后无实质运行内容",
                        }
                    )
                    continue
                for clause in split_items:
                    text_zh = clause.text
                    item_heading = clause.heading
                    phase = clause.phase
                    operation_subsection = item_heading in OPERATION_SECTION_PHASES
                    records.append(
                        {
                            "airport": canonical_airport_name(airport),
                            "source_file": source_file,
                            "source": source,
                            "source_page": source_page,
                            "source_heading": source_heading,
                            "source_section": source_section
                            + (f"／{item_heading}" if item_heading else ""),
                            "operational_phase": phase,
                            "role_scope": clause.role_scope,
                            "operation_subsection": operation_subsection,
                            "importance": (
                                operation_subsection_importance(text_zh)
                                if operation_subsection
                                else 50
                            ),
                            "airport_specific": True,
                            "category": category,
                            "text_zh": text_zh,
                            "text_en": "",
                            "source_original_text": clause.source_original_text,
                            "source_record_id": source_record_id,
                            "excluded_source_clauses": clause.excluded_sibling_clauses,
                            "exclusion_reasons": clause.excluded_sibling_reasons,
                        }
                    )

        add_records(
            manual_risks,
            source_file=(
                str(Path(manual_source).resolve().relative_to(repo.resolve()))
                if manual_source
                and Path(manual_source).resolve().is_relative_to(repo.resolve())
                else str(manual_source)
            ),
            source=manual_type or "PDF",
            source_page=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_page", "N/A"),
            source_heading=manual_section,
            source_section=f"{manual_section}／典型不安全事件",
            category="typical",
        )
        add_records(
            manual_threats,
            source_file=(
                str(Path(manual_source).resolve().relative_to(repo.resolve()))
                if manual_source
                and Path(manual_source).resolve().is_relative_to(repo.resolve())
                else str(manual_source)
            ),
            source=manual_type or "PDF",
            source_page=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_page", "N/A"),
            source_heading=manual_section,
            source_section=f"{manual_section}／核心威胁与运行特点",
            category="core",
        )
        add_records(
            structured_risks,
            source_file=SUPPLEMENT_FILE,
            source="supplement",
            source_page="N/A",
            source_heading=matched_name or airport,
            source_section=f"airport_supplements.json／{matched_name or airport}／typical_incidents",
            category="typical",
        )
        add_records(
            structured_threats,
            source_file=SUPPLEMENT_FILE,
            source="supplement",
            source_page="N/A",
            source_heading=matched_name or airport,
            source_section=f"airport_supplements.json／{matched_name or airport}／core_threats",
            category="core",
        )
        add_records(
            list(CURATED_TYPICAL_INCIDENTS.get(canonical_airport_name(airport), [])),
            source_file=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_file", "crew_agents/flight_prep_agent.py"),
            source="CURATED",
            source_page=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_page", "N/A"),
            source_heading=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_heading", f"{canonical_airport_name(airport)}人工精选"),
            source_section=f"{canonical_airport_name(airport)}人工精选／典型不安全事件",
            category="typical",
        )
        add_records(
            list(CURATED_CORE_THREATS.get(canonical_airport_name(airport), [])),
            source_file=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_file", "crew_agents/flight_prep_agent.py"),
            source="CURATED",
            source_page=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_page", "N/A"),
            source_heading=AIRPORT_SOURCE_LOCATIONS.get(
                canonical_airport_name(airport), {}
            ).get("source_heading", f"{canonical_airport_name(airport)}人工精选"),
            source_section=f"{canonical_airport_name(airport)}人工精选／核心威胁",
            category="core",
        )
        source_records[airport] = records

        # The latest airport manual is authoritative for airport-specific content.
        # Supplements only fill gaps; they must not hide richer manual chapters with
        # two generic legacy sentences. Curated airport-specific wording remains
        # available through CURATED_TYPICAL_INCIDENTS and dedicated core builders.
        merged_risks = unique([*manual_risks, *structured_risks])
        merged_risks = merged_risks[:max_items]

        merged_threats = unique([*manual_threats, *structured_threats])[:max_items]

        if not merged_risks:
            warnings.append(f"{airport}未在最新机场特点或补充知识库中找到典型风险")
        if not merged_threats:
            warnings.append(f"{airport}未在最新机场特点或补充知识库中找到核心威胁")

        risks[airport] = merged_risks
        threats[airport] = merged_threats

        if manual:
            warnings.append(
                f"{airport}匹配最新机场特点章节：{manual.get('matched_header', '')}"
                + (f"（{manual.get('matched_icao')}）" if manual.get("matched_icao") else "")
            )
        elif matched_name:
            warnings.append(f"{airport}未匹配手册章节，使用补充知识库：{matched_name}")

    return (
        risks,
        threats,
        source_records,
        warnings,
        manual_source,
        manual_ver,
        manual_type,
    )


def global_threats(operational_focus: dict, month: int) -> list[str]:
    items: list[str] = []
    if 4 <= month <= 10:
        items.extend((operational_focus.get("thunderstorm_avoidance") or [])[:4])
    items.extend((operational_focus.get("stabilized_approach") or [])[:3])
    items.extend((operational_focus.get("energy_and_configuration") or [])[:2])
    items.extend((operational_focus.get("ground_operations") or [])[:2])
    items.extend((operational_focus.get("crm_and_fatigue") or [])[:2])
    return unique(items)



def canonical_airport_name(airport: str) -> str:
    return normalize_ics_airport_name(airport)


def is_airport(airport: str, target_name: str) -> bool:
    return canonical_airport_name(airport) == target_name


def compact_flight_numbers(flights: list[CalendarEvent]) -> str:
    numbers = [e.flight_number for e in flights if e.flight_number]
    if not numbers:
        return ""
    first = numbers[0]
    parts = [first]
    prefix_match = re.match(r"^([A-Z0-9]*[A-Z])(\d.*)$", first)
    prefix = prefix_match.group(1) if prefix_match else ""
    for number in numbers[1:]:
        if prefix and number.startswith(prefix):
            parts.append(number[len(prefix):])
        else:
            parts.append(number)
    return "/".join(parts)


def route_chain_text(flights: list[CalendarEvent]) -> str:
    chain: list[str] = []
    for event in flights:
        dep, arr = event.route
        if dep and (not chain or chain[-1] != dep):
            chain.append(dep)
        if arr and (not chain or chain[-1] != arr):
            chain.append(arr)
    return "—".join(short_airport_name(x) for x in chain)


def flight_overview_text(flights: list[CalendarEvent], target: date) -> str:
    number_text = compact_flight_numbers(flights)
    route_text = route_chain_text(flights)
    tomorrow = (now_beijing() + timedelta(days=1)).date()
    if target == tomorrow:
        prefix = "明日航班为"
    else:
        prefix = f"{target.month}月{target.day}日航班为"
    details = "，".join(x for x in (number_text, route_text) if x)
    return prefix + details + "。" if details else ""


def full_flight_numbers(flights: list[CalendarEvent]) -> str:
    return "/".join(unique([e.flight_number for e in flights if e.flight_number]))


def route_duty_text(flights: list[CalendarEvent]) -> str:
    routes = [(e.route[0], e.route[1]) for e in flights if e.route[0] and e.route[1]]
    if not routes:
        return ""
    segments = [f"{dep}至{arr}" for dep, arr in routes]
    if len(routes) == 1:
        return segments[0]

    prior_airports = {airport for dep, arr in routes[:-1] for airport in (dep, arr)}
    last_dep, last_arr = routes[-1]
    last_text = f"{last_dep}返回{last_arr}" if last_arr in prior_airports else f"{last_dep}至{last_arr}"
    if len(routes) == 2:
        return segments[0] + "，再由" + last_text
    return "、".join(segments[:-1]) + "，再由" + last_text


def group_personal_intro(profile: dict, records: list[dict]) -> str:
    name = profile.get("name", "")
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    parts = [
        f"我是来自{unit}的{role}{name}"
        if name
        else f"我是来自{unit}的{role}".strip()
    ]
    if profile.get("technical_level"):
        parts.append(f"目前技术级别{profile['technical_level']}")
    if profile.get("promotion_date"):
        parts.append(
            f"晋级日期{format_profile_date_cn(profile['promotion_date'])}"
        )
    if profile.get("stage_hours") is not None:
        parts.append(f"本阶段经历时间{profile['stage_hours']}小时")
    if profile.get("stage_landings") is not None:
        parts.append(f"起落{profile['stage_landings']}个")
    if profile.get("landings_90_days") is not None:
        parts.append(f"近90天起落{profile['landings_90_days']}个")
    if profile.get("duty_day"):
        parts.append(f"明日为本人本次值勤期第{profile['duty_day']}天")

    for record in records:
        airport = airport_with_suffix(record.get("airport", ""))
        if airport:
            status = "已运行过" if record.get("within") else "未运行过"
            parts.append(f"近3个月{status}{airport}")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        date_text = format_date_cn(last.get("date", "")) if last.get("date") else ""
        parts.append(
            f"上一次实际操纵落地为{date_text}"
            f"{airport_with_suffix(last['airport'])}"
        )
    return "，".join(p for p in parts if p) + "。"


def english_airport_name(airport: str) -> str:
    canonical = canonical_airport_name(airport)
    return AIRPORT_ENGLISH_NAMES.get(canonical, short_airport_name(airport))


def format_profile_date_en(value: str) -> str:
    match = re.fullmatch(r"\s*(\d{1,2})月(\d{1,2})日\s*", value or "")
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        return date(2000, month, day).strftime("%B %-d") if sys.platform != "win32" else date(2000, month, day).strftime("%B %#d")
    try:
        parsed = date.fromisoformat(value)
        return parsed.strftime("%B %-d") if sys.platform != "win32" else parsed.strftime("%B %#d")
    except Exception:
        return value


def english_personal_intro(profile: dict, records: list[dict]) -> str:
    name = PILOT_ENGLISH_NAMES.get(profile.get("name", ""), profile.get("name", ""))
    unit = profile.get("unit", "")
    role = profile.get("role", "")
    unit_en = "Flight Squadron 15" if unit == "飞行十五中队" else unit
    role_en = "First Officer" if role == "副驾驶" else role
    sentences = [f"I am {name}, a {role_en} in {unit_en}.".replace("..", ".")]

    qualification: list[str] = []
    if profile.get("technical_level"):
        qualification.append(f"my current technical level is {profile['technical_level']}")
    if profile.get("promotion_date"):
        qualification.append(
            f"my promotion date is {format_profile_date_en(profile['promotion_date'])}"
        )
    if qualification:
        first_qualification = qualification[0][0].upper() + qualification[0][1:]
        sentences.append(first_qualification + (
            ", and " + qualification[1] if len(qualification) > 1 else ""
        ) + ".")

    stage: list[str] = []
    if profile.get("stage_hours") is not None:
        stage.append(f"{profile['stage_hours']} hours")
    if profile.get("stage_landings") is not None:
        stage.append(f"{profile['stage_landings']} takeoffs and landings")
    if stage:
        sentences.append(
            "In this qualification stage, I have " + " and ".join(stage) + "."
        )

    recent: list[str] = []
    if profile.get("landings_90_days") is not None:
        recent.append(
            f"{profile['landings_90_days']} landings in the last 90 days"
        )
    if recent:
        recent_text = "I have completed " + " and ".join(recent)
        sentences.append(recent_text + ".")
    if profile.get("duty_day"):
        sentences.append(f"This is day {profile['duty_day']} of my current duty period.")

    operated = [english_airport_name(record["airport"]) for record in records if record.get("within")]
    pending = [english_airport_name(record["airport"]) for record in records if not record.get("within")]
    if operated:
        if len(operated) == 2:
            sentences.append(
                "I have operated at both "
                + operated[0]
                + " and "
                + operated[1]
                + " within the past three months."
            )
        else:
            sentences.append(
                "Within the past three months, I have operated at "
                + ", ".join(operated[:-1])
                + (", and " if len(operated) > 2 else "")
                + operated[-1]
                + "."
            )
    if pending:
        sentences.append(
            "Within the past three months, I have not operated at "
            + " or ".join(pending)
            + "."
        )

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        last_text = (
            f"My most recent landing as PF was at "
            f"{english_airport_name(last['airport'])} Airport"
        )
        if last.get("date"):
            last_text += f" on {format_profile_date_en(last['date'])}"
        sentences.append(last_text + ".")
    return " ".join(sentence for sentence in sentences if sentence).strip()


FEEDBACK_ENGLISH_TRANSLATIONS = {
    "30尺以下带杆量欠一点；着陆后快速脱离道口前及时减速至30节以下": (
        "below 30 ft I should use slightly more aft-stick input and, after landing, decelerate "
        "below 30 kt before entering the rapid-exit taxiway"
    ),
    "增加SOP熟练度，标准喊话声音大一些": (
        "I should improve SOP proficiency and make standard callouts more audible"
    ),
    "五边速度180时注意形态二，入口前关注飞机状态": (
        "at 180 kt on final I should monitor Config 2 and the aircraft state before the threshold"
    ),
    "RNP进近五边速度180节时注意形态二，入口前关注飞机状态": (
        "at 180 kt on final during an RNP approach I should monitor Config 2 and the aircraft state before the threshold"
    ),
}


def english_feedback_item(value: str) -> str:
    source = strip_terminal_punct(value)
    translated = FEEDBACK_ENGLISH_TRANSLATIONS.get(source)
    if translated:
        return translated
    if source and re.search(r"[\u4e00-\u9fff]", source):
        raise ValueError(f"缺少近期讲评英文受控表达：{source}")
    return source


def feedback_text_en(profile: dict) -> str:
    feedback = profile.get("recent_feedback") or {}
    parts: list[str] = []
    pf = feedback.get("PF")
    if pf:
        parts.append(
            f"as PF, the instructor noted that {english_feedback_item(pf)}"
        )
    if feedback.get("PM"):
        parts.append(
            f"as PM, the captain noted that {english_feedback_item(feedback['PM'])}"
        )
    text = "Latest PF/PM feedback: " + "; ".join(parts)
    return text.rstrip("; ") + "." if parts else ""



    operated = [r['airport'] + ("机场" if not r['airport'].endswith("机场") else "") for r in records if r.get("within")]
    pending = [r['airport'] + ("机场" if not r['airport'].endswith("机场") else "") for r in records if not r.get("within")]
    if operated:
        parts.append("近三个月已运行" + "、".join(operated))
    if pending:
        parts.append("、".join(pending) + "近3个月运行情况待确认")

    last = profile.get("last_operated_landing") or {}
    if last.get("airport"):
        last_text = f"上次操纵落地的机场为{last['airport']}"
        if last.get("date"):
            last_text += format_date_cn(last["date"])
        parts.append(last_text)
    return "，".join(p for p in parts if p) + "。"


def group_airport_title(airport: str) -> str:
    return airport if airport.endswith("机场") else airport + "机场"


GROUP_CONCEPTS = (
    {
        "name": "military",
        "keywords": ("军航", "空军活动", "军方活动", "训练空域"),
        "focus": "军航活动和非标准指挥",
        "typical": "周边军航或训练活动可能导致进离场程序、复飞高度及管制指令临时变化。",
        "core": "军航或训练活动期间，我们应听清并完整复诵指令，及时核对MCDU、气压基准、复飞高度和后续航迹；指令与计划不一致时完成补充简令，不确定时立即向ATC证实。",
        "priority": 94,
    },
    {
        "name": "approach_energy",
        "keywords": ("剖面高", "下降较晚", "大下降率", "不稳定进近", "高距比", "构型建立偏晚", "超速"),
        "focus": "进近能量和稳定进近",
        "typical": "进近阶段可能因下降指挥偏晚或剖面偏高出现超速、构型建立偏晚和不稳定进近。",
        "core": "进近前应提前完成下降、减速和构型计划，收到直飞、雷达引导或五边内切指令后重新评估剩余距离和高距比；无法在规定高度达到稳定进近标准时应果断复飞。",
        "priority": 95,
    },
    {
        "name": "ground",
        "keywords": ("不停航施工", "滑错", "等待线", "跑道侵入", "未经许可推出", "Route1/2", "滑行路线转弯多", "无标识", "引导车"),
        "focus": "复杂地面运行",
        "typical": "地面滑行路线、施工区域或等待位置识别复杂，存在滑错路线和跑道侵入风险。",
        "core": "推出和滑行前应完整确认许可、路线、等待位置及跑道入口，结合机场图、标志、灯光和外部目视持续交叉检查；位置不明或指令存在疑问时应立即停住并向管制证实。",
        "priority": 92,
    },
    {
        "name": "wind",
        "keywords": ("风切变", "乱流", "大风", "侧风", "阵风"),
        "focus": "大风乱流和稳定进近",
        "typical": "大风、乱流或风切变可能造成速度波动、下降率增大和着陆状态不稳定。",
        "core": "航前应核对平均风、阵风和侧风分量，进近阶段持续监控速度趋势、下降率和姿态；出现风切变警告、低高度大幅修正或状态不稳定时，严格按程序处置并及时复飞。",
        "priority": 96,
    },
    {
        "name": "highland",
        "keywords": ("一般高原", "高原机场", "高原高温", "发动机启动悬挂", "超轮速"),
        "focus": "高原高温和性能管理",
        "typical": "高原高温条件下起飞性能、发动机启动、抬轮时机及超轮速风险增加。",
        "core": "高原高温运行应复核起飞性能、组件/引气构型和发动机启动状态；起飞滑跑时PM准确报出Vr，PF及时柔和抬轮，出现性能不满足、启动异常或顺风超限时不得勉强起飞。",
        "priority": 99,
    },
    {
        "name": "terrain",
        "keywords": ("复杂地形", "超障裕度", "爬升梯度", "严禁北偏", "航坞山", "最低安全高度", "地形高"),
        "focus": "地形及程序限制",
        "typical": "机场周边地形或超障裕度限制明显，偏离程序、低高度直飞或天气绕飞可能增加地形风险。",
        "core": "我们应严格保持公布航迹、高度和爬升梯度，持续监控地形显示、MSA和导航精度；接受直飞、雷达引导或低高度绕飞前先确认地形间隔，无法保证安全裕度时及时向ATC提出。",
        "priority": 86,
    },
    {
        "name": "procedure_change",
        "keywords": ("进离场方式经常改变", "跑道、进离场方式经常改变", "航路断点", "更改进场航路", "复飞高度可能与航图不一致", "跑道变化", "程序变化"),
        "focus": "程序变化和交叉检查",
        "typical": "跑道、进离场方式或走廊口可能临时变化，容易出现程序选择错误、航路断点或复飞高度理解不一致。",
        "core": "收到跑道、进离场方式或航路变化后，应及时修改MCDU并由PF、PM对照航图交叉检查过渡段、断点、高度速度限制和复飞程序，完成补充简令后再继续执行。",
        "priority": 84,
    },
    {
        "name": "ils",
        "keywords": ("双截获", "高截获", "自主建立盲降", "截获盲降", "假信号", "航向道不稳定", "下滑道"),
        "focus": "盲降截获和进近能量",
        "typical": "自主建立盲降、较高高度截获或导航信号异常时，存在双截获、假信号和航向道不稳定风险。",
        "core": "建立盲降前应确认飞机位置、截获角、高度和剩余距离，持续监控LOC/GS、FMA、下降率及速度；出现假信号、双截获或航向道不稳定时按程序处置，不能满足稳定进近要求时复飞。",
        "priority": 82,
    },
    {
        "name": "nav_interference",
        "keywords": ("虚假 EGPWS", "虚假EGPWS", "信号干扰", "GPS PRIMARY", "GPS干扰", "导航干扰"),
        "focus": "导航干扰和告警处置",
        "typical": "机场周边可能存在导航信号干扰或虚假EGPWS告警，影响位置判断和自动飞行监控。",
        "core": "出现GPS异常或EGPWS警告时，应结合实际位置、航迹、高度、目视条件和其他导航源判断，严格执行相应程序并及时向ATC报告，不得凭经验简单忽略警告。",
        "priority": 80,
    },
    {
        "name": "pressure",
        "keywords": ("气压基准", "QFE", "场压", "标准气压高度"),
        "focus": "气压基准和高度交叉检查",
        "typical": "高度指令或QNH/QFE转换过程中存在气压基准设置错误和穿越许可高度风险。",
        "core": "改变高度或切换QNH/QFE时，PF、PM应明确气压基准并完成高度表、FMA和MCDU交叉检查，标准喊话清晰完整；存在疑问时立即向ATC证实。",
        "priority": 78,
    },
    {
        "name": "visual_illusion",
        "keywords": ("视觉错觉", "灯光致视觉错觉", "入口内移", "跑道入口内移"),
        "focus": "跑道识别和视觉错觉",
        "typical": "跑道入口、道面或灯光环境可能造成视觉错觉，增加接地点判断和跑道识别风险。",
        "core": "进近着陆阶段应结合仪表、PAPI、跑道标志和灯光综合判断，不以单一目视感觉修正航迹；出现接地点过远、下降率异常或跑道识别不清时及时复飞。",
        "priority": 76,
    },
    {
        "name": "tcas",
        "keywords": ("TCAS", "TA/RA", "邻近航空器"),
        "focus": "TCAS冲突和升降率控制",
        "typical": "进离场航流交叉或较大升降率可能增加TCAS告警风险。",
        "core": "接近目标高度最后2000英尺存在邻近航空器时，应合理控制升降率并持续监控冲突趋势；发生TA/RA时严格按照现行程序执行。",
        "priority": 70,
    },
    {
        "name": "bird",
        "keywords": ("鸟击", "鸟情", "鸟类活动"),
        "focus": "鸟击风险",
        "typical": "机场及周边鸟类活动可能对低高度起飞、进近和着陆造成鸟击风险。",
        "core": "起飞和进近阶段应关注ATIS、ATC及机场鸟情通报，加强外部观察；发现鸟群或发生鸟击后，根据飞机状态严格执行程序并及时报告。",
        "priority": 68,
    },
)

CONCEPT_ENGLISH = {
    "military": (
        "Military or training activity can cause temporary changes to arrival, departure, missed-approach, or ATC instructions.",
        "During military or training activity, we must hear and fully read back each clearance and cross-check the MCDU, pressure reference, missed-approach altitude, and onward track; confirm any inconsistency with ATC.",
    ),
    "approach_energy": (
        "Late descent or a high profile can lead to overspeed, delayed configuration, and an unstable approach.",
        "We must plan descent, deceleration, and configuration early. After a direct clearance, radar vector, or shortened final, reassess remaining distance and energy and go around if stabilization criteria cannot be met.",
    ),
    "ground": (
        "Complex taxi routes, work areas, or holding positions can create wrong-turn and runway-incursion risks.",
        "Before pushback and taxi, we must confirm the clearance, route, holding position, and runway entry and continuously cross-check charts, signs, lights, and outside visual cues; stop and confirm with ATC whenever position or clearance is uncertain.",
    ),
    "wind": (
        "Strong wind, turbulence, or windshear can cause speed fluctuation, high descent rate, and an unstable landing condition.",
        "We must verify mean wind, gust, and crosswind components and monitor speed trend, descent rate, and attitude; apply the prescribed procedure and go around for a windshear warning or an unstable low-altitude condition.",
    ),
    "highland": (
        "High-and-hot conditions reduce takeoff performance margin and increase engine-start and tire-overspeed risks.",
        "We must verify takeoff performance, bleed configuration, and engine-start condition. The PM must call rotation speed accurately and the PF must rotate normally; do not depart with inadequate performance or an abnormal start.",
    ),
    "terrain": (
        "Surrounding terrain or obstacle-clearance limits make deviations, low-altitude directs, and weather avoidance more critical.",
        "We must remain on the published track, altitude, and climb gradient and monitor terrain, MSA, and navigation accuracy; before accepting a direct clearance, radar vector, or low-altitude deviation, confirm terrain clearance.",
    ),
    "procedure_change": (
        "Runway, arrival, departure, or routing changes can produce a wrong procedure, route discontinuity, or misunderstood missed-approach altitude.",
        "After any runway, procedure, or routing change, we must update the MCDU and cross-check the transition, discontinuities, altitude and speed constraints, and missed approach before continuing.",
    ),
    "ils": (
        "An ILS intercept from an unsuitable position or altitude can produce false capture or an unstable localizer and glideslope.",
        "Before intercept, we must verify position, intercept angle, altitude, and distance and monitor LOC/GS, FMA, descent rate, and speed; apply the procedure for false or unstable capture and go around if necessary.",
    ),
    "nav_interference": (
        "Navigation interference or a false EGPWS alert can affect position awareness and automated-flight monitoring.",
        "After GPS or EGPWS anomalies, we must cross-check position, track, altitude, visual conditions, and other navigation sources, apply the applicable procedure, and report promptly to ATC.",
    ),
    "pressure": (
        "An incorrect pressure reference during QNH/QFE or altitude changes can lead to a level deviation.",
        "When changing level or pressure reference, we must state the reference and cross-check altimeters, FMA, and MCDU with clear standard callouts; confirm any uncertainty with ATC.",
    ),
    "visual_illusion": (
        "Runway threshold, surface, or lighting conditions can create a visual illusion and affect touchdown-point judgement.",
        "During approach and landing, we must use instruments, PAPI, runway markings, and lighting together rather than a single visual impression; go around for a long touchdown, abnormal descent rate, or uncertain runway identification.",
    ),
    "tcas": (
        "Crossing traffic or a high vertical rate in terminal airspace can increase the likelihood of a TCAS alert.",
        "Within the last 2000 ft before a target altitude, we must manage vertical rate when nearby traffic exists and monitor the conflict trend; comply strictly with the current TA/RA procedure.",
    ),
    "bird": (
        "Bird activity around the airport can create a low-altitude bird-strike risk during departure, approach, and landing.",
        "We must monitor ATIS, ATC, and airport bird advisories and maintain an external scan at low altitude; after a bird sighting or strike, apply the procedure appropriate to the aircraft condition and report promptly.",
    ),
}

def detected_group_concepts(source: str) -> list[dict]:
    text = source or ""
    result = [rule for rule in GROUP_CONCEPTS if any(keyword in text for keyword in rule["keywords"])]
    return sorted(result, key=lambda rule: int(rule["priority"]), reverse=True)


def focus_label(source: str) -> str:
    return "、".join(rule["focus"] for rule in detected_group_concepts(source)[:2])


def group_risk_overview(
    flights: list[CalendarEvent],
    target: date,
    airports: list[str],
    risks: dict[str, list[str]],
    threats: dict[str, list[str]],
) -> str:
    numbers = full_flight_numbers(flights)
    route_text = route_duty_text(flights)
    lead = "本次航班"
    if numbers:
        lead += f"为{numbers}"
    if route_text:
        lead += f"，{route_text}"
    lead += "。"

    focus_parts: list[str] = []
    for airport in airports:
        source_items = [*(risks.get(airport) or []), *(threats.get(airport) or [])]
        label = focus_label(" ".join(source_items))
        specifics = _source_specific_clauses(source_items)
        short = short_airport_name(airport)
        if label and specifics:
            focus_parts.append(f"{short}重点关注{label}，尤其是{specifics[0]}")
        elif label:
            focus_parts.append(f"{short}重点关注{label}")
        elif specifics:
            focus_parts.append(f"{short}重点关注{specifics[0]}")

    if 4 <= target.month <= 10:
        focus_parts.insert(0, "当前季节注意雷雨、雷击、颠簸、风切变、湿跑道及绕飞等待对油量的影响")
    if len(flights) >= 3:
        focus_parts.append("连续航段注意疲劳累积，过站不能沿用上一段结论")

    if focus_parts:
        return lead + "；".join(unique(focus_parts)[:6]) + "。"
    return lead + "天气、通告、跑道、程序和油量以航前最新TAF/METAR、PIB及放行资料为准。"



    focus_parts: list[str] = []
    for airport in airports:
        source = " ".join([*(risks.get(airport) or []), *(threats.get(airport) or [])])
        label = focus_label(source)
        if label:
            focus_parts.append(f"{airport}需关注{label}")
    if 4 <= target.month <= 10:
        focus_parts.insert(0, "当前季节需重点关注雷雨绕飞、低空风切变和湿跑道")
    if len(flights) >= 3:
        focus_parts.append("连续运行需防范末段疲劳和监控质量下降")

    tail = "天气以航前最新TAF/METAR、PIB及放行资料为准"
    if focus_parts:
        tail += "；" + "，".join(unique(focus_parts)[:5])
    return lead + tail + "。"


def _source_specific_clauses(source_items: list[str]) -> list[str]:
    source = "；".join(source_items)
    if "我们应" in source:
        source = source.split("我们应", 1)[0]
    raw = re.split(r"[；。]+|(?=\d+[.、])", source)
    candidates: list[tuple[int, str]] = []
    for value in raw:
        text = normalize_text(value)
        text = re.sub(r"^(?:天气|机场|飞行程序|环境和地形|ATC)方面[，,:：]?", "", text)
        text = re.sub(r"^(?:离场|进场)", "", text)
        text = re.sub(r"^(?:[（(]?\d+[）).、，,:：]\s*)+", "", text)
        text = re.sub(r"\s*/\s*", "/", text).strip("，；。 ")
        if len(text) < 10 or len(text) > 150:
            continue
        if "机场标高" in text or "无高风险" in text:
            continue
        score = 0
        if re.search(r"(?:RWY|跑道|号跑道|HC\d+|P\d+|D\d+|≤|≥|\d+\s*(?:米|英尺|ft|KT|节))", text, re.I):
            score += 5
        if any(word in text for word in ("速度限制", "高度限制", "形态", "禁止", "不得", "复飞高度", "爬升梯度", "航向道", "等待线", "顺风超标")):
            score += 7
        if any(word in text for word in ("常用RNAV", "无影响", "燃油加注")):
            score -= 5
        if score > 5:
            candidates.append((score, text))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return unique([text for _, text in candidates])[:2]


def group_typical_items(risks: list[str], threats: list[str], max_items: int = 3) -> list[str]:
    source = " ".join([*risks, *threats])
    concepts = detected_group_concepts(source)
    items = [rule["typical"] for rule in concepts[:max_items]]
    if len(items) < max_items:
        for clause in _source_specific_clauses([*risks, *threats]):
            item = clause + ("。" if not clause.endswith("。") else "")
            if item not in items:
                items.append(item)
            if len(items) >= max_items:
                break
    return unique(items)[:max_items]


def group_core_sentences(source_items: list[str], max_sentences: int = 3) -> list[str]:
    source = " ".join(source_items)
    concepts = detected_group_concepts(source)
    items = [rule["core"] for rule in concepts[:max_sentences]]
    specifics = _source_specific_clauses(source_items)
    if specifics and len(items) < max_sentences + 1:
        items.append(
            "如实际涉及相关跑道或程序，应重点核对" + "；".join(specifics)
            + "，并与当前有效航图、MCDU及ATC指令交叉检查。"
        )
    return unique(items)[: max_sentences + 1]


def group_route_control(target: date, flights: list[CalendarEvent]) -> str:
    parts: list[str] = []
    if 4 <= target.month <= 10:
        parts.append(
            "本次运行可能涉及雷雨绕飞、直飞、雷达引导或高度变化，我们应加强频率守听、指令复诵和交叉证实。"
            "飞行中不得关闭气象雷达，按雷达型号结合自动和人工扫描；雷雨绕飞应尽早决策，必要时提前约40海里申请，"
            "并严格保持规定间隔。"
        )
    else:
        parts.append(
            "本次运行可能涉及直飞、雷达引导或高度变化，我们应加强频率守听、指令复诵和交叉证实，"
            "根据实际天气合理使用气象雷达。"
        )
    if len(flights) >= 3:
        parts.append(
            "连续运行阶段应合理分配任务，利用平飞及过站时间恢复精力；末段重点防止疲劳导致漏听指令、"
            "程序输入错误和进近监控下降，不确定时及时证实，无法满足稳定进近标准时坚决复飞。"
        )
    return "".join(parts)



def flight_context_text(flights: list[CalendarEvent]) -> str:
    return "\n".join(
        normalize_text(f"{event.summary}\n{event.description}\n{event.location}").upper()
        for event in flights
    )


def context_has(context: str, *tokens: str) -> bool:
    upper = (context or "").upper()
    return any(token.upper() in upper for token in tokens)


def weather_has_operational_risk(weather_sentence: str) -> bool:
    return any(
        token in (weather_sentence or "")
        for token in ("雷暴", "雷雨", "阵雨", "大雨", "低云", "云底", "能见度", "雾", "风切变", "湿跑道")
    )


def professionalize_incident(item: str) -> str:
    text = strip_terminal_punct(item)
    text = re.sub(r"[（(][^）)]*(?:参考|详见|EFB|机场特点汇总)[^）)]*[）)]", "", text)
    text = text.replace("请机组识别相关风险", "应提前识别并做好相应预案")
    text = text.replace("请机组注意识别该风险", "应提前识别并做好相应预案")
    text = text.replace("请机组注意", "我们应注意")
    text = re.sub(r"\s+", " ", text).strip("；。 ")
    return text + "。" if text else ""



def selected_typical_items(
    airport: str,
    risks: list[str],
    threats: list[str],
    month: int,
    max_items: int,
    *,
    detail: bool = False,
) -> list[str]:
    curated = CURATED_TYPICAL_INCIDENTS.get(canonical_airport_name(airport), [])
    limit = max_items if detail else min(max_items, 4)
    if curated:
        return curated[:limit]
    items = []
    for x in build_typical_items(risks, threats, month, max_items=max_items):
        item = professionalize_incident(x)
        bare = strip_terminal_punct(item)
        if not item or FALSE_INCIDENT_LABEL_RE.match(bare):
            continue
        items.append(item)
    if not items:
        # 没有明确典型不安全事件时，降级为少量“运行风险事件化”表述，禁止输出原表格字段。
        items = group_typical_items(risks, threats, max_items=min(limit, 3))
    return items[:limit]


def overall_risk_items(
    airports: list[str],
    target: date,
    weather_sentence: str,
    *,
    detail: bool = False,
) -> list[str]:
    items: list[str] = []
    if any(is_airport(a, "上海浦东") for a in airports):
        if target >= PUDONG_2606_EFFECTIVE:
            if detail:
                items.append(
                    "浦东机场运行流量大，多跑道运行，地面滑行和空中进离场程序较为复杂；"
                    "2606期程序已经调整，应重点防范新旧程序混淆、跑道过渡选择错误和FMS数据输入错误。"
                )
            else:
                items.append(
                    "浦东2606期程序刚完成调整，应防范新旧程序混淆、跑道过渡选择错误及FMS输入错误。"
                )
        else:
            items.append("浦东机场运行流量大，多跑道运行，地面滑行和空中进离场程序较为复杂。")
    if any(is_airport(a, "丽江三义") for a in airports):
        items.append(
            "丽江为一般高原机场、复杂机场，周围地形复杂、进近剖面较陡，管制指挥可能造成下降偏晚、"
            "剖面偏高和构型建立偏晚。"
        )
        if 5 <= target.month <= 9:
            items.append(
                "丽江处于雨季，应重点关注降水、低云、风切变、湿跑道、顺风和着陆距离变化，"
                "提前完成性能评估并明确复飞、等待和备降预案。"
            )
    if 4 <= target.month <= 10:
        items.append(
            "航路及终端区可能涉及雷雨绕飞、直飞、雷达引导和高度变化，我们应加强频率守听、"
            "指令复诵和交叉证实，持续监控油量、航迹和最低安全高度。"
        )
    if weather_sentence:
        items.append(weather_sentence)
    return unique(items)[: (6 if detail else 5)]


def pudong_core_items(target: date, context: str = "", *, detail: bool = False) -> list[str]:
    items: list[str] = []
    if target >= PUDONG_2606_EFFECTIVE:
        base = (
            "浦东2606期飞行程序已经调整。航前应确认导航数据库处于有效周期，结合最新航图、"
            "航图勘误、NOTAM和放行资料核对进离场程序；PF和PM应交叉检查跑道过渡、离场公共段、"
            "第一航路点及高度速度限制，防止新旧程序或跑道选择混淆。"
        )
        if context_has(context, "PIKAS"):
            base += "本次资料涉及PIKAS时，应重点区分PIKAS-3与PIKAS-5。"
        if context_has(context, "BEKOK", "PINOT", "NUPLA", "TOSAS"):
            base += "本次航路涉及相关点位时，应确认BEKOK替代PINOT、NUPLA替代TOSAS。"
        items.append(base)

    items.append(
        "浦东空域内进离港航空器数量多，且可能受到虹桥航流影响。我们应严格执行高度、速度和航向指令，"
        "收到直飞、雷达引导或进近方式变化后重新评估剩余距离、下降剖面和减速需求；飞机未准备好时，"
        "不应急于接受过度内切或转向五边。"
    )
    items.append(
        "浦东机坪可能给出“推出开车”或“推出到位报告”两类指令，应准确区分并完整复诵。"
        "滑行中如发现地面滑行引导车，应按机场细则关闭滑行灯并跟随引导车滑行。"
    )
    if 5 <= target.month <= 9:
        items.append(
            "浦东夏季雷雨活动频繁，可能伴随低云低能见、湿跑道、风切变和鸟击风险。起飞前应结合天气雷达、"
            "放行资料、备降条件和剩余油量提前制定绕飞、等待或备降预案；天气趋势持续恶化时应尽早与AOC沟通。"
        )

    if detail:
        if target >= PUDONG_2606_EFFECTIVE:
            items.insert(
                1,
                "浦东16L、17R、34R、35L跑道部分VNAV、GP INOP及LNAV进近最低标准已调整，航前应使用最新有效标准；"
                "如执行VOR 17L或VOR 35R进近，应重点核对航图、导航数据库修正内容及相关高度限制。",
            )
        if context_has(context, "34R"):
            items.append(
                "本次资料涉及34R。执行34R盲降进近时，特定位置和高度可能因地面建筑物造成无线电高度跳变并触发TERRAIN警戒；"
                "我们应结合实际位置、高度、导航精度和飞机状态，严格按照当前有效操作通告处置并按要求报告。"
            )
        else:
            items.append(
                "条件性提示：如实际执行34R盲降进近，应在航前查阅当前有效操作通告，关注特定位置和高度可能发生的"
                "无线电高度跳变及TERRAIN警戒；未使用34R时不套用该特殊处置。"
            )
    return unique(items)


def lijiang_core_items(target: date, context: str = "", *, detail: bool = False) -> list[str]:
    items = [
        "丽江机场标高7358英尺，周围四面环山，东西两侧地形限制明显。我们应严格按照公布程序飞行，持续监控航迹、"
        "高度、最低安全高度和导航精度；雷达引导、直飞或天气绕飞时，应特别防范偏离程序后接近复杂地形。",
        "丽江进近可能出现下降偏晚和剖面偏高。我们应提前制定下降、减速和构型计划，结合剩余距离、顺风、地速和下降率"
        "及时向管制申请下降或减速，避免为追赶剖面使用过大下降率；结合下降剖面和速度条件，尽量在低于5700米后选择形态，"
        "如需在5700米以上放形态，严格按照当前运行要求执行信息报告。",
        "20号跑道相关进近下降梯度较大，五边还可能存在顺风。我们应提前建立着陆构型，持续监控下降率、速度趋势、推力状态"
        "和垂直偏差；未在规定高度达到稳定进近标准时，应果断复飞。",
    ]
    if 5 <= target.month <= 9:
        items.append(
            "丽江5月至9月处于雨季，应重点关注降水、低云、风切变、湿跑道和着陆距离。航前应根据跑道状况、风向风速、"
            "飞机重量和制动效应完成着陆性能评估，必要时考虑使用中档自动刹车，并明确复飞、等待或备降预案。"
        )
    if detail:
        items.append(
            "丽江进近区域实施ADS-B管制，GPS存在工作不稳定的可能。飞行中应监控GPS状态、导航精度、飞机位置和航迹变化；"
            "如出现GPS PRIMARY LOST、FM/GPS位置不一致或导航性能下降，应及时向ATC报告，并做好传统导航、非GPS进近及"
            "公司共同决策的准备。"
        )
        if context_has(context, "ILS INOP", "GS INOP", "盲降不工作", "盲降不可用", "下滑道不工作"):
            items.append(
                "本次资料提示盲降或下滑道不可用，应按照当前有效操作通告重新准备进近方式，核对FINAL APP、FDP限制高度、"
                "APPR及FMA方式；执行RNP 20时按要求设置DDA。"
            )
        else:
            items.append(
                "条件性提示：仅当NOTAM、放行资料或ATIS明确盲降/下滑道不可用时，才按当前有效丽江特殊操作通告准备RNP进近；"
                "设备正常时不固定套用该程序。"
            )
    return unique(items)


def _core_item_score(item: str) -> int:
    text = strip_terminal_punct(item)
    if not text or text in {"暂无", "无", "暂无。", "无。"}:
        return -1000
    score = 0
    for token in RISK_KEYWORDS:
        if token in text:
            score += 4
    for token in ("ATC", "管制", "雷达引导", "直飞", "跑道", "滑行", "进近", "离场", "复飞", "盲降", "地形", "风切变"):
        if token in text:
            score += 6
    if text.startswith(("机场分类", "责任中队")):
        score -= 30
    if "详见" in text or "参考 EFB" in text or "参考EFB" in text:
        score -= 15
    return score


def generic_core_items(items: list[str], month: int, max_items: int = 6) -> list[str]:
    ranked = sorted(enumerate(items), key=lambda pair: (-_core_item_score(pair[1]), pair[0]))
    result: list[str] = []
    for _, item in ranked:
        if _core_item_score(item) < -100:
            continue
        text = natural_core_item(item, month)
        text = re.sub(r"^(?:离场|进场)?(?:天气|机场|飞行程序|环境和地形|ATC)方面[，,:：]?", "", text)
        text = text.replace("建议", "我们应").replace("需要", "应")
        text = text.replace("我们应不要", "我们不应").replace("我们应不得", "我们不得")
        text = text.replace("我们应严禁", "严禁")
        text = re.sub(r"\s+", " ", text).strip("；。 ")
        if not text or FALSE_INCIDENT_LABEL_RE.match(text):
            continue
        # 表格拼接内容过长时，只保留最关键的前两句，避免机械堆砌。
        fragments = [x.strip("；。 ") for x in re.split(r"[。；]", text) if x.strip("；。 ")]
        if len(fragments) > 2:
            text = "；".join(fragments[:2])
        if not any(token in text for token in ("我们", "应", "注意", "防止", "避免", "严格", "提前", "确认", "监控", "不得", "严禁")):
            text = "我们应结合实际运行条件重点关注" + text
        result.append(text + "。")
    return unique(result)[:max_items]


def airport_core_items(
    airport: str,
    source_items: list[str],
    target: date,
    context: str = "",
    *,
    detail: bool = False,
) -> list[str]:
    canonical = canonical_airport_name(airport)
    if canonical == "上海浦东":
        return pudong_core_items(target, context, detail=detail)
    if canonical == "丽江三义":
        return lijiang_core_items(target, context, detail=detail)
    curated = CURATED_CORE_THREATS.get(canonical)
    if curated:
        return curated[: (6 if detail else 4)]
    return generic_core_items(source_items, target.month, max_items=6 if detail else 4)


def english_generation_decision(
    event: CalendarEvent | DutyContext,
    settings: dict,
    override: str = "auto",
) -> tuple[bool, bool, list[str]]:
    del settings
    names = foreign_crew_names(event)
    if override == "yes":
        return True, False, names
    if not names:
        return False, False, names
    return False, True, names


def should_generate_english(event: CalendarEvent | DutyContext) -> bool:
    return bool(foreign_crew_names(event))


def airport_roles(
    event: CalendarEvent | DutyContext,
    airport: str,
) -> tuple[str, ...]:
    canonical = canonical_airport_name(airport)
    if isinstance(event, DutyContext):
        roles = event.role_map.get(canonical, ())
        if roles:
            return roles
    departure, arrival = event.route[:2]
    roles: list[str] = []
    if canonical == canonical_airport_name(departure):
        roles.append("departure")
    if canonical == canonical_airport_name(arrival):
        roles.append("arrival")
    if not roles:
        raise ValueError(f"机场不属于已匹配任务：{airport}")
    return tuple(roles)


def airport_role(event: CalendarEvent | DutyContext, airport: str) -> str:
    roles = set(airport_roles(event, airport))
    if roles == {"departure", "arrival"}:
        return "transit"
    return next(iter(roles))


def bind_catalog_fact(fact: BilingualFact) -> BilingualFact:
    metadata = FACT_PROVENANCE.get(fact.fact_id)
    if not metadata:
        return fact
    airport = canonical_airport_name(str(metadata.get("airport", fact.airport)))
    location = AIRPORT_SOURCE_LOCATIONS.get(airport, {})
    resolved = {
        "source_file": str(location.get("source_file", "")),
        "source_page": FACT_SOURCE_PAGES.get(
            fact.fact_id,
            str(location.get("source_page", "N/A")),
        ),
        "source_heading": str(location.get("source_heading", airport)),
        "semantic_key": fact.fact_id,
        **metadata,
    }
    return attach_source_semantics(replace(fact, **resolved))


def _text_bigrams(value: str) -> set[str]:
    compact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", value or "").upper()
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _support_score(left: str, right: str) -> float:
    left_parts = _text_bigrams(left)
    right_parts = _text_bigrams(right)
    if not left_parts or not right_parts:
        return 0.0
    return len(left_parts & right_parts) / len(left_parts | right_parts)


def best_source_record(
    airport: str,
    text_zh: str,
    records: list[dict[str, object]],
    *,
    category: str,
) -> dict[str, object]:
    canonical = canonical_airport_name(airport)
    candidates: list[tuple[float, int, dict[str, object]]] = []
    for record in records:
        if canonical_airport_name(str(record.get("airport", ""))) != canonical:
            continue
        if str(record.get("category", "")) != category:
            continue
        score = _support_score(text_zh, str(record.get("text_zh", "")))
        if score < 0.08:
            continue
        source_rank = SOURCE_PRIORITY.get(str(record.get("source", "")), 9)
        candidates.append((-score, source_rank, record))
    if candidates:
        return min(candidates, key=lambda item: (item[0], item[1]))[2]
    location = AIRPORT_SOURCE_LOCATIONS.get(canonical, {})
    return {
        "airport": canonical,
        "source_file": str(
            location.get("source_file", "crew_agents/flight_prep_agent.py")
        ),
        "source": "CURATED",
        "source_page": str(location.get("source_page", "N/A")),
        "source_heading": str(
            location.get("source_heading", f"{canonical}人工精选")
        ),
        "source_section": f"{canonical}人工精选／{category}",
        "operational_phase": "incident" if category == "typical" else "unspecified",
        "airport_specific": True,
        "category": category,
        "text_zh": text_zh,
        "text_en": "",
    }


SOURCE_RESTRICTION_RE = re.compile(r"禁止|只能|仅允许|必须|不得|严禁|限制")
SOURCE_MITIGATION_RE = re.compile(r"应|建议|注意|需|请|防止|避免|控制|确认|使用|采取")
SOURCE_RISK_RE = re.compile(r"风险|易|可能|导致|触发|威胁|危险")
SOURCE_APPLICABILITY_RE = re.compile(
    r"\d{2}号(?:跑道)?|跑道|起飞|离场|进场|进近|着陆|落地|滑行|经停|过站"
)
COMPOUND_LANDING_DISTANCE_RE = re.compile(
    r"(?P<runways>\d{2}(?:\s*和\s*\d{2})+)号(?:跑道)?的?"
    r"实际着陆可用距离为"
    r"(?P<distances>\d+\s*米(?:\s*和\s*\d+\s*米)+)"
)
RUNWAY_ENTRY_DISPLACEMENT_RE = re.compile(
    r"(?:跑道)?(?:两头|两端|两侧)?(?:均|都)?(?:有)?(?:跑道)?入口(?:有)?内移"
)


def source_semantics(text: str) -> SourceSemantics:
    clauses = tuple(
        unique(
            [
                clause.strip()
                for clause in re.split(r"[，,；;。]+", normalize_text(text))
                if clause.strip()
            ]
        )
    )
    restriction = tuple(
        clause for clause in clauses if SOURCE_RESTRICTION_RE.search(clause)
    )
    mitigation = tuple(
        clause
        for clause in clauses
        if clause not in restriction and SOURCE_MITIGATION_RE.search(clause)
    )
    risk = tuple(
        clause
        for clause in clauses
        if clause not in restriction
        and clause not in mitigation
        and SOURCE_RISK_RE.search(clause)
    )
    operational_condition = tuple(
        clause
        for clause in clauses
        if clause not in restriction and clause not in mitigation and clause not in risk
    )
    applicability = tuple(
        unique(SOURCE_APPLICABILITY_RE.findall(normalize_text(text)))
    )
    return SourceSemantics(
        operational_condition=operational_condition,
        applicability=applicability,
        risk=risk,
        mitigation=mitigation,
        restriction=restriction,
    )


def attach_source_semantics(fact: BilingualFact) -> BilingualFact:
    original = fact.source_text_zh or fact.text_zh
    semantics = source_semantics(original)
    enriched = replace(
        fact,
        source_text_zh=original,
        operational_condition=(
            fact.operational_condition or semantics.operational_condition
        ),
        applicability=fact.applicability or semantics.applicability,
        risk=fact.risk or semantics.risk,
        mitigation=fact.mitigation or semantics.mitigation,
        restriction=fact.restriction or semantics.restriction,
        season_scope=fact.season_scope or detected_season_scope(original),
        source_fact_ids=fact.source_fact_ids or (fact.fact_id,),
    )
    return replace(enriched, topic=classify_fact_topic(enriched))


def landing_prohibited_runways(
    airport: str,
    records: list[dict[str, object]],
) -> set[str]:
    canonical = canonical_airport_name(airport)
    runways: set[str] = set()
    for record in records:
        if canonical_airport_name(str(record.get("airport", ""))) != canonical:
            continue
        if str(record.get("category", "")) != "core":
            continue
        text = normalize_text(str(record.get("text_zh", "")))
        record_runways = set(
            re.findall(r"(?<!\d)(\d{2})号(?:跑道)?", text)
        )
        clauses = [
            clause.strip()
            for clause in re.split(r"[，,；;。]+", text)
            if clause.strip()
        ]
        for clause in clauses:
            landing_prohibited = bool(
                ("禁止" in clause and ("进近" in clause or "着陆" in clause))
                or ("只能" in clause and "起飞" in clause)
                or ("仅允许" in clause and "起飞" in clause)
            )
            if not landing_prohibited:
                continue
            clause_runways = set(
                re.findall(r"(?<!\d)(\d{2})号(?:跑道)?", clause)
            )
            if clause_runways:
                runways.update(clause_runways)
            elif len(record_runways) == 1:
                runways.update(record_runways)
    return runways


def project_source_fact_for_applicability(
    text: str,
    *,
    landing_prohibited: set[str],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Conservatively remove inapplicable runway-distance pairs.

    Only an explicitly paired runway/distance list is projected, and only when a
    separate source restriction prohibits landing on one of those runways. All
    remaining clauses, especially mitigations and restrictions, stay verbatim.
    Unrecognised structures are returned unchanged.
    """
    original = strip_terminal_punct(normalize_text(text))
    rewritten = original
    excluded: list[str] = []
    reasons: list[str] = []
    match = COMPOUND_LANDING_DISTANCE_RE.search(original)
    if match:
        runways = re.findall(r"\d{2}", match.group("runways"))
        distances = re.findall(r"\d+\s*米", match.group("distances"))
        if len(runways) == len(distances):
            retained = [
                (runway, distance.replace(" ", ""))
                for runway, distance in zip(runways, distances)
                if runway not in landing_prohibited
            ]
            removed = [
                (runway, distance.replace(" ", ""))
                for runway, distance in zip(runways, distances)
                if runway in landing_prohibited
            ]
            if retained and removed:
                if len(retained) == 1:
                    runway_text = f"{retained[0][0]}号跑道"
                    distance_text = retained[0][1]
                else:
                    runway_text = "和".join(item[0] for item in retained) + "号跑道"
                    distance_text = "和".join(item[1] for item in retained)
                replacement = (
                    f"{runway_text}的实际着陆可用距离为{distance_text}"
                )
                rewritten = (
                    original[: match.start()]
                    + replacement
                    + original[match.end() :]
                )
                if RUNWAY_ENTRY_DISPLACEMENT_RE.search(rewritten):
                    rewritten = RUNWAY_ENTRY_DISPLACEMENT_RE.sub(
                        f"{runway_text}入口内移",
                        rewritten,
                        count=1,
                    )
                    rewritten = rewritten.replace(
                        f"，{runway_text}的实际着陆可用距离",
                        "，实际着陆可用距离",
                        1,
                    )
                for runway, distance in removed:
                    excluded.append(
                        f"{runway}号跑道实际着陆可用距离为{distance}"
                    )
                    reasons.append(
                        f"同一机场来源限制明确{runway}号跑道禁止进近着陆"
                    )

    conditional_measure = re.compile(
        r"请结合(?P<basis>[^，。；（）()]*?(?:计算)?结果)"
        r"采取(?:相关)?措施[（(](?P<measure>[^）)]+)[）)]"
    )
    rewritten = conditional_measure.sub(
        lambda item: (
            f"应结合{item.group('basis')}采取措施，"
            f"如计算需要再{item.group('measure')}"
        ),
        rewritten,
    )
    return rewritten.rstrip("。") + "。", tuple(excluded), tuple(reasons)


SOURCE_REFERENCE_PAREN_RE = re.compile(
    r"[（(][^）)]*(?:参考|详见)\s*(?:EFB|航图|机场特点(?:汇总)?)[^）)]*[）)]",
    re.IGNORECASE,
)
SOURCE_REFERENCE_CLAUSE_RE = re.compile(
    r"(?:请)?(?:参考|详见)\s*(?:EFB|航图|机场特点(?:汇总)?)[^；。]*",
    re.IGNORECASE,
)


def strip_source_reference_clauses(text: str) -> tuple[str, tuple[str, ...]]:
    """Remove manual cross-references while preserving the operational fact.

    Source references are provenance rather than cockpit content. The removed
    clause is retained in fact metadata so the transformation stays auditable.
    """
    excluded: list[str] = []

    def drop(match: re.Match[str]) -> str:
        clause = match.group(0).strip(" （）()。；;，,")
        if clause:
            excluded.append(clause)
        return ""

    cleaned = SOURCE_REFERENCE_PAREN_RE.sub(drop, normalize_text(text))
    cleaned = SOURCE_REFERENCE_CLAUSE_RE.sub(drop, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[，,；;]+(?=。|$)", "", cleaned).strip(" ；;，,")
    return (
        cleaned.rstrip("。") + "。" if cleaned.strip("。") else "",
        tuple(unique(excluded)),
    )


def _month_range(start: int, end: int) -> tuple[int, ...]:
    if start <= end:
        return tuple(range(start, end + 1))
    return tuple([*range(start, 13), *range(1, end + 1)])


def detected_season_scope(text: str) -> tuple[int, ...]:
    """Return explicit applicable months without inferring an unspecified season."""
    normalized = normalize_text(text)
    months: set[int] = set()
    for label in SEASON_LABELS:
        if label in normalized:
            months.update(SEASON_MONTHS[label])
    range_spans: list[tuple[int, int]] = []
    for match in MONTH_SCOPE_RE.finditer(normalized):
        months.update(_month_range(int(match.group("start")), int(match.group("end"))))
        range_spans.append(match.span())
    for match in SINGLE_MONTH_SCOPE_RE.finditer(normalized):
        if any(start <= match.start() < end for start, end in range_spans):
            continue
        months.add(int(match.group("month")))
    return tuple(month for month in range(1, 13) if month in months)


def filter_seasonal_text(
    text: str,
    month: int,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[int, ...]]:
    """Conservatively remove only clauses with an explicit mismatched season.

    A seasonal marker embedded in a clause applies to that whole clause. An
    annual prefix is retained only when punctuation clearly separates it from
    the seasonal suffix; otherwise the complete clause is excluded.
    """
    normalized = normalize_text(text)
    full_scope = detected_season_scope(normalized)
    if not full_scope:
        return normalized, (), (), full_scope

    kept: list[str] = []
    excluded: list[str] = []
    reasons: list[str] = []
    changed = False
    segments = [item for item in re.findall(r"[^；。]+[；。]?", normalized) if item.strip()]
    inherited_scope: tuple[int, ...] = ()
    for raw_segment in segments:
        punctuation = raw_segment[-1] if raw_segment[-1:] in "；。" else ""
        segment = raw_segment.rstrip("；。").strip()
        explicit_scope = detected_season_scope(segment)
        scope = explicit_scope or inherited_scope
        if not explicit_scope and any(
            marker in segment for marker in ("全年", "常年", "四季")
        ):
            scope = ()
        if not scope or month in scope:
            kept.append(segment + punctuation)
            inherited_scope = scope if punctuation == "；" else ()
            continue

        marker_matches = [
            *SEASON_LABEL_RE.finditer(segment),
            *MONTH_SCOPE_RE.finditer(segment),
            *SINGLE_MONTH_SCOPE_RE.finditer(segment),
        ]
        marker = min(marker_matches, key=lambda item: item.start()) if marker_matches else None
        prefix = ""
        seasonal_clause = segment
        if marker and marker.start() > 0:
            boundary = segment.rfind("，", 0, marker.start())
            ascii_boundary = segment.rfind(",", 0, marker.start())
            boundary = max(boundary, ascii_boundary)
            if boundary >= 0 and not segment[boundary + 1 : marker.start()].strip():
                prefix = segment[:boundary].strip(" ，,")
                seasonal_clause = segment[boundary + 1 :].strip(" ，,")
        if prefix:
            kept.append(prefix + punctuation)
        excluded.append(seasonal_clause)
        reasons.append(
            f"目标月份为{month}月，不在资料明确季节适用月份"
            f"{','.join(str(value) for value in scope)}月内"
        )
        changed = True
        inherited_scope = scope if punctuation == "；" else ()

    if not changed:
        return normalized, (), (), full_scope
    cleaned = "".join(kept).strip(" ；。")
    return (
        cleaned + "。" if cleaned else "",
        tuple(unique(excluded)),
        tuple(reasons),
        full_scope,
    )


FLIGHT_SCOPE_RE = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z]\d|\d[A-Z])\d{3,4}[A-Z]?(?![A-Z0-9])",
    re.IGNORECASE,
)
ROUTE_SCOPE_RE = re.compile(
    r"(?:航线|航段)\s*[:：]?\s*"
    r"(?P<departure>[\u4e00-\u9fffA-Za-z0-9]{2,20})\s*"
    r"(?:→|至|-)\s*"
    r"(?P<arrival>[\u4e00-\u9fffA-Za-z0-9]{2,20})"
)


def record_flight_scope(record: dict[str, object], text: str) -> tuple[str, ...]:
    configured = record.get("flight_scope") or record.get("flight_numbers") or ()
    if isinstance(configured, str):
        configured = re.split(r"[,，/\s]+", configured)
    values = [str(value).strip().upper() for value in configured if str(value).strip()]
    values.extend(match.group(0).upper() for match in FLIGHT_SCOPE_RE.finditer(text))
    return tuple(unique(values))


def record_route_scope(
    record: dict[str, object],
    text: str,
) -> tuple[tuple[str, str], ...]:
    routes: list[tuple[str, str]] = []
    configured = record.get("route_scope") or record.get("routes") or ()
    if isinstance(configured, (str, tuple)) and not (
        isinstance(configured, tuple) and len(configured) == 2
    ):
        configured = [configured]
    if isinstance(configured, tuple) and len(configured) == 2:
        configured = [configured]
    for value in configured:
        if isinstance(value, (list, tuple)) and len(value) == 2:
            departure, arrival = value
        else:
            match = re.search(r"(.+?)\s*(?:→|至|-)\s*(.+)", str(value))
            if not match:
                continue
            departure, arrival = match.groups()
        routes.append(
            (
                canonical_airport_name(str(departure)),
                canonical_airport_name(str(arrival)),
            )
        )
    for match in ROUTE_SCOPE_RE.finditer(text):
        routes.append(
            (
                canonical_airport_name(match.group("departure")),
                canonical_airport_name(match.group("arrival")),
            )
        )
    return tuple(dict.fromkeys(routes))


def classify_fact_topic(fact: BilingualFact) -> str:
    if fact.topic:
        return fact.topic
    phase_topics = {
        "preparation": "preparation",
        "clearance": "preparation",
        "ground": "ground",
        "landing_ground": "ground",
        "departure": "departure",
        "initial_climb": "departure",
        "arrival": "arrival",
        "approach": "approach",
        "landing": "approach",
        "terrain": "terrain",
        "weather": "weather",
        "navigation": "preparation",
        "special": "special",
    }
    if fact.operational_phase in phase_topics:
        return phase_topics[fact.operational_phase]
    text = normalize_text(fact.text_zh)
    keyword_topics = (
        ("terrain", ("地形", "MSA", "CFIT", "最低安全高度")),
        ("performance", ("高原", "性能", "FLYSMART", "FLY SMART", "载重", "襟缝翼")),
        ("weather", ("天气", "雷暴", "风切变", "大风", "沙尘", "结冰", "低云")),
        ("ground", ("滑行", "推出", "机位", "道面", "地面")),
        ("departure", ("起飞", "离场", "SID", "初始爬升")),
        ("arrival", ("进场", "雷达引导", "高截获", "能量管理")),
        ("approach", ("进近", "着陆", "盲降", "ILS", "PAPI")),
        ("preparation", ("驾驶舱准备", "程序核对", "航路点", "MCDU")),
    )
    for topic, keywords in keyword_topics:
        if any(keyword.upper() in text.upper() for keyword in keywords):
            return topic
    return "special"


def exclusion_log_entry(
    fact: BilingualFact,
    clause: str,
    reason: str,
) -> dict[str, object]:
    return {
        "airport": fact.airport,
        "fact_id": fact.fact_id,
        "source_file": fact.source_file,
        "source_page": fact.source_page,
        "source_heading": fact.source_heading,
        "source_section": fact.source_section,
        "clause": clause,
        "reason": reason,
    }


def filter_fact_for_duty(
    fact: BilingualFact,
    event: CalendarEvent | DutyContext,
    target: date,
    exclusion_log: list[dict[str, object]] | None = None,
) -> BilingualFact | None:
    flights = {
        item.flight_number.upper()
        for item in (event.events if isinstance(event, DutyContext) else (event,))
        if item.flight_number
    }
    duty_routes = {
        tuple(canonical_airport_name(value) for value in item.route)
        for item in (event.events if isinstance(event, DutyContext) else (event,))
    }
    if fact.flight_scope and flights.isdisjoint(fact.flight_scope):
        reason = "与当前航班/航线不匹配"
        if exclusion_log is not None:
            exclusion_log.append(exclusion_log_entry(fact, fact.source_text_zh or fact.zh, reason))
        return None
    if fact.route_scope and duty_routes.isdisjoint(set(fact.route_scope)):
        reason = "与当前航班/航线不匹配"
        if exclusion_log is not None:
            exclusion_log.append(exclusion_log_entry(fact, fact.source_text_zh or fact.zh, reason))
        return None

    filtered, clauses, reasons, scope = filter_seasonal_text(fact.zh, target.month)
    if not filtered:
        if exclusion_log is not None:
            for clause, reason in zip(clauses or (fact.zh,), reasons or ("季节范围不适用",)):
                exclusion_log.append(exclusion_log_entry(fact, clause, reason))
        return None
    rendered_semantics = source_semantics(filtered)
    return replace(
        fact,
        text_zh=filtered,
        text_en="" if clauses and filtered != fact.zh else fact.text_en,
        season_scope=scope,
        topic=classify_fact_topic(replace(fact, text_zh=filtered)),
        operational_condition=rendered_semantics.operational_condition,
        applicability=rendered_semantics.applicability,
        risk=rendered_semantics.risk,
        mitigation=rendered_semantics.mitigation,
        restriction=rendered_semantics.restriction,
        excluded_source_clauses=tuple([*fact.excluded_source_clauses, *clauses]),
        exclusion_reasons=tuple([*fact.exclusion_reasons, *reasons]),
        source_fact_ids=fact.source_fact_ids or (fact.fact_id,),
    )


def source_record_facts(
    airport: str,
    records: list[dict[str, object]],
    *,
    category: str,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    """Build only facts that have an explicit current-airport source record.

    Records carrying bilingual text are used verbatim. For legacy Chinese-only
    records, a controlled concept wording is allowed only when the source text
    explicitly triggers that concept; otherwise the record is omitted rather than
    filled with a generic airport template.
    """
    canonical = canonical_airport_name(airport)
    prohibited_runways = landing_prohibited_runways(canonical, records)
    facts_by_semantic: dict[str, BilingualFact] = {}
    ordered_records = sorted(
        enumerate(records, start=1),
        key=lambda item: (
            SOURCE_BUILD_PRIORITY.get(str(item[1].get("source", "")), 9),
            item[0],
        ),
    )
    for index, record in ordered_records:
        if canonical_airport_name(str(record.get("airport", ""))) != canonical:
            continue
        if str(record.get("category", "")) != category:
            continue
        source_clause = str(record.get("text_zh", "")).strip()
        source_original_text = str(
            record.get("source_original_text") or source_clause
        ).strip()
        if not source_clause or record.get("pre_excluded_reason"):
            if exclusion_log is not None and source_original_text:
                exclusion_log.append(
                    {
                        "airport": canonical,
                        "fact_id": str(record.get("fact_id") or ""),
                        "source_file": str(record.get("source_file") or ""),
                        "source_page": str(record.get("source_page") or "N/A"),
                        "source_heading": str(record.get("source_heading") or canonical),
                        "source_section": str(record.get("source_section") or "未标明章节"),
                        "clause": source_original_text,
                        "reason": str(
                            record.get("pre_excluded_reason")
                            or "清洗后无实质运行内容"
                        ),
                    }
                )
            continue
        source_text_zh = source_original_text
        text_zh, excluded_clauses, exclusion_reasons = (
            project_source_fact_for_applicability(
                source_clause,
                landing_prohibited=prohibited_runways,
            )
        )
        excluded_clauses = tuple(
            [*record.get("excluded_source_clauses", ()), *excluded_clauses]
        )
        exclusion_reasons = tuple(
            [*record.get("exclusion_reasons", ()), *exclusion_reasons]
        )
        text_zh, reference_clauses = strip_source_reference_clauses(text_zh)
        if reference_clauses:
            excluded_clauses = tuple([*excluded_clauses, *reference_clauses])
            exclusion_reasons = tuple(
                [
                    *exclusion_reasons,
                    *("资料交叉引用不进入运行正文" for _ in reference_clauses),
                ]
            )
        if not text_zh:
            continue
        text_en = str(record.get("text_en", "")).strip()
        original_semantics = source_semantics(source_clause)
        rendered_semantics = source_semantics(text_zh)
        concept_name = str(record.get("semantic_key", "")).strip()
        phase = str(record.get("operational_phase") or "unspecified")
        if not (text_zh and text_en):
            concepts = detected_group_concepts(text_zh)
            if concepts:
                concept = concepts[0]
                concept_name = str(concept["name"])
                english = CONCEPT_ENGLISH.get(concept_name)
                if english:
                    text_en = english[0 if category == "typical" else 1]
                phase = {
                    "ground": "ground",
                    "terrain": "terrain",
                    "weather": "weather",
                    "windshear": "weather",
                    "energy": "arrival",
                    "tcas": "approach",
                    "bird": "approach",
                }.get(concept_name, phase)
        semantic_key = str(record.get("semantic_key") or record.get("fact_id") or "")
        if not semantic_key:
            normalized_fact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", text_zh).upper()
            if (
                category == "core"
                and "跑道入口" in text_zh
                and "着陆" in text_zh
                and "距离" in text_zh
            ):
                semantic_key = "runway_landing_distance"
            else:
                semantic_key = f"text:{normalized_fact}"
        source = str(record.get("source") or "CURATED")
        importance = int(record.get("importance", 50))
        if source == "CURATED":
            importance = max(importance, 85)
        elif source == "supplement":
            importance = max(importance, 65)
        operation_subsection = bool(record.get("operation_subsection"))
        if not operation_subsection and any(
            token in text_zh
            for token in ("禁止", "只能", "高度", "速度", "距离", "跑道")
        ):
            importance = max(importance, 92)
        elif not operation_subsection and any(
            token in text_zh for token in ("地形", "CFIT", "风切变")
        ):
            importance = max(importance, 88)
        fact_id = str(
            record.get("fact_id")
            or f"{canonical}_{category}_record_{index}"
        )
        # A flight number or route inside a typical incident identifies the
        # historical event; it is not an applicability restriction for the
        # current duty.  Core operating facts retain the existing scope rules.
        flight_scope = (
            () if category == "typical" else record_flight_scope(record, source_clause)
        )
        route_scope = (
            () if category == "typical" else record_route_scope(record, source_clause)
        )
        provisional = BilingualFact(
            fact_id,
            text_zh,
            text_en,
            airport=canonical,
            operational_phase=phase,
        )
        facts_by_semantic[semantic_key] = BilingualFact(
            fact_id,
            text_zh,
            text_en,
            airport=canonical,
            source_file=str(record.get("source_file") or ""),
            source=source,
            source_page=str(record.get("source_page") or "N/A"),
            source_heading=str(record.get("source_heading") or canonical),
            source_section=str(record.get("source_section") or "未标明章节"),
            operational_phase=phase,
            airport_specific=bool(record.get("airport_specific", True)),
            category=category,
            role_scope=tuple(record.get("role_scope") or ()),
            importance=importance,
            semantic_key=semantic_key,
            source_text_zh=source_text_zh,
            operational_condition=rendered_semantics.operational_condition,
            applicability=rendered_semantics.applicability,
            risk=original_semantics.risk,
            mitigation=original_semantics.mitigation,
            restriction=original_semantics.restriction,
            excluded_source_clauses=excluded_clauses,
            exclusion_reasons=exclusion_reasons,
            season_scope=detected_season_scope(text_zh),
            flight_scope=flight_scope,
            route_scope=route_scope,
            topic=classify_fact_topic(provisional),
            source_fact_ids=(fact_id,),
            source_record_ids=(
                str(record.get("source_record_id") or fact_id),
            ),
            source_clauses=(source_clause,),
            source_original_texts=(source_original_text,),
        )
    return list(facts_by_semantic.values())


def fuse_airport_facts(facts: list[BilingualFact]) -> list[BilingualFact]:
    """Apply PDF base -> supplement gaps -> CURATED override semantics."""
    fused: dict[str, BilingualFact] = {}
    ordered = sorted(
        facts,
        key=lambda fact: (
            SOURCE_BUILD_PRIORITY.get(fact.source, 9),
            fact.fact_id,
        ),
    )
    for fact in ordered:
        semantic_key = fact.semantic_key or fact.fact_id
        current = fused.get(semantic_key)
        if current is None:
            fused[semantic_key] = fact
            continue
        if SOURCE_PRIORITY.get(fact.source, 9) <= SOURCE_PRIORITY.get(
            current.source, 9
        ):
            fused[semantic_key] = fact
    return list(fused.values())


ROLE_ALLOWED_PHASES = {
    "departure": {
        "preparation",
        "clearance",
        "ground",
        "departure",
        "initial_climb",
        "navigation",
        "weather",
        "terrain",
        "performance",
        "special",
        "unspecified",
    },
    "arrival": {
        "preparation",
        "ground",
        "arrival",
        "approach",
        "landing",
        "landing_ground",
        "navigation",
        "weather",
        "terrain",
        "performance",
        "special",
        "unspecified",
    },
}


def fact_matches_airport_role(fact: BilingualFact, role: str) -> bool:
    """Use structured phase/scope metadata to reject opposite-role core facts."""
    if role == "transit":
        return not fact.role_scope or bool(
            set(fact.role_scope).intersection({"departure", "arrival"})
        )
    if fact.role_scope:
        return role in fact.role_scope
    phase = fact.operational_phase or "unspecified"
    if phase not in ROLE_ALLOWED_PHASES[role]:
        return False
    if phase not in {"unspecified", "special"}:
        return True
    topic = classify_fact_topic(fact)
    if role == "departure" and topic in {"arrival", "approach"}:
        return False
    if role == "arrival" and topic == "departure":
        return False
    return True


def is_manual_operation_subsection_fact(fact: BilingualFact) -> bool:
    return any(
        f"／{label}" in fact.source_section for label in OPERATION_SECTION_PHASES
    )


def select_airport_facts(
    airport: str,
    role: str,
    facts: list[BilingualFact],
    *,
    max_items: int = 5,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    canonical = canonical_airport_name(airport)
    eligible: list[BilingualFact] = []
    for fact in fuse_airport_facts(facts):
        if canonical_airport_name(fact.airport) != canonical:
            continue
        if not fact_matches_airport_role(fact, role):
            if exclusion_log is not None:
                exclusion_log.append(
                    exclusion_log_entry(
                        fact,
                        fact.source_text_zh or fact.zh,
                        f"与当前机场{role}角色不匹配",
                    )
                )
            continue
        eligible.append(
            replace(
                fact,
                topic=classify_fact_topic(fact),
                source_fact_ids=fact.source_fact_ids or (fact.fact_id,),
            )
        )

    if role == "transit":
        primary = [
            fact
            for fact in eligible
            if not is_manual_operation_subsection_fact(fact)
        ]
        if primary:
            eligible = primary

    phase_order = ROLE_PHASE_PRIORITY[role]
    selection_order = sorted(
        eligible,
        key=lambda fact: (
            0 if fact.importance >= 99 else 1,
            SOURCE_PRIORITY.get(fact.source, 9),
            phase_order.get(fact.operational_phase, 10),
            -fact.importance,
            fact.fact_id,
        )
    )
    selected: list[BilingualFact] = []
    selected_ids: set[str] = set()

    # Explicit restrictions, source controls, and high-importance operational
    # facts are protected before topic coverage is considered.
    for fact in selection_order:
        if len(selected) >= max_items:
            break
        if (
            fact.restriction or fact.importance >= 92
        ) and not is_manual_operation_subsection_fact(fact):
            selected.append(fact)
            selected_ids.add(fact.fact_id)

    # Then retain the strongest available fact for each role-relevant topic.
    # This is intentionally done after protected controls so topic diversity
    # cannot evict a mandatory restriction.
    for topic in ROLE_TOPIC_PRIORITY[role]:
        if len(selected) >= max_items:
            break
        candidate = next(
            (
                fact
                for fact in selection_order
                if fact.fact_id not in selected_ids and fact.topic == topic
            ),
            None,
        )
        if candidate is None:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.fact_id)

    selected_topics = {fact.topic for fact in selected}
    for fact in selection_order:
        if len(selected) >= max_items:
            break
        if fact.fact_id in selected_ids:
            continue
        if (
            is_manual_operation_subsection_fact(fact)
            and fact.topic in selected_topics
            and not any(
                set(fact.source_record_ids or (fact.fact_id,)).intersection(
                    selected_fact.source_record_ids or (selected_fact.fact_id,)
                )
                for selected_fact in selected
            )
        ):
            continue
        selected.append(fact)
        selected_ids.add(fact.fact_id)
        selected_topics.add(fact.topic)
    return sorted(
        selected,
        key=lambda fact: (
            phase_order.get(fact.operational_phase, 10),
            SOURCE_PRIORITY.get(fact.source, 9),
            -fact.importance,
            fact.fact_id,
        ),
    )


TYPICAL_NO_DATA_TEXT_ZH = "当前资料未列出明确典型不安全事件。"
TYPICAL_NO_DATA_TEXT_EN = (
    "The current source does not list a specific typical unsafe event."
)
TYPICAL_NO_DATA_RE = re.compile(
    r"^(?:目前数据库中)?(?:无数据|暂无数据|未收录|无|N/?A|未发现明确事件)$",
    re.IGNORECASE,
)


def is_typical_no_data(value: str) -> bool:
    compact = re.sub(r"[\s。；;，,]+", "", normalize_text(value))
    return bool(TYPICAL_NO_DATA_RE.fullmatch(compact))


def bilingual_typical_facts(
    airport: str,
    risks: list[str],
    threats: list[str],
    month: int,
    max_items: int,
    source_records: list[dict[str, object]] | None = None,
    event: CalendarEvent | DutyContext | None = None,
    target: date | None = None,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    del risks, threats
    canonical = canonical_airport_name(airport)
    manual_records = [
        record
        for record in (source_records or [])
        if str(record.get("source")) in {"PDF", "TXT"}
        and str(record.get("category")) == "typical"
    ]
    facts = source_record_facts(
        canonical,
        manual_records,
        category="typical",
        exclusion_log=exclusion_log,
    )
    placeholders = [fact for fact in facts if is_typical_no_data(fact.zh)]
    real_facts = [fact for fact in facts if not is_typical_no_data(fact.zh)]
    if event is not None:
        applicable: list[BilingualFact] = []
        for fact in real_facts:
            filtered = filter_fact_for_duty(
                fact,
                event,
                target or date(2000, month, 1),
                exclusion_log,
            )
            if filtered is not None:
                applicable.append(filtered)
        real_facts = applicable
    if real_facts:
        return real_facts[:max_items]
    if placeholders:
        source = placeholders[0]
        return [
            replace(
                source,
                fact_id=f"{canonical}_typical_no_data",
                text_zh=TYPICAL_NO_DATA_TEXT_ZH,
                text_en=TYPICAL_NO_DATA_TEXT_EN,
                category="typical_no_data",
                source_fact_ids=tuple(
                    unique(
                        [
                            fact_id
                            for fact in placeholders
                            for fact_id in (fact.source_fact_ids or (fact.fact_id,))
                        ]
                    )
                ),
            )
        ]
    return []


PROFILE_LABEL_RE = re.compile(
    r"^(?P<label>机场分类|高原机场|地形)\s*[:：]\s*(?P<value>.+)$"
)
SOURCE_LABEL_RE = re.compile(
    r"^[.。；;，,\s]*(?P<label>机场分类|高原机场|特殊复杂程序|地形|常用程序|"
    r"指挥特点|注意事项|气象特点|道面特点|其他威胁|运行特点)"
    r"\s*[:：]\s*(?P<value>.+)$"
)


def _expand_chinese_unit(value: str) -> str:
    def expand(match: re.Match[str]) -> str:
        return f"{int(match.group('amount')) * 10000}{match.group('unit')}"

    return re.sub(
        r"(?<!\d)(?P<amount>\d+)\s*万\s*(?P<unit>英尺|米)",
        expand,
        value,
    )


def _polish_source_chinese(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[A-Z0-9])", "", text)
    text = re.sub(r"(?<=[A-Z0-9])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=\d)\s+(?=(?:号|米|英尺|海里|公里|节))", "", text)
    if re.search(r"[\u4e00-\u9fff]", text):
        text = text.replace(",", "，")
    return text


def naturalize_source_fact(value: str) -> str:
    text = strip_terminal_punct(normalize_text(value))
    match = SOURCE_LABEL_RE.match(text)
    if not match:
        return _polish_source_chinese(
            _expand_chinese_unit(text).rstrip("。") + "。"
        )
    label = match.group("label")
    detail = _expand_chinese_unit(match.group("value").strip(" 。"))
    if label in {"机场分类", "高原机场"}:
        return _polish_source_chinese(f"该机场属于{detail}。")
    if label == "特殊复杂程序":
        return _polish_source_chinese(f"特殊程序{detail}。")
    if label != "地形":
        return _polish_source_chinese(detail.rstrip("。") + "。")
    detail = detail.replace("～", "至").replace("—", "至")
    sector = re.match(r"(?P<sector>\d+°至\d+°)(?P<rest>.*)", detail)
    if sector and "地形" not in detail:
        rest = sector.group("rest").lstrip("，,")
        return _polish_source_chinese(
            f"{sector.group('sector')}方向存在地形"
            + (f"，{rest}" if rest else "")
            + "。"
        )
    return _polish_source_chinese(f"地形方面，{detail}。")


def merge_fact_paragraph(
    facts: list[BilingualFact],
    text_zh: str,
    *,
    topic: str,
) -> BilingualFact:
    source_fact_ids = tuple(
        unique(
            [
                fact_id
                for fact in facts
                for fact_id in (fact.source_fact_ids or (fact.fact_id,))
            ]
        )
    )
    source_text = " ".join(
        unique([fact.source_text_zh or fact.text_zh for fact in facts])
    )
    source_record_ids = tuple(
        unique(
            [
                record_id
                for fact in facts
                for record_id in (fact.source_record_ids or (fact.fact_id,))
            ]
        )
    )
    source_clauses = tuple(
        unique(
            [
                clause
                for fact in facts
                for clause in (fact.source_clauses or (fact.text_zh,))
                if clause.strip()
            ]
        )
    )
    source_original_texts = tuple(
        unique(
            [
                original
                for fact in facts
                for original in (
                    fact.source_original_texts
                    or (fact.source_text_zh or fact.text_zh,)
                )
                if original.strip()
            ]
        )
    )
    source = min(facts, key=lambda fact: SOURCE_PRIORITY.get(fact.source, 9)).source
    english_parts = [fact.text_en.strip().rstrip(".") for fact in facts if fact.text_en.strip()]
    excluded_pairs = [
        (clause, fact.exclusion_reasons[index])
        for fact in facts
        for index, clause in enumerate(fact.excluded_source_clauses)
        if index < len(fact.exclusion_reasons)
    ]
    first = facts[0]
    return BilingualFact(
        fact_id="paragraph:" + "+".join(source_fact_ids),
        text_zh=text_zh.rstrip("。") + "。",
        text_en=". ".join(english_parts) + ("." if english_parts else ""),
        airport=first.airport,
        source_file=" | ".join(unique([fact.source_file for fact in facts if fact.source_file])),
        source=source,
        source_page=",".join(unique([fact.source_page for fact in facts if fact.source_page])),
        source_heading=" | ".join(unique([fact.source_heading for fact in facts if fact.source_heading])),
        source_section=" | ".join(unique([fact.source_section for fact in facts if fact.source_section])),
        operational_phase=first.operational_phase,
        airport_specific=all(fact.airport_specific for fact in facts),
        category="core",
        role_scope=tuple(unique([role for fact in facts for role in fact.role_scope])),
        importance=max(fact.importance for fact in facts),
        semantic_key="paragraph:" + "+".join(source_fact_ids),
        source_text_zh=source_text,
        operational_condition=tuple(
            unique([item for fact in facts for item in fact.operational_condition])
        ),
        applicability=tuple(
            unique([item for fact in facts for item in fact.applicability])
        ),
        risk=tuple(unique([item for fact in facts for item in fact.risk])),
        mitigation=tuple(
            unique([item for fact in facts for item in fact.mitigation])
        ),
        restriction=tuple(
            unique([item for fact in facts for item in fact.restriction])
        ),
        excluded_source_clauses=tuple(pair[0] for pair in excluded_pairs),
        exclusion_reasons=tuple(pair[1] for pair in excluded_pairs),
        season_scope=tuple(
            month
            for month in range(1, 13)
            if any(month in fact.season_scope for fact in facts)
        ),
        flight_scope=tuple(unique([number for fact in facts for number in fact.flight_scope])),
        route_scope=tuple(
            dict.fromkeys([route for fact in facts for route in fact.route_scope])
        ),
        topic=topic,
        source_fact_ids=source_fact_ids,
        source_record_ids=source_record_ids,
        source_clauses=source_clauses,
        source_original_texts=source_original_texts,
        render_role=first.render_role,
    )


PARAGRAPH_TOPIC_PRIORITY = {
    "departure": (
        "takeoff",
        "clearance",
        "ground_departure",
        "departure_performance",
        "departure_atc",
        "departure",
        "weather",
        "terrain",
        "special",
    ),
    "arrival": (
        "arrival_energy",
        "approach_intercept",
        "approach",
        "weather",
        "terrain",
        "landing",
        "landing_ground",
        "special",
    ),
    "transit": (
        "arrival_energy",
        "approach_intercept",
        "approach",
        "landing",
        "landing_ground",
        "clearance",
        "ground_departure",
        "takeoff",
        "departure_performance",
        "departure_atc",
        "departure",
        "weather",
        "terrain",
        "special",
    ),
}


def source_grounded_paragraph_topic(fact: BilingualFact, role: str) -> str:
    text = normalize_text(fact.text_zh)
    upper = text.upper()
    phase = fact.operational_phase
    if phase == "weather" or any(
        token in text for token in ("雷暴", "风切变", "大风", "结冰", "沙尘")
    ):
        return "weather"
    if phase == "terrain" or any(token in upper for token in ("地形", "MSA", "CFIT")):
        return "terrain"
    if any(token in text for token in ("擦机尾", "离地姿态", "拉杆速率")):
        return "takeoff"
    if phase in {"clearance", "preparation"} or any(
        token in upper for token in ("PDC", "放行", "ACARS")
    ):
        return "clearance"
    if phase in {"ground", "landing_ground"}:
        return "ground_departure" if role == "departure" else "landing_ground"
    if phase in {"departure", "initial_climb"}:
        if any(token in upper for token in ("FLYSMART", "FLY SMART", "性能", "载重")):
            return "departure_performance"
        if any(
            token in text
            for token in ("雷达引导", "换频", "塔台", "管制", "直飞", "脱播")
        ):
            return "departure_atc"
        return "departure"
    if phase == "arrival":
        if any(
            token in text
            for token in ("能量", "下降", "剖面", "高度", "距离短", "调速")
        ):
            return "arrival_energy"
        return "approach"
    if phase == "approach":
        if any(
            token in upper
            for token in ("盲降", "ILS", "截获", "下滑道", "航向道", "五边")
        ):
            return "approach_intercept"
        return "approach"
    if phase == "landing":
        return "landing"
    return fact.topic if fact.topic in {"weather", "terrain"} else "special"


def _paragraph_topic_family(topic: str) -> str:
    if topic in {
        "clearance",
        "ground_departure",
        "takeoff",
        "departure_performance",
        "departure_atc",
        "departure",
    }:
        return "departure"
    if topic in {
        "arrival_energy",
        "approach_intercept",
        "approach",
        "landing",
        "landing_ground",
    }:
        return "arrival"
    return topic


def _paragraph_overlap_markers(value: str) -> set[str]:
    text = normalize_text(value).upper()
    markers = _source_clause_identifiers(text)
    markers.update(re.findall(r"(?<![A-Z0-9])[A-Z]{2,8}(?![A-Z0-9])", text))
    for token in (
        "五边",
        "顺风",
        "调速",
        "剖面",
        "盲降",
        "雷达引导",
        "自主建立",
        "下滑道",
        "航向道",
        "等待",
        "FLYSMART",
        "PDC",
        "机位",
        "滑行",
    ):
        if token.upper() in text:
            markers.add(token.upper())
    return markers


def _facts_are_duplicates(first: BilingualFact, second: BilingualFact) -> bool:
    if _paragraph_topic_family(first.topic) != _paragraph_topic_family(second.topic):
        return False
    first_key = compact_key(first.text_zh).upper()
    second_key = compact_key(second.text_zh).upper()
    if not first_key or not second_key:
        return False
    if first_key in second_key or second_key in first_key:
        return True
    overlap = _paragraph_overlap_markers(first.text_zh) & _paragraph_overlap_markers(
        second.text_zh
    )
    return len(overlap) >= 4


def _richer_fact(first: BilingualFact, second: BilingualFact) -> BilingualFact:
    def richness(fact: BilingualFact) -> tuple[int, int, int]:
        return (
            len(critical_fact_tokens(fact.text_zh))
            + len(_paragraph_overlap_markers(fact.text_zh)),
            len(normalize_text(fact.text_zh)),
            -SOURCE_PRIORITY.get(fact.source, 9),
        )

    return max((first, second), key=richness)


def merge_duplicate_fact_paragraph(
    first: BilingualFact,
    second: BilingualFact,
) -> BilingualFact:
    richer = _richer_fact(first, second)
    omitted = second if richer is first else first
    merged = merge_fact_paragraph(
        [first, second],
        richer.text_zh,
        topic=richer.topic,
    )
    omitted_clauses = omitted.source_clauses or (omitted.text_zh,)
    return replace(
        merged,
        source_clauses=richer.source_clauses or (richer.text_zh,),
        excluded_source_clauses=tuple(
            [*merged.excluded_source_clauses, *omitted_clauses]
        ),
        exclusion_reasons=tuple(
            [
                *merged.exclusion_reasons,
                *("重复事实由信息更完整的来源表达" for _ in omitted_clauses),
            ]
        ),
        operational_condition=richer.operational_condition,
        applicability=richer.applicability,
        risk=richer.risk,
        mitigation=richer.mitigation,
        restriction=richer.restriction,
    )


def _fact_sequence(fact: BilingualFact) -> tuple[int, str]:
    match = re.search(r"_(\d+)$", fact.fact_id)
    return (int(match.group(1)) if match else 10**9, fact.fact_id)


def _join_source_sentences(facts: list[BilingualFact]) -> str:
    sentences = unique(
        naturalize_source_fact(fact.text_zh)
        for fact in sorted(facts, key=_fact_sequence)
        if _source_clause_has_substance(fact.text_zh)
    )
    return "".join(sentences)


def organize_source_grounded_briefing_paragraphs(
    facts: list[BilingualFact],
    role: str,
    *,
    max_paragraphs: int = 6,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    """Edit source-backed facts into traceable, topic-oriented paragraphs."""
    if not facts:
        return []

    usable: list[BilingualFact] = []
    for fact in facts:
        cleaned = clean_output_fact(fact.text_zh)
        if not _source_clause_has_substance(cleaned):
            if exclusion_log is not None:
                exclusion_log.append(
                    exclusion_log_entry(
                        fact,
                        fact.source_text_zh or fact.text_zh,
                        "清洗后无实质运行内容",
                    )
                )
            continue
        topic = source_grounded_paragraph_topic(fact, role)
        usable.append(
            replace(
                fact,
                text_zh=naturalize_source_fact(fact.text_zh),
                topic=topic,
                render_role=role,
                source_clauses=fact.source_clauses or (fact.text_zh,),
                source_original_texts=(
                    fact.source_original_texts
                    or (fact.source_text_zh or fact.text_zh,)
                ),
                source_record_ids=fact.source_record_ids or (fact.fact_id,),
            )
        )

    def profile_source_text(fact: BilingualFact) -> str:
        cleaned, _ = strip_source_reference_clauses(fact.source_clauses[0])
        return strip_terminal_punct(normalize_text(cleaned))

    profile_facts = [
        fact for fact in usable if PROFILE_LABEL_RE.match(profile_source_text(fact))
    ]
    if profile_facts:
        classification_values: list[str] = []
        terrain_sentences: list[str] = []
        for fact in profile_facts:
            match = PROFILE_LABEL_RE.match(profile_source_text(fact))
            if not match:
                continue
            if match.group("label") in {"机场分类", "高原机场"}:
                classification_values.append(
                    _expand_chinese_unit(match.group("value").strip(" 。"))
                )
            else:
                terrain_sentences.append(naturalize_source_fact(fact.source_clauses[0]))
        classifications = unique(classification_values)
        classifications.sort(key=lambda value: (0 if "高原" in value else 1, value))
        parts = ([f"该机场属于{'和'.join(classifications)}。"] if classifications else [])
        parts.extend(terrain_sentences)
        profile_paragraph = merge_fact_paragraph(
            profile_facts,
            "".join(parts),
            topic="terrain",
        )
        usable = [fact for fact in usable if fact not in profile_facts]
        usable.append(replace(profile_paragraph, render_role=role))

    # First reunite complete, role-compatible clauses from the same source record.
    record_groups: list[list[BilingualFact]] = []
    for fact in usable:
        record_id = (fact.source_record_ids or (fact.fact_id,))[0]
        match_index: int | None = None
        for index, grouped in enumerate(record_groups):
            grouped_record_id = (
                grouped[0].source_record_ids or (grouped[0].fact_id,)
            )[0]
            if grouped_record_id != record_id:
                continue
            shared_markers = (
                _paragraph_overlap_markers("".join(item.text_zh for item in grouped))
                & _paragraph_overlap_markers(fact.text_zh)
            )
            dependent_control = bool(
                re.match(
                    r"^(?:机组|建议|注意|应|需|必须|不得|严禁|未经|可以|同时|随后|然后)",
                    clean_output_fact(fact.text_zh),
                )
            )
            if (
                _paragraph_topic_family(grouped[-1].topic)
                == _paragraph_topic_family(fact.topic)
                and (len(shared_markers) >= 2 or dependent_control)
            ):
                match_index = index
                break
        if match_index is None:
            record_groups.append([fact])
        else:
            record_groups[match_index].append(fact)
    candidates: list[BilingualFact] = []
    for grouped in record_groups:
        if len(grouped) == 1:
            candidates.append(grouped[0])
            continue
        topic = min(
            grouped,
            key=lambda fact: PARAGRAPH_TOPIC_PRIORITY[role].index(fact.topic)
            if fact.topic in PARAGRAPH_TOPIC_PRIORITY[role]
            else 99,
        ).topic
        candidates.append(
            merge_fact_paragraph(
                grouped,
                _join_source_sentences(grouped),
                topic=topic,
            )
        )

    # Collapse duplicate facts while retaining every contributing source ID.
    deduplicated: list[BilingualFact] = []
    for candidate in candidates:
        duplicate_index = next(
            (
                index
                for index, current in enumerate(deduplicated)
                if _facts_are_duplicates(current, candidate)
            ),
            None,
        )
        if duplicate_index is None:
            deduplicated.append(candidate)
            continue
        current = deduplicated[duplicate_index]
        deduplicated[duplicate_index] = merge_duplicate_fact_paragraph(
            current,
            candidate,
        )

    # Related source-backed facts may share a paragraph; unrelated topics never do.
    paragraphs: list[BilingualFact] = []
    for candidate in deduplicated:
        merge_index = next(
            (
                index
                for index, current in enumerate(paragraphs)
                if current.topic == candidate.topic
                and current.topic
                in {"clearance", "weather", "terrain", "ground_departure", "landing_ground"}
                and current.importance < 99
                and candidate.importance < 99
                and not current.restriction
                and not candidate.restriction
                and len(current.text_zh) + len(candidate.text_zh) <= 260
            ),
            None,
        )
        if merge_index is None:
            paragraphs.append(candidate)
            continue
        current = paragraphs[merge_index]
        paragraphs[merge_index] = merge_fact_paragraph(
            [current, candidate],
            _join_source_sentences([current, candidate]),
            topic=current.topic,
        )

    order = PARAGRAPH_TOPIC_PRIORITY[role]
    paragraphs.sort(
        key=lambda fact: (
            0 if fact.importance >= 92 else 1,
            order.index(fact.topic) if fact.topic in order else len(order),
            -fact.importance,
            SOURCE_PRIORITY.get(fact.source, 9),
            fact.fact_id,
        )
    )
    return paragraphs[:max_paragraphs]


def organize_core_fact_paragraphs(
    facts: list[BilingualFact],
    role: str = "transit",
    *,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    """Compatibility wrapper for the source-grounded paragraph editor."""
    return organize_source_grounded_briefing_paragraphs(
        facts,
        role,
        exclusion_log=exclusion_log,
    )


def prepare_operational_facts(
    event: CalendarEvent | DutyContext,
    airport: str,
    target: date,
    candidates: list[BilingualFact],
    *,
    max_items: int,
    exclusion_log: list[dict[str, object]] | None,
) -> list[BilingualFact]:
    role = airport_role(event, airport)
    applicable: list[BilingualFact] = []
    for candidate in candidates:
        prepared = attach_source_semantics(candidate)
        filtered = filter_fact_for_duty(prepared, event, target, exclusion_log)
        if filtered is not None:
            applicable.append(filtered)
    selected = select_airport_facts(
        airport,
        role,
        applicable,
        max_items=max(len(applicable), max_items),
        exclusion_log=exclusion_log,
    )
    return organize_core_fact_paragraphs(
        selected,
        role,
        exclusion_log=exclusion_log,
    )


def airport_operational_facts(
    event: CalendarEvent | DutyContext,
    airport: str,
    source_items: list[str],
    target: date,
    source_records: list[dict[str, object]] | None = None,
    exclusion_log: list[dict[str, object]] | None = None,
) -> list[BilingualFact]:
    del source_items
    canonical = canonical_airport_name(airport)
    role = airport_role(event, airport)
    if canonical == "新加坡樟宜" and role in ("departure", "transit"):
        candidates = [bind_catalog_fact(fact) for fact in SINGAPORE_DEPARTURE_FACTS]
    elif canonical == "上海浦东":
        candidates: list[BilingualFact] = []
        if role in ("arrival", "transit"):
            candidates.extend(
                bind_catalog_fact(fact) for fact in PUDONG_ARRIVAL_FACTS
            )
        if role in ("departure", "transit"):
            candidates.extend(
                bind_catalog_fact(fact) for fact in PUDONG_DEPARTURE_FACTS
            )
    elif canonical in CURATED_CORE_THREATS and canonical in CURATED_CORE_ENGLISH:
        chinese = CURATED_CORE_THREATS[canonical]
        english = CURATED_CORE_ENGLISH[canonical]
        phases = CURATED_CORE_PHASES.get(canonical, ())
        source_pages = CURATED_CORE_SOURCE_PAGES.get(canonical, ())
        location = AIRPORT_SOURCE_LOCATIONS.get(canonical, {})
        candidates = [
            attach_source_semantics(
                BilingualFact(
                    f"{canonical}_core_{index}",
                    zh,
                    en,
                    airport=canonical,
                    source_file=str(
                        location.get("source_file", AIRPORT_MANUAL_FILE)
                    ),
                    source="CURATED",
                    source_page=(
                        source_pages[index - 1]
                        if index <= len(source_pages)
                        else str(location.get("source_page", "N/A"))
                    ),
                    source_heading=str(location.get("source_heading", canonical)),
                    source_section=f"{canonical}人工精选／核心威胁第{index}条",
                    operational_phase=(
                        phases[index - 1]
                        if index <= len(phases)
                        else "unspecified"
                    ),
                    airport_specific=True,
                    category="core",
                    importance=(
                        99
                        if any(
                            token in zh
                            for token in (
                                "GPS",
                                "禁止",
                                "必须",
                                "高度限制",
                                "速度限制",
                                "地形",
                                "CFIT",
                            )
                        )
                        else (90 if index <= 2 else 75)
                    ),
                    semantic_key=f"{canonical}_core_{index}",
                )
            )
            for index, (zh, en) in enumerate(zip(chinese, english), start=1)
        ]
    elif canonical == "丽江三义":
        candidates = [bind_catalog_fact(fact) for fact in LIJIANG_CORE_FACTS]
    else:
        candidates = source_record_facts(
            canonical,
            source_records or [],
            category="core",
            exclusion_log=exclusion_log,
        )
    return prepare_operational_facts(
        event,
        canonical,
        target,
        candidates,
        max_items=8 if role == "transit" else 5,
        exclusion_log=exclusion_log,
    )


def _first_operational_sentence(value: str) -> str:
    return re.split(r"(?<=[。.!?])\s*|；|;", value.strip(), maxsplit=1)[0].strip()


def flight_risk_facts(
    event: CalendarEvent | DutyContext,
    target: date,
    core_facts: dict[str, list[BilingualFact]] | None = None,
) -> list[BilingualFact]:
    del target
    facts: list[BilingualFact] = []
    core_facts = core_facts or {}
    for airport in unique([item for item in event.route if item]):
        role = airport_role(event, airport)
        role_zh = "起飞" if role == "departure" else "落地"
        role_en = "departure from" if role == "departure" else "arrival at"
        selected = core_facts.get(airport, [])[:2]
        for fact in selected:
            summary_zh = _first_operational_sentence(fact.zh)
            summary_en = _first_operational_sentence(fact.en)
            if critical_fact_tokens(summary_zh) != critical_fact_tokens(summary_en):
                summary_zh = fact.zh
                summary_en = fact.en
            phase_zh = {
                "preparation": "驾驶舱准备",
                "clearance": "放行",
                "ground": "地面运行",
                "departure": "离场程序",
                "initial_climb": "初始爬升",
                "arrival": "进场和能量管理",
                "approach": "进近",
                "weather": "天气",
                "landing": "着陆",
            }.get(fact.operational_phase, "运行")
            phase_en = {
                "preparation": "cockpit-preparation",
                "clearance": "clearance",
                "ground": "ground-operations",
                "departure": "departure-procedure",
                "initial_climb": "initial-climb",
                "arrival": "arrival and energy-management",
                "approach": "approach",
                "weather": "weather",
                "landing": "landing",
            }.get(fact.operational_phase, "operational")
            phase_article = "an" if phase_en[0].lower() in "aeiou" else "a"
            summary_zh = (
                f"我们识别到{short_airport_name(airport)}{role_zh}阶段的{phase_zh}风险："
                f"{strip_terminal_punct(summary_zh)}"
            )
            summary_en = (
                f"For {role_en} {english_airport_name(airport)}, "
                f"we have identified {phase_article} {phase_en} risk: "
                f"{summary_en.strip().rstrip('.')}"
            )
            facts.append(
                replace(
                    fact,
                    fact_id=f"risk_{fact.fact_id}",
                    text_zh=summary_zh,
                    text_en=summary_en,
                    category="risk",
                )
            )
    return facts[:5]


def _checkin_time(event: CalendarEvent) -> str:
    match = re.search(r"\b(\d{2}:\d{2})\b", event.checkin or "")
    return match.group(1) if match else ""


def clean_output_fact(value: str) -> str:
    text = strip_terminal_punct(value)
    text = re.sub(r"^[.。；;，,\s]+", "", text)
    text = re.sub(
        r"^(?:常用程序|指挥特点|注意事项|气象特点|道面特点|其他威胁|运行特点)\s*[:：]\s*",
        "",
        text,
    )
    text = re.sub(r"^[（(]?\d+[）).、]\s*", "", text)
    text = re.sub(r"/\s+", "/", text)
    return normalize_text(text)


def duty_risk_text(
    duty: CalendarEvent | DutyContext,
    records: list[dict],
    core_facts: dict[str, list[BilingualFact]],
    weather_sentence: str,
) -> str:
    del core_facts  # Core airport facts belong only in the dedicated threat section.
    flights = list(duty.events) if isinstance(duty, DutyContext) else [duty]
    sentences: list[str] = []
    first, last = flights[0], flights[-1]
    checkin = _checkin_time(first)
    if checkin and int(checkin.split(":", 1)[0]) < 6:
        sentences.append(
            f"我们识别到本次为早班，{checkin}签到，"
            f"任务时段{first.start:%H:%M}-{last.end:%H:%M}，"
            "应提前做好休息和精力管理"
        )
    elif last.end.date() > first.start.date():
        sentences.append(
            f"我们识别到本次任务从{first.start:%H:%M}"
            f"持续至次日{last.end:%H:%M}，应重点做好跨夜精力管理"
        )
    if len(flights) > 1:
        turnarounds = []
        for previous, following in zip(flights, flights[1:]):
            minutes = int((following.start - previous.end).total_seconds() // 60)
            if minutes >= 0:
                turnarounds.append(
                    f"{airport_with_suffix(previous.route[1])}过站{minutes}分钟"
                )
        detail = "、".join(turnarounds)
        sentences.append(
            f"我们识别到本次为{len(flights)}段连续任务"
            + (f"，{detail}" if detail else "")
            + "，应在过站期间合理分配准备和恢复时间"
        )
    for record in records:
        if not record.get("within"):
            sentences.append(
                f"我们识别到近3个月未运行过"
                f"{airport_with_suffix(record.get('airport', ''))}，"
                "应重点复习最新机场特点和有效程序"
            )
    paragraphs: list[str] = []
    if sentences:
        paragraphs.append("；".join(unique(sentences)) + "。")
    weather = weather_sentence.strip()
    if not weather:
        weather = "。".join(
            f"{airport_with_suffix(airport)}航班时段天气以航前最新TAF/METAR及放行资料为准"
            for airport in duty.route
        ) + "。"
    elif not weather.endswith("。"):
        weather += "。"
    paragraphs.append(weather)
    paragraphs.append(
        "最新有效PIB/NOTAM以航前放行资料为准，不对尚未取得的通告内容作推断。"
    )
    return "".join(paragraphs)


FACT_GUARD_TOKENS = (
    "IRS",
    "SID",
    "STAR",
    "ATC",
    "PDC",
    "TOBT",
    "DUDIS",
    "FOLLOWGREEN",
    "M771",
    "G4",
    "MERSING9B",
    "VMR9B",
    "MERSING6A",
    "VMR6A",
    "FL120",
    "MERSING",
    "DOLOX",
    "WSSS",
    "ZSPD",
    "CPDLC",
    "MCDU",
    "TA/RA",
    "ATIS",
    "ADGS",
    "FL200",
    "VFENEXT",
    "FAF",
    "GPS",
    "ADS-B",
    "CN104",
)


def critical_fact_tokens(value: str) -> set[str]:
    upper = (value or "").upper()
    tokens: set[str] = set()
    for token in FACT_GUARD_TOKENS:
        pattern = re.escape(token).replace(r"\ ", r"\s+")
        if re.search(rf"(?<![A-Z0-9]){pattern}(?![A-Z0-9])", upper):
            tokens.add(re.sub(r"\s+", "", token))

    compact = re.sub(r"\s+", "", upper)
    normalized_units = compact
    for source, replacement in (
        ("英尺", "FT"),
        ("节", "KT"),
        ("秒", "S"),
        ("SECONDS", "S"),
        ("SECOND", "S"),
        ("分钟", "MIN"),
        ("MINUTES", "MIN"),
        ("MINUTE", "MIN"),
        ("米", "M"),
    ):
        normalized_units = normalized_units.replace(source, replacement)
    tokens.update(
        match.upper()
        for match in re.findall(
            r"-?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?(?:FT|KT|MIN|S|M|%)",
            normalized_units,
        )
    )
    return tokens


SOURCE_OPERATIONAL_ANCHORS = (
    "中档刹车",
    "关空调",
    "FLY SMART",
    "滑行速度",
    "入口内移",
    "着陆可用距离",
    "载重限制",
    "地形",
    "程序",
    "起飞",
    "离场",
    "进场",
    "进近",
    "着陆",
    "滑行",
    "速度",
    "高度",
    "距离",
    "刹车",
    "PAPI",
    "VOR",
    "CFIT",
)


def source_semantic_anchors(value: str) -> set[str]:
    text = normalize_text(value)
    upper = text.upper()
    anchors = {
        token.upper()
        for token in SOURCE_OPERATIONAL_ANCHORS
        if token.upper() in upper
    }
    anchors.update(
        match.upper().replace(" ", "")
        for match in re.findall(
            r"(?<!\d)\d{2}号(?:跑道)?|"
            r"(?<!\d)\d+(?:\.\d+)?\s*(?:米|英尺|FT|M|节|秒|分钟|公里|%)",
            text,
            flags=re.IGNORECASE,
        )
    )
    anchors.update(
        f"{runway}号"
        for runway in re.findall(
            r"(?<!\d)(\d{2})(?=号|和\d{2}号|、\d{2}号)",
            text,
        )
    )
    return anchors


def source_literal_tokens(value: str) -> set[str]:
    """Return source literals that an editor must never invent."""
    text = _expand_chinese_unit(normalize_text(value)).upper().replace(" ", "")
    tokens = set(
        re.findall(
            r"(?<![A-Z0-9])[A-Z]{2,10}\d*(?![A-Z0-9])|"
            r"(?<!\d)\d+(?:\.\d+)?(?:[-—–至到~～]\d+(?:\.\d+)?)?"
            r"(?:英尺|米|海里|公里|节|秒|分钟|FT|NM|KM|M|KT|%)?",
            text,
        )
    )
    return {token.replace("—", "-").replace("–", "-").replace("至", "-") for token in tokens}


def validate_source_semantic_preservation(fact: BilingualFact) -> list[str]:
    """Ensure a rendered source fact retains explicit source controls and facts."""
    if not fact.source_text_zh.strip():
        return []

    rendered = normalize_text(fact.text_zh)
    semantic_source = " ".join(fact.source_clauses) or fact.source_text_zh
    excluded_anchors: set[str] = set()
    for clause in fact.excluded_source_clauses:
        excluded_anchors.update(source_semantic_anchors(clause))
    required_anchors = source_semantic_anchors(semantic_source) - excluded_anchors
    rendered_anchors = source_semantic_anchors(rendered)
    missing_anchors = sorted(required_anchors - rendered_anchors)
    errors = [
        f"来源语义未完整保留：{fact.fact_id}缺少{','.join(missing_anchors)}"
    ] if missing_anchors else []

    source_literals = source_literal_tokens(semantic_source)
    rendered_literals = source_literal_tokens(rendered)
    added_literals = sorted(rendered_literals - source_literals)
    if added_literals:
        errors.append(
            f"来源语义新增内容：{fact.fact_id}新增{','.join(added_literals)}"
        )

    source_controls = "；".join([*fact.mitigation, *fact.restriction])
    control_groups = (
        (r"禁止|不得|严禁", r"禁止|不得|严禁", "禁止性要求"),
        (r"只能|仅允许", r"只能|仅允许", "唯一允许范围"),
        (r"必须", r"必须", "强制要求"),
        (r"限制", r"限制", "限制条件"),
        (r"应|建议|注意|需", r"应|建议|注意|需", "控制措施"),
    )
    for source_pattern, rendered_pattern, label in control_groups:
        if re.search(source_pattern, source_controls) and not re.search(
            rendered_pattern, rendered
        ):
            errors.append(f"来源语义未完整保留：{fact.fact_id}缺少{label}")
    rendered_controls = {
        label
        for pattern, _, label in control_groups
        if re.search(pattern, rendered)
    }
    source_control_labels = {
        label
        for pattern, _, label in control_groups
        if re.search(pattern, source_controls)
    }
    invented_controls = sorted(rendered_controls - source_control_labels)
    if invented_controls:
        errors.append(
            f"来源语义新增控制措施：{fact.fact_id}新增{','.join(invented_controls)}"
        )
    return errors


def validate_bilingual_facts(facts: list[BilingualFact]) -> list[str]:
    errors: list[str] = []
    for fact in facts:
        zh_tokens = critical_fact_tokens(fact.zh)
        en_tokens = critical_fact_tokens(fact.en)
        if zh_tokens != en_tokens:
            errors.append(
                f"中英文关键事实不一致：{fact.key}：中文{sorted(zh_tokens)}，英文{sorted(en_tokens)}"
            )
    return errors


def validate_airport_fact_bindings(
    airport: str,
    facts: list[BilingualFact],
) -> list[str]:
    canonical = canonical_airport_name(airport)
    errors: list[str] = []
    for fact in facts:
        if canonical_airport_name(fact.airport) != canonical:
            errors.append(
                f"机场事实跨机场污染：{canonical}引用了{fact.airport or '未标明机场'}／{fact.fact_id}"
            )
        if fact.source not in {"PDF", "TXT", "supplement", "CURATED"}:
            errors.append(f"机场事实来源无效：{fact.fact_id}／{fact.source}")
        if not fact.source_file.strip():
            errors.append(f"机场事实缺少来源文件：{fact.fact_id}")
        if not fact.source_page.strip():
            errors.append(f"机场事实缺少来源页码：{fact.fact_id}")
        if not fact.source_heading.strip():
            errors.append(f"机场事实缺少来源章节标题：{fact.fact_id}")
        if not fact.source_section.strip():
            errors.append(f"机场事实缺少来源章节：{fact.fact_id}")
        if not fact.operational_phase.strip():
            errors.append(f"机场事实缺少运行阶段：{fact.fact_id}")
        if not fact.text_zh.strip():
            errors.append(f"机场事实缺少中文内容：{fact.fact_id}")
        if len(fact.excluded_source_clauses) != len(fact.exclusion_reasons):
            errors.append(f"机场事实排除条款缺少原因：{fact.fact_id}")
    return errors


def render_chinese_briefing(
    event: CalendarEvent | DutyContext,
    target: date,
    profile: dict,
    records: list[dict],
    typical_facts: dict[str, list[BilingualFact]],
    core_facts: dict[str, list[BilingualFact]],
    weather_sentence: str = "",
) -> str:
    sections: list[str] = [group_personal_intro(profile, records)]
    feedback = feedback_text(profile)
    if feedback:
        sections.append(feedback)

    del target, weather_sentence

    airports = unique([airport for airport in event.route if airport])
    for airport in airports:
        items = [
            fact
            for fact in typical_facts.get(airport, [])
            if fact.category != "typical_no_data" and clean_output_fact(fact.zh)
        ]
        if not items:
            continue
        typical_text = "\n\n".join(
            clean_output_fact(fact.zh) + "。" for fact in items
        )
        sections.append(
            f"{airport_with_suffix(airport)}典型不安全事件：\n{typical_text}"
        )

    core_lines = ["核心威胁："]
    for airport in airports:
        paragraphs = "\n\n".join(
            clean_output_fact(fact.zh) + "。"
            for fact in core_facts[airport]
            if clean_output_fact(fact.zh)
        )
        core_lines.append(f"{airport_with_suffix(airport)}：\n{paragraphs}")
    sections.append("\n\n".join(core_lines))
    return "\n\n".join(section.strip() for section in sections if section.strip()).strip() + "\n"


def render_english_briefing(
    event: CalendarEvent | DutyContext,
    target: date,
    profile: dict,
    records: list[dict],
    typical_facts: dict[str, list[BilingualFact]],
    core_facts: dict[str, list[BilingualFact]],
) -> str:
    sections: list[str] = [english_personal_intro(profile, records)]
    feedback = feedback_text_en(profile)
    if feedback:
        sections.append(feedback)

    del target

    airports = unique([airport for airport in event.route if airport])
    for airport in airports:
        items = [
            fact
            for fact in typical_facts.get(airport, [])
            if fact.category != "typical_no_data" and fact.en.strip()
        ]
        if not items:
            continue
        paragraphs = "\n\n".join(
            fact.en.strip().rstrip(".") + "." for fact in items
        )
        sections.append(
            f"{english_airport_name(airport)} Airport typical unsafe events:\n{paragraphs}"
        )

    core_lines = ["Core threats:"]
    for airport in airports:
        paragraphs = "\n\n".join(
            fact.en.strip().rstrip(".") + "."
            for fact in core_facts[airport]
            if fact.en.strip()
        )
        core_lines.append(f"{english_airport_name(airport)} Airport:\n{paragraphs}")
    sections.append("\n\n".join(core_lines))
    return "\n\n".join(section.strip() for section in sections if section.strip()).strip() + "\n"


def briefing_fact_sets(
    event: CalendarEvent | DutyContext,
    target: date,
    risks: dict[str, list[str]],
    threats: dict[str, list[str]],
    max_items: int,
    source_records: dict[str, list[dict[str, object]]] | None = None,
    exclusion_log: list[dict[str, object]] | None = None,
) -> tuple[dict[str, list[BilingualFact]], dict[str, list[BilingualFact]], list[BilingualFact]]:
    airports = unique([airport for airport in event.route if airport])
    source_records = source_records or {}
    typical = {
        airport: bilingual_typical_facts(
            airport,
            risks.get(airport, []),
            threats.get(airport, []),
            target.month,
            max_items=max_items,
            source_records=source_records.get(airport, []),
            event=event,
            target=target,
            exclusion_log=exclusion_log,
        )
        for airport in airports
    }
    core = {
        airport: airport_operational_facts(
            event,
            airport,
            threats.get(airport, []),
            target,
            source_records=source_records.get(airport, []),
            exclusion_log=exclusion_log,
        )
        for airport in airports
    }
    all_facts = [
        *(fact for airport in airports for fact in typical[airport]),
        *(fact for airport in airports for fact in core[airport]),
    ]
    return typical, core, all_facts


def general_control_items(
    target: date,
    airports: list[str],
    weather_sentence: str,
    *,
    detail: bool = False,
) -> list[str]:
    thunderstorm_risk = 4 <= target.month <= 10 or weather_has_operational_risk(weather_sentence)
    items: list[str] = []
    if thunderstorm_risk:
        items.extend([
            "飞行中不得关闭气象雷达。应根据雷达型号和天气情况合理使用自动及人工模式；使用RDR-4B时不能仅依赖自动识别，"
            "应结合增益、倾斜角和人工扫描判断天气。",
            "云中绕飞与雷暴主体或强回波保持至少20海里；云外绕飞与积雨云保持至少6海里且与强回波保持至少20海里；"
            "云上飞越时与云顶保持至少1500米垂直间隔。低高度绕飞时，PM重点监控地形显示、MSA和地形间隔。",
        ])
    else:
        items.append("飞行中应根据实际天气合理使用气象雷达，并结合雷达型号按要求使用自动及人工模式。")

    items.append(
        "在光洁形态下放出形态前，PF确认当前高度低于FL200、进近阶段已经启用、速度处于管理方式且低于VFE NEXT；"
        "PM复核后喊话“高度检查，速度检查”，再操作襟翼手柄。严格遵守IAF点高度速度限制，最迟7海里放轮，"
        "并在1500英尺AAL前建立稳定状态。"
    )
    if any(is_airport(a, "上海浦东") for a in airports):
        items.append(
            "接近目标高度最后2000英尺时，如有邻近航空器，应合理限制升降率以降低TCAS告警风险；发生TA时及时检查和控制升降率，"
            "并严格按照现行程序处置。"
        )
    if weather_has_operational_risk(weather_sentence) or detail:
        items.append(
            "复飞决策一旦作出，应立即执行标准复飞动作，不得再次收油门尝试继续着陆。低高度复飞以内部仪表为主，"
            "严格监控姿态、速度、形态和正上升率；任何情况下使用反推后必须完成着陆全停。"
        )
    if detail:
        items.append("使用减速板后，如无超速风险应及时收回，防止影响后续能量管理；颠簸中避免与飞机对抗，优先恢复并保持自动驾驶。")
    return unique(items)[: (6 if detail else 5)]


def validate_content(
    content: str,
    event: CalendarEvent | DutyContext,
    profile: dict,
    airports: list[str],
    *,
    language: str,
    typical_facts: dict[str, list[BilingualFact]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if language == "zh":
        expected_name = profile.get("name", "")
        expected_start = "我是"
        risk_heading = "个人对本次航班中识别的风险："
        core_heading = "核心威胁："
    else:
        expected_name = PILOT_ENGLISH_NAMES.get(profile.get("name", ""), profile.get("name", ""))
        expected_start = "I am "
        risk_heading = "Risks I have identified for this flight:"
        core_heading = "Core threats:"

    if expected_name and expected_name not in content:
        errors.append("正文缺少姓名")
    if not content.lstrip().startswith(expected_start):
        errors.append("正文未直接从个人信息开始")
    if risk_heading in content:
        errors.append("正文仍包含已取消的个人风险识别栏目")
    if core_heading not in content:
        errors.append("正文缺少核心威胁标题")

    forbidden_metadata = [
        event.flight_number,
        event.registration,
        f"{event.route[0]}→{event.route[1]}",
        f"{event.route[0]}至{event.route[1]}",
        f"{english_airport_name(event.route[0])}-{english_airport_name(event.route[1])}",
        "签到：",
        "签到时间",
        "人员名单",
        "注册号：",
    ]
    forbidden_metadata.extend(
        strip_crew_role_markers(name)
        for name in event.people
        if strip_crew_role_markers(name) not in {
            profile.get("name", ""),
            PILOT_ENGLISH_NAMES.get(profile.get("name", ""), ""),
        }
    )
    for token in forbidden_metadata:
        if token and token in content:
            errors.append(f"正文泄露内部匹配信息：{token}")

    for airport in airports:
        if language == "zh":
            typical_title = f"{airport_with_suffix(airport)}典型不安全事件："
            core_title = f"{airport_with_suffix(airport)}："
        else:
            typical_title = f"{english_airport_name(airport)} Airport typical unsafe events:"
            core_title = f"{english_airport_name(airport)} Airport:"
        real_typical = None
        if typical_facts is not None:
            real_typical = [
                fact
                for fact in typical_facts.get(airport, [])
                if fact.category != "typical_no_data"
                and (
                    clean_output_fact(fact.zh)
                    if language == "zh"
                    else fact.en.strip()
                )
            ]
            if real_typical and typical_title not in content:
                errors.append(f"正文漏掉{typical_title}")
            if not real_typical and typical_title in content:
                errors.append(f"正文不应显示无可靠事件的{typical_title}")
        if core_title not in content:
            errors.append(f"正文漏掉{core_title}")

    source_artifacts = (
        "参考 EFB",
        "参考EFB",
        "机场特点汇总-",
        "非受控文件",
        "非受 控文件",
        "FORREFERENCEONLY",
        "版本号",
        "责任中队",
        "机场运行特点",
        "典型不安全事件详述",
        "指挥特点：",
        "气象特点：",
        "道面特点：",
        "机场分类：",
        "高原机场：",
        "特殊复杂程序：",
        "地形：",
        "Airport Information",
        "Command characteristics:",
        "Weather characteristics:",
        "Surface characteristics:",
    )
    normalized_content = content.replace(" ", "")
    if any(token.replace(" ", "") in normalized_content for token in source_artifacts):
        errors.append("正文仍包含资料出处、页眉页脚或表格标题")
    if language == "zh" and any(
        token in content
        for token in ("近期注意点：", "•", "核心威胁与控制措施：")
    ):
        errors.append("正文仍包含旧版栏目或黑点列表")
    if re.search(r"(?m)^\s*(?:\d+[.、]|[•●▪])\s*\S", content):
        errors.append("正式正文仍包含编号或项目符号")

    for airport in airports:
        if language == "zh":
            typical_title = f"{airport_with_suffix(airport)}典型不安全事件："
            core_title = f"{airport_with_suffix(airport)}："
        else:
            typical_title = (
                f"{english_airport_name(airport)} Airport typical unsafe events:"
            )
            core_title = f"{english_airport_name(airport)} Airport:"
        if typical_title in content and not re.search(
            rf"(?m)^{re.escape(typical_title)}\n\S", content
        ):
            errors.append(f"{typical_title}缺少事件内容")
        if not re.search(rf"(?m)^{re.escape(core_title)}\n\S", content):
            errors.append(f"{core_title}缺少核心威胁内容")
    return errors


def prep_group_output_name(
    target: date,
    group_index: int,
    group_count: int,
    flights: list[CalendarEvent],
    *,
    english: bool = False,
) -> str:
    language_suffix = "_EN" if english else ""
    if group_count == 1:
        return f"{target.isoformat()}_航前准备{language_suffix}.txt"
    number_slug = "-".join(
        re.sub(r"[^A-Z0-9]", "", event.flight_number.upper())
        for event in flights
        if event.flight_number
    ) or f"GROUP{group_index:02d}"
    return (
        f"{target.isoformat()}_航前准备_{group_index:02d}_{number_slug}"
        f"{language_suffix}.txt"
    )


def fact_source_metadata(fact: BilingualFact) -> dict[str, object]:
    return {
        "fact_id": fact.fact_id,
        "paragraph_id": fact.fact_id if fact.category == "core" else "",
        "airport": fact.airport,
        "source_file": fact.source_file,
        "source": fact.source,
        "source_page": fact.source_page,
        "source_heading": fact.source_heading,
        "source_section": fact.source_section,
        "source_text_zh": fact.source_text_zh,
        "source_original_text": " ".join(
            fact.source_original_texts or (fact.source_text_zh,)
        ),
        "source_original_texts": list(
            fact.source_original_texts or (fact.source_text_zh,)
        ),
        "source_record_ids": list(
            fact.source_record_ids or (fact.fact_id,)
        ),
        "source_clauses": list(fact.source_clauses or (fact.text_zh,)),
        "operational_phase": fact.operational_phase,
        "role_scope": list(fact.role_scope),
        "operational_condition": list(fact.operational_condition),
        "applicability": list(fact.applicability),
        "risk": list(fact.risk),
        "mitigation": list(fact.mitigation),
        "restriction": list(fact.restriction),
        "excluded_source_clauses": [
            {
                "clause": clause,
                "reason": (
                    fact.exclusion_reasons[index]
                    if index < len(fact.exclusion_reasons)
                    else "明确记录为不适用于当前运行"
                ),
            }
            for index, clause in enumerate(fact.excluded_source_clauses)
        ],
        "text_zh": fact.text_zh,
        "text_en": fact.text_en,
        "rendered_text": fact.text_zh,
        "season_scope": list(fact.season_scope),
        "flight_scope": list(fact.flight_scope),
        "route_scope": [list(route) for route in fact.route_scope],
        "topic": fact.topic,
        "role": fact.render_role,
        "source_fact_ids": list(fact.source_fact_ids or (fact.fact_id,)),
        "airport_specific": fact.airport_specific,
        "category": fact.category,
    }


def selected_fact_exclusions(
    airports: list[str],
    typical_facts: dict[str, list[BilingualFact]],
    core_facts: dict[str, list[BilingualFact]],
) -> list[dict[str, object]]:
    return [
        {
            "airport": airport,
            "fact_id": fact.fact_id,
            "clause": clause,
            "reason": (
                fact.exclusion_reasons[index]
                if index < len(fact.exclusion_reasons)
                else "明确记录为不适用于当前运行"
            ),
        }
        for airport in airports
        for fact in [*typical_facts[airport], *core_facts[airport]]
        for index, clause in enumerate(fact.excluded_source_clauses)
    ]


def merge_group_airport_metadata(
    prep_groups: list[dict[str, object]],
    field: str,
) -> dict[str, object]:
    merged: dict[str, object] = {}
    for group in prep_groups:
        group_data = group.get(field, {})
        if not isinstance(group_data, dict):
            continue
        for airport, value in group_data.items():
            if field == "airport_fact_ids":
                destination = merged.setdefault(airport, {"typical": [], "core": []})
                if not isinstance(destination, dict) or not isinstance(value, dict):
                    continue
                for category in ("typical", "core"):
                    current = destination.setdefault(category, [])
                    for fact_id in value.get(category, []):
                        if fact_id not in current:
                            current.append(fact_id)
            elif field == "core_paragraph_fact_ids":
                destination = merged.setdefault(airport, [])
                for source_ids in value:
                    if source_ids not in destination:
                        destination.append(source_ids)
            else:
                destination = merged.setdefault(airport, [])
                known = {
                    (item.get("fact_id"), tuple(item.get("source_fact_ids", [])))
                    for item in destination
                    if isinstance(item, dict)
                }
                for item in value:
                    key = (item.get("fact_id"), tuple(item.get("source_fact_ids", [])))
                    if key not in known:
                        destination.append(item)
                        known.add(key)
    return merged



def write_status(repo: Path, data: dict) -> None:
    out_dir = repo / "agent_output" / "flight_prep"
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / "status.json", data)



def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    target = determine_target_date(args.target_date, args.days_ahead)
    output_dir = repo / "flight_preparation"
    output_dir.mkdir(parents=True, exist_ok=True)
    success_marker = output_dir / ".success"
    if success_marker.exists():
        success_marker.unlink()

    try:
        settings = load_json(repo / "config" / "prep_settings.json", {}) or {}
        profile = load_json(repo / "config" / "pilot_profile.json", {}) or {}
        experience = load_json(repo / "config" / "airport_experience.json", {}) or {}

        all_events = parse_ics(repo / "flight.ics")
        date_flights = [
            event
            for event in all_events
            if event.start.date() == target and event.is_flight and not event.is_positioning
        ]
        selectors_supplied = any((args.flight_number, args.departure, args.arrival))
        if not date_flights and not selectors_supplied:
            status = {
                "status": "NO_TASK",
                "target_date": target.isoformat(),
                "message": "目标日期未发现航班任务，未覆盖已有准备稿。",
                "version": VERSION,
            }
            write_status(repo, status)
            append_github_summary(f"## 免费航前准备\n\n**NO_TASK**：{target.isoformat()} 未发现航班任务。")
            return 0

        try:
            flights = select_continuous_flight_group(
                all_events,
                target,
                flight_number=args.flight_number,
                departure=args.departure,
                arrival=args.arrival,
            )
        except (AmbiguousFlightSelectionError, FlightSelectionError) as exc:
            status = {
                "status": "NEEDS_SELECTION",
                "target_date": target.isoformat(),
                "message": str(exc),
                "version": VERSION,
                "note": "存在多组互不连续任务，需要人工指定；正式准备稿未覆盖。",
            }
            write_status(repo, status)
            atomic_write_json(output_dir / "latest_meta.json", status)
            append_github_summary(
                f"## 免费航前准备\n\n**FAILED_SAFE**：{exc}\n\n正式准备稿未覆盖。"
            )
            return 2

        prep_flight_groups = split_flight_prep_groups_by_flight_number(flights)
        duty = DutyContext(tuple(flights))
        changes: list[str] = []
        if settings.get("auto_update_airport_experience", True):
            experience, changes = update_airport_experience(
                all_events,
                experience,
                as_of=now_beijing(),
                rolling_days=int(settings.get("airport_experience_rolling_days", 90)),
            )
            atomic_write_json(repo / "config" / "airport_experience.json", experience)

        airports = list(duty.route)
        mapping = extract_airport_mapping(repo / "crew_calendar_main.py")
        icao_map = {airport: resolve_icao(airport, mapping) for airport in airports}

        weather_meta: dict[str, dict] = {}
        weather_sentence = "。".join(
            f"{airport_with_suffix(airport)}航班时段天气以航前最新TAF/METAR及放行资料为准"
            for airport in airports
        ) + "。"
        warnings: list[str] = []
        if settings.get("include_weather_section", True):
            weather_sentence, weather_warnings, weather_meta = weather_risk_sentence(
                airports,
                icao_map,
                int(settings.get("weather_timeout_seconds", 20)),
                target=target,
                flights=flights,
            )
            warnings.extend(weather_warnings)

        configured_max = int(
            (settings.get("typical_incidents_per_airport") or {}).get(
                "max", 100
            )
            or 100
        )
        max_items = max(100, configured_max)
        (
            risks,
            airport_threat_map,
            airport_source_records,
            risk_warnings,
            manual_source,
            manual_ver,
            manual_type,
        ) = airport_risks(repo, airports, icao_map, max_items=max_items)
        warnings.extend(risk_warnings)

        missing_airports = [
            airport for airport in airports
            if not airport_threat_map.get(airport)
        ]
        if missing_airports:
            status = {
                "status": "FAILED_SAFE",
                "target_date": target.isoformat(),
                "errors": [f"最新机场特点未完整匹配：{airport}" for airport in missing_airports],
                "version": VERSION,
                "airport_information_file": manual_source,
                "airport_information_version": manual_ver,
                "airport_information_type": manual_type,
                "note": "任一涉及机场缺少核心运行事实，正式准备稿不覆盖。",
            }
            write_status(repo, status)
            append_github_summary(
                "## 免费航前准备\n\n**FAILED_SAFE**：机场资料不完整，未覆盖正式准备稿。\n"
                + "\n".join(f"- {airport}" for airport in missing_airports)
            )
            return 2

        rendered_groups: list[dict[str, object]] = []
        errors: list[str] = []
        group_count = len(prep_flight_groups)
        for group_index, group_flights in enumerate(prep_flight_groups, start=1):
            group_duty = DutyContext(tuple(group_flights))
            group_airports = list(group_duty.route)
            group_records = experience_records(experience, group_airports, target)
            fact_exclusions: list[dict[str, object]] = []
            typical_facts, core_facts, all_facts = briefing_fact_sets(
                group_duty,
                target,
                risks,
                airport_threat_map,
                max_items=max_items,
                source_records=airport_source_records,
                exclusion_log=fact_exclusions,
            )
            (
                english_required,
                english_confirmation_required,
                english_names,
            ) = english_generation_decision(
                group_duty,
                settings,
                args.generate_english,
            )
            group_content = render_chinese_briefing(
                group_duty,
                target,
                profile,
                group_records,
                typical_facts,
                core_facts,
                weather_sentence,
            )
            english_content = (
                render_english_briefing(
                    group_duty,
                    target,
                    profile,
                    group_records,
                    typical_facts,
                    core_facts,
                )
                if english_required
                else ""
            )
            group_label = "/".join(
                event.flight_number for event in group_flights
            )
            errors.extend(
                f"{group_label}：{item}"
                for item in validate_content(
                    group_content,
                    group_duty,
                    profile,
                    group_airports,
                    language="zh",
                    typical_facts=typical_facts,
                )
            )
            for airport in group_airports:
                if not core_facts[airport]:
                    errors.append(f"{group_label}：{airport}没有可追溯的核心运行事实")
                bound_facts = [*typical_facts[airport], *core_facts[airport]]
                errors.extend(
                    f"{group_label}：{item}"
                    for item in validate_airport_fact_bindings(airport, bound_facts)
                )
                for fact in bound_facts:
                    errors.extend(
                        f"{group_label}：{item}"
                        for item in validate_source_semantic_preservation(fact)
                    )
            if english_required:
                errors.extend(
                    f"{group_label}：{item}"
                    for item in validate_bilingual_facts(all_facts)
                )
                errors.extend(
                    f"{group_label}英文版：{item}"
                    for item in validate_content(
                        english_content,
                        group_duty,
                        profile,
                        group_airports,
                        language="en",
                        typical_facts=typical_facts,
                    )
                )

            output_name = prep_group_output_name(
                target,
                group_index,
                group_count,
                group_flights,
            )
            english_output_name = (
                prep_group_output_name(
                    target,
                    group_index,
                    group_count,
                    group_flights,
                    english=True,
                )
                if english_required
                else ""
            )
            group_exclusions = (
                selected_fact_exclusions(
                    group_airports,
                    typical_facts,
                    core_facts,
                )
                + fact_exclusions
            )
            rendered_groups.append(
                {
                    "group_index": group_index,
                    "flight_numbers": [event.flight_number for event in group_flights],
                    "airports": group_airports,
                    "output": output_name,
                    "english_output": english_output_name,
                    "english_generated": english_required,
                    "foreign_crew_detected": bool(english_names),
                    "foreign_crew_names": english_names,
                    "english_confirmation_required": english_confirmation_required,
                    "matched_event_uids": [event.uid for event in group_flights],
                    "matched_flights": [event.to_dict() for event in group_flights],
                    "matched_people": group_duty.people,
                    "weather": {
                        airport: weather_meta[airport]
                        for airport in group_airports
                        if airport in weather_meta
                    },
                    "airport_fact_ids": {
                        airport: {
                            "typical": [fact.fact_id for fact in typical_facts[airport]],
                            "core": [fact.fact_id for fact in core_facts[airport]],
                        }
                        for airport in group_airports
                    },
                    "airport_fact_sources": {
                        airport: [
                            fact_source_metadata(fact)
                            for fact in [*typical_facts[airport], *core_facts[airport]]
                        ]
                        for airport in group_airports
                    },
                    "excluded_source_clauses": group_exclusions,
                    "core_paragraph_fact_ids": {
                        airport: [
                            list(fact.source_fact_ids or (fact.fact_id,))
                            for fact in core_facts[airport]
                        ]
                        for airport in group_airports
                    },
                    "core_paragraphs": {
                        airport: [
                            {
                                "paragraph_index": paragraph_index,
                                "paragraph_id": fact.fact_id,
                                "topic": fact.topic,
                                "role": fact.render_role,
                                "text": fact.text_zh,
                                "source_fact_ids": list(
                                    fact.source_fact_ids or (fact.fact_id,)
                                ),
                                "source_record_ids": list(
                                    fact.source_record_ids or (fact.fact_id,)
                                ),
                                "source_clauses": list(
                                    fact.source_clauses or (fact.text_zh,)
                                ),
                                "source_original_texts": list(
                                    fact.source_original_texts
                                    or (fact.source_text_zh or fact.text_zh,)
                                ),
                                "source_files": unique(
                                    source_file.strip()
                                    for source_file in fact.source_file.split("|")
                                    if source_file.strip()
                                ),
                                "source_sections": unique(
                                    section.strip()
                                    for section in fact.source_section.split("|")
                                    if section.strip()
                                ),
                            }
                            for paragraph_index, fact in enumerate(
                                core_facts[airport], start=1
                            )
                        ]
                        for airport in group_airports
                    },
                    "content_sha256": hashlib.sha256(
                        group_content.encode("utf-8")
                    ).hexdigest(),
                    "_content": group_content,
                    "_english_content": english_content,
                }
            )
        if errors:
            status = {
                "status": "FAILED_SAFE",
                "target_date": target.isoformat(),
                "errors": errors,
                "version": VERSION,
                "note": "正式准备稿未覆盖。",
            }
            write_status(repo, status)
            append_github_summary("## 免费航前准备\n\n**FAILED_SAFE**：\n" + "\n".join(f"- {e}" for e in errors))
            return 2

        group_contents = [str(group.pop("_content")) for group in rendered_groups]
        english_group_contents = [
            str(group.pop("_english_content"))
            for group in rendered_groups
            if group.get("english_generated")
        ]
        aggregate_content = "\n\n====================\n\n".join(
            content.rstrip() for content in group_contents
        ) + "\n"
        aggregate_english = (
            "\n\n====================\n\n".join(
                content.rstrip() for content in english_group_contents
            ) + "\n"
            if english_group_contents
            else ""
        )
        dated_group_name = f"{target.isoformat()}_航前准备.txt"
        dated_english_name = (
            f"{target.isoformat()}_航前准备_EN.txt"
            if aggregate_english
            else ""
        )
        desired_outputs = {
            dated_group_name,
            *(str(group["output"]) for group in rendered_groups),
            *(str(group["english_output"]) for group in rendered_groups if group["english_output"]),
        }
        if dated_english_name:
            desired_outputs.add(dated_english_name)
        for group, content in zip(rendered_groups, group_contents):
            atomic_write_text(output_dir / str(group["output"]), content)
        atomic_write_text(output_dir / dated_group_name, aggregate_content)
        atomic_write_text(output_dir / "latest.txt", aggregate_content)
        english_index = 0
        for group in rendered_groups:
            if not group["english_generated"]:
                continue
            atomic_write_text(
                output_dir / str(group["english_output"]),
                english_group_contents[english_index],
            )
            english_index += 1
        if aggregate_english:
            atomic_write_text(output_dir / dated_english_name, aggregate_english)
            atomic_write_text(output_dir / "latest_en.txt", aggregate_english)
        for stale in output_dir.glob(f"{target.isoformat()}_航前准备_*.txt"):
            if stale.name not in desired_outputs:
                stale.unlink()

        top_airport_fact_ids = merge_group_airport_metadata(
            rendered_groups, "airport_fact_ids"
        )
        top_airport_fact_sources = merge_group_airport_metadata(
            rendered_groups, "airport_fact_sources"
        )
        top_core_paragraph_ids = merge_group_airport_metadata(
            rendered_groups, "core_paragraph_fact_ids"
        )
        top_core_paragraphs = merge_group_airport_metadata(
            rendered_groups, "core_paragraphs"
        )
        all_exclusions = [
            exclusion
            for group in rendered_groups
            for exclusion in group["excluded_source_clauses"]
        ]
        english_names = unique(
            name
            for group in rendered_groups
            for name in group["foreign_crew_names"]
        )
        english_required = any(
            bool(group["english_generated"]) for group in rendered_groups
        )
        english_confirmation_required = any(
            bool(group["english_confirmation_required"])
            for group in rendered_groups
        )

        atomic_write_json(
            output_dir / "latest_meta.json",
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "generated_at_beijing": now_beijing().isoformat(),
                "generator": VERSION,
                "flight_numbers": [event.flight_number for event in flights],
                "airports": airports,
                "group_output": dated_group_name,
                "english_output": dated_english_name,
                "english_generated": english_required,
                "foreign_crew_detected": bool(english_names),
                "foreign_crew_names": english_names,
                "english_confirmation_required": english_confirmation_required,
                "english_trigger_names": english_names,
                "matched_event_uids": [event.uid for event in flights],
                "matched_flights": [event.to_dict() for event in flights],
                "matched_people": duty.people,
                "prep_groups": rendered_groups,
                "warnings": unique(warnings),
                "weather": weather_meta,
                "airport_experience_changes": changes,
                "airport_information_file": manual_source,
                "airport_information_version": manual_ver,
                "airport_information_type": manual_type,
                "airport_fact_ids": top_airport_fact_ids,
                "airport_fact_sources": top_airport_fact_sources,
                "excluded_source_clauses": all_exclusions,
                "core_paragraph_fact_ids": top_core_paragraph_ids,
                "core_paragraphs": top_core_paragraphs,
            },
        )
        atomic_write_text(success_marker, "SUCCESS\n")
        write_status(
            repo,
            {
                "status": "SUCCESS",
                "target_date": target.isoformat(),
                "group_output": str(output_dir / dated_group_name),
                "group_outputs": [
                    str(output_dir / str(group["output"]))
                    for group in rendered_groups
                ],
                "english_output": str(output_dir / dated_english_name) if english_required else "",
                "english_confirmation_required": english_confirmation_required,
                "version": VERSION,
            },
        )
        summary = f"## {target.isoformat()} 航前准备\n"
        for group, content in zip(rendered_groups, group_contents):
            summary += (
                f"\n### 第{group['group_index']}组 "
                f"{'/'.join(group['flight_numbers'])}\n\n"
                f"```text\n{content}```\n"
            )
        if english_required:
            summary += f"\n\n英文版：`flight_preparation/{dated_english_name}`"
        if warnings:
            summary += "\n\n### 系统提示\n" + "\n".join(f"- {w}" for w in unique(warnings))
        append_github_summary(summary)
        print(f"SUCCESS: {output_dir / dated_group_name}")
        for group in rendered_groups:
            print(f"GROUP: {output_dir / str(group['output'])}")
        if english_required:
            print(f"ENGLISH: {output_dir / dated_english_name}")
        return 0

    except Exception as exc:
        status = {
            "status": "FAILED_SAFE",
            "target_date": target.isoformat(),
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=12),
            "version": VERSION,
            "note": "正式准备稿未覆盖。",
        }
        write_status(repo, status)
        append_github_summary(
            f"## 免费航前准备\n\n**FAILED_SAFE**：{type(exc).__name__}: {exc}\n\n原准备稿未覆盖。"
        )
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
