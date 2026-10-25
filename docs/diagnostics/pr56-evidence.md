# PR #56 bilingual pairing evidence

Synchronized main: `56732c91bade5e9636332f6d6663638699b42b3f`. PR remains draft; both dates remain FAILED_SAFE.

This is diagnostic evidence, not an official briefing. No translated replacement or source spelling was generated.

## Before / after

| Target | Before errors | After errors | Chinese selected source IDs unchanged |
|---|---:|---:|---|
| 2026-10-26 | 19 | 8 | True |
| 2026-10-28 | 25 | 9 | True |

## Page-level classifications

A = genuinely absent; B = extraction/token representation; C = structure/phase/order; D = source conflict or unresolved source-language semantic difference.
Source-language review entries are distinguished from proven waypoint/unit conflicts; they do not authorize an automatic correction.

### A-VTBS-STAR (A)

ICAO: VTBS; Chinese page: 315; English pages reviewed: [1163, 1164, 1165, 1166, 1167, 1168]
Source record IDs: `['曼谷素旺那普:core:2c9eb872ff8083ca']`

Status: TRUE_ENGLISH_COVERAGE_GAP; selected dates: ['2026-10-26', '2026-10-28']

**chinese_exact_clause:** 曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。

**evidence:** Chinese Command Characteristics subitem (4) appears after north/south runway operations. English p1163 ends Command Characteristics at subitem (3), followed directly by 4. Pavement characteristics; its continuation on p1164 concerns towing only. Complete arrival section p1166-1168 has no STAR/runway-confirmation counterpart. Later chapter pages are hotel information, not a continuation of this source item.

### A-ZGGG-919R (A)

ICAO: ZGGG; Chinese page: 983; English pages reviewed: [1563, 1564, 1565, 1566]
Source record IDs: `['广州白云:core:a173ff5e7969d2ed']`

Status: TRUE_ENGLISH_COVERAGE_GAP; selected dates: ['2026-10-26']

**chinese_exact_clause:** 广州 机位919R 不建议单发滑行.。

**evidence:** Chinese Core Threats / Pavement characteristics has subitem (1) E J23-J14 uphill and subitem (2) stand 919R. English p1563 has only the first pavement subitem, then immediately Meteorological characteristics. No 919R restriction occurs elsewhere in the complete four-page English chapter. The p1564 J3 single-engine taxi paragraph exists and is correctly paired; it cannot substitute for 919R.

**selection_note:** The selected merged paragraph retains this source fact ID even though its final Chinese projection omits the 919R clause. No Chinese selection or source identity was removed by this fix.

### A-ZGGG-PUSHBACK (A)

ICAO: ZGGG; Chinese page: 986; English pages reviewed: [1563, 1564, 1565, 1566]
Source record IDs: `['广州白云:core:9bbbbc56abd69b8b']`

Status: TRUE_ENGLISH_COVERAGE_GAP; selected dates: ['2026-10-28']

**chinese_exact_clause:** 广州T3，939附近机位，管制给推出指令，可以推 开，推到R3，跑道01R。机务可能只推到大概正对838到939 之间的位置。这个时候应提醒机务往前拉一点，尽量满足推 到R3上。因R3，R4，R5连接处有点滑行区域没有标注，在推 出过程中管制指令和机务行为有时候不够统一，务必多留心。建议设计特定推出程序，或者给出明确清晰推出指令。

**evidence:** Chinese Ground / Precautions subitem (6) occurs on p986 after a p984-985 page continuation and illustration. English Ground / Precautions on p1564 ends at subitem (4) T64, then anti-icing and Exit. No R3/R4/R5, 838/939 pushback item appears in the remaining English chapter.

### A-ZGGG-BRAKE (A)

ICAO: ZGGG; Chinese page: 983; English pages reviewed: [1563, 1564, 1565, 1566]
Source record IDs: `['广州白云:core:6328ded28cd58d53']`

Status: TRUE_ENGLISH_COVERAGE_GAP; selected dates: ['2026-10-28']

**chinese_exact_clause:** 广州涉及航线距离较长，飞机起飞重量大，从T3滑行 至01R/19L地面滑行时间长，且道面坡度起伏和转弯多，易 造成刹车温度高，导致航班延误或起飞后机轮温度超限情况，请机组注意。

**evidence:** Chinese Core Threats / Other threats subitem (5) is the final paragraph on p983. English Other threats p1563 ends at subitem (4) new-runway confusion, followed by Operational Characteristics p1564. No equivalent high-weight/long-taxi/brake-temperature paragraph appears in the complete English chapter.

### A-ZGGG-NORTH-DEPARTURE (A)

ICAO: ZGGG; Chinese page: 986; English pages reviewed: [1563, 1564, 1565, 1566]
Source record IDs: `['广州白云:core:2422ee6d04561eeb']`

Status: TRUE_ENGLISH_COVERAGE_GAP; selected dates: ['2026-10-28']

**chinese_exact_clause:** 广州早出港航班，向北起飞，有时管制指挥使用跑道 02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着 的是P13并不是02R跑道头。Y18为跑道02R跑道等待点，转向 Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。

**evidence:** Chinese Exit / Precautions subitem (2) contains both the crossing/P13 and Y18 clauses. English Exit / Precautions p1565 contains only the general early-departure runway-choice paragraph, then Navigation routes. Neither 02L crossing/P13 nor Y18 exists in the complete English chapter. Two selected Chinese facts share this one parent record.

### D-ZGGG-W19 (D)

ICAO: ZGGG; Chinese page: 987; English pages reviewed: [1565]
Source record IDs: `['广州白云:core:c9f2ac8896ce0bac']`

Status: SOURCE_CONFLICT; selected dates: ['2026-10-26']

**chinese_exact_clause:** 将W19航线MASGU-MABAG-OGABI-NOMAR 航段调整为MASGU- UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃 珠三角航班使用。

**english_exact_clause:** The W19 route segment MASGU-MABAG-OGABI-NOMAR will be adjusted to MASGU-UPMIP-ATKAV-OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China.

**evidence:** Both pages show Navigation routes item 1 with W19 and the same surrounding MASGU/UPMIP/ATKAV/NOMAR sequence. Rendered glyphs confirm OLPAB versus OBLAP, not a text-extraction substitution.

**cross_reference_conclusion:** The other OBLAP occurrences concern Changzhou/Yangzhou via EMRID/V143/OLRIS; they do not independently confirm this W19 revision. Frequency of spelling is not authority to choose either waypoint. No spelling has been selected or rewritten.

### D-ZGGG-180 (D)

ICAO: ZGGG; Chinese page: 987; English pages reviewed: [1565]
Source record IDs: `['广州白云:core:c86df9922ff0cc1f']`

Status: SOURCE_CONFLICT; selected dates: ['2026-10-26']

**chinese_exact_clause:** 会指挥速度180到8海里，尽量满足避免造成间隔不够。

**english_exact_clause:** The vessel shall maintain a speed of 180 to 8 knots, ensuring sufficient spacing to avoid insufficient intervals.

**evidence:** Both are Entry / Command Characteristics subitem (2). English does exist and the parser extracts it as arrival sequence 1. It says 8 knots rather than the Chinese distance 8 nautical miles, and describes a speed range rather than retaining a speed to a distance. Pairing cannot repair this source-level unit/meaning conflict; empty pairing is not classified as missing source.

### D-VTBS-FIVE-WAY (D)

ICAO: VTBS; Chinese page: 318; English pages reviewed: [1166]
Source record IDs: `['曼谷素旺那普:core:cb29f683c773c0a8']`

Status: SOURCE_SEMANTIC_DIVERGENCE_REQUIRES_REVIEW; selected dates: ['2026-10-26', '2026-10-28']

**chinese_exact_clause:** 航图新增Z 进近程序为主用程序，数据库也有变化，提示机组注意阅读对应进场图中Warning 中的说明，避免未经ATC 许可转向五边加入进近程序。

**english_exact_clause:** The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.

**evidence:** Corresponding Arrival / Command Characteristics subitem (3) is fully extracted and paired. The rendered English itself says five-way turns, not final approach. This is a source-English semantic-quality difference, not a missing paragraph or page-continuation bug; no generated replacement was supplied.

### D-VTBS-FIVE-SIDES (D)

ICAO: VTBS; Chinese page: 318; English pages reviewed: [1166, 1167]
Source record IDs: `['曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec']`

Status: SOURCE_SEMANTIC_DIVERGENCE_REQUIRES_REVIEW; selected dates: ['2026-10-26', '2026-10-28']

**evidence:** English Precautions (1) starts at the bottom of p1166 and continues on p1167; the parser retains the full item. English (2) is also present. Rendered English uses 20R RNP five sides and three-way approach, whereas Chinese uses 五边 and 三边航向. Numeric/runway anchors now match, but the existing final-approach semantic guard still rejects the English. This is not a coverage gap; it needs source-English review, not an unreviewed automatic translation.

### D-ZSPD-BASE-LEG (D)

ICAO: ZSPD; Chinese page: 585; English pages reviewed: [1357]
Source record IDs: `['上海浦东:core:368f05545407d85b']`

Status: SOURCE_SEMANTIC_DIVERGENCE_REQUIRES_REVIEW; selected dates: ['2026-10-28']

**evidence:** Chinese item 4.4 says ATC可能指挥短切五边; English item 4.4 says ATC may assign short base-leg vectors. Correct same numbered counterpart is present and paired, and runway/ATC/ILS anchors match after extraction fixes. The final-approach concept guard does not consider base-leg an equivalent final approach. This is documented as a source-language semantic difference requiring authoritative review, not asserted as a proven wrong procedure and not bypassed.

## W19 complete page contexts and cross-check

### OLPAB - PDF page 987

```text
版本：20260924 修订日期：2026.09.24 页码：987
页码：987
（三）航路：
1.将W19航线MASGU-MABAG-OGABI-NOMAR 航段调整为MASGU-
UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃
珠三角航班使用。
2.广州-廊曼出入境点为ASSAD。
3.广州飞宁波管制指挥XEBUL后加入H25航路到VETIB，VETIB
后加入W155航路到TEBON，再加入A470，B221航路经DST加入
原航路，直接准备期间要有心理预期，以防管制临时指挥导
致手忙脚乱。
4.广州飞虹桥航班，经常遇到更换航路，改为走
H25,W155,A470,B221的沿着海岸线的航路，且H25航路在数
据库中没有，注意检查飞行计划
（四）进场：
1.指挥特点：
（1）进场后段会雷达引导，计算好高距比。
（2）会指挥速度180到8海里，尽量满足避免造成间隔不够
。
3.注意事项：
（1）广州01L落地后，指挥GREEN 1时，由E左转T3 时，左
侧无t3灯牌，且地面也无转入t3的图标，只有一个转入T4的
图标，且T4处有灯牌，容易造成误解
（五）特殊运行要求：
1.减噪程序：参考细则 2.21.2 。
2.单发程序：广州机场跑道01L/R、02L/R、03从06.11日起
开始实施单发程序，请机组注意。
3.释压程序：详见EFB。
4.无线电失效程序：详见机场细则2.22.5无线电通信失效通
用程序。
```

### OBLAP - PDF page 523

```text
版本：20260924 修订日期：2026.09.24 页码：523
页码：523
OBLAP加入进港程序。
4.常州-兰州，放行里第一个点给的是ZJ，离场图里没有 ZJ
离港，建议早点联系塔台证实离港方式，一般会给指令保持
一边。11号起飞之后会给指令右转直飞秣陵，需提前熟
悉，否则容易造成机组起飞后工作负荷过大。
5.常州-兰州，放行给11 号跑道保持一边起始高度900 米。
后续修正海压2400米交给南京，南京指挥上修正海压3000
米。注意:常州11 号跑道起飞默认过度高度是2100米
（6900），期间PFD 右下角QNH 会闪烁，需要注意不要习惯
性的设置成STD，避免造成高度穿越。
（四）进场：
1.常用程序：RNP进场程序。
2.指挥特点：塔台可能指挥飞奔牛ZJ或上空CZO，最后放行点
为ZJ，两者相差3.5nm，机组注意区分。
3.注意事项：常州机场11号落地之后，从D 或者E 直角脱离跑
道，脱离后滑行距离较短，有离港的飞机会走A，有滑过的风
险，航图上也没有标注热点区域。
（五）特殊运行要求：
1.场压运行：涉及，本机场为场压（QFE）机场。
2.释压程序：涉及兰州机场航线有释压程序。
3.无线电失效程序：参见NAIP总则3.4.5 中的仪表飞行规则航
空器地空双向无线电通讯失效通用程序；无线电通讯失效程序下，
```

### OBLAP - PDF page 619

```text
版本：20260924 修订日期：2026.09.24 页码：619
页码：619
（3）扬州离场雷达引导触发alt*模式时由于计划自动
定序会导致取消预的选绿点速度，目标速度转变为250
，需注意非预期快速增速避免形态超速。
（三）航路：
（1）厦门、福州-扬州EMRID之后加入V143航路飞
OLRIS，OBLAP加入计划航路；可以向南京进近可以申请
飞ZJ。
（2）舟山-扬州POMOK后可直飞UNTAN。
（3）南昌、珠海-扬州P179后可直飞MADUK。
（4）扬州-南昌、珠海可以申请直飞MADUK—P468或者
VEMEX-P468。
（5）扬州南宁航路：在情报区通告中有关于V107临时
航路使用的提示。如果有活动，R343航路的LLC-GOSMA
航段受限。按照通告，扬州飞南宁有活动时使用浠水-
W80-IDGAG-W581-VIBUB-V107-LLC;南宁飞扬州有活动时
使用LLC-V107-VIBUB-A581-WHA。建议根据通告在二计
划提前做好。
（6）扬州-桂林，广州区域，有空军活动时，UDUMI航
路点不能提前转弯，注意提前减速过点转弯。
（7）扬州-南宁航路特点：GOSMA之前会指挥右偏8海里
，到南宁区域会指挥ENKUS之后右偏15海里，进场雷达
引导。
（四）进场：
1.常用程序：通常使用RNAV程序
2.指挥特点：
（1）扬州使用VMB-93A进场时，无锡进近可能会指挥直飞ZJ
然后PIMOL，前后ATC指令冲突，这是长期行为，望机组悉
知。
（2）当本场向北运行时，从奔牛(ZJ)方向进港如遇军方活
动常州塔台可能指挥ZJ前下高度2400米并且ZJ后飞YA206，
后续换频联系扬州塔台后指挥保持高度过YA206后飞YA107、
YA104接35号盲降。期间过YA206才能下降并要求YA107前到
达900米。通过900米后才可以右转飞YA104。YA104前塔台可
```

### OBLAP - PDF page 1294

```text
版本：20260924 修订日期：2026.09.24 页码：1294
页码：1294
2.Commandprocedure:Theaircraftexitingthefieldfirstcontacts
groundcontrolat121.65torequestclearance,thennotifiesthe
crewtocontactthecontroltowerat118.45uponreadiness.
(III)NavigationRoute:
1.ThelongitudediscrepancybetweentheP564coordinatesin
theZSCG-ZGOWdatabaseandthoseintheflightplanis0.1
minutes,andtheOROTU-P564-TESIGtrackalsoshows
deviations.Thecrewisadvisedtoverifyagainsttheflightplan.
2.FortheChangzhou-Shenyangroute,youcanapplyforadirect
flighttoP74aftercontactingShanghai.
3.Shantou-Changzhou:Duringthe11thapproach,theaircraftis
notpermittedtodescendbelowthespecifiedaltitude,resulting
inasignificantlyhigherprofile.Itisessentialtoreducealtitude
promptly.
Maintainarapiddescentmodewithcontrolledlow-altitude
descentrate,andcontactthecontroltowerinadvanceto
expeditetheprocess.
Decline.AfterusingthetemporaryrouteEMRID,flytheV143
routetoOLRISandthenproceed.
OBLAPjoinedtheportentryprocedure.
4.ChangzhoutoLanzhou.
```

### OBLAP - PDF page 1378

```text
版本：20260924 修订日期：2026.09.24 页码：1378
页码：1378
gate.ItenteredHefeiareacontrolandwasdirectedtoflydirectly
toADGOL.NearIKUBA,thecrewcontactedShanghaifor
climbingaltitude.Theroutewasagainstthewind,andthe
aircraftwasmostlyrestrictedfromclimbing.Thecrew
monitoredfuellevelsclosely.
(4)Generally,theinitialaltitudeforYangzhou'sRNAV
departureprocedureis900meters(correctedsealevel).Incase
ofmilitaryactivities,theaircrafttypicallymaintainsoneside
afterdeparture,withtheinitialaltitudesetat700meters
(correctedsealevel).
3.Precautions:
(1)GiventheproximitybetweenChangzhouandYangzhou,
paycloseattentiontoairtrafficcontrolaltitudesand
pressurereferencestopreventaltitudeerrors.
(2)DepartureinZJdirection.AfterpassingChangzhou,
proceedtoPIMUS.UponapproachtoNanjingwith
sufficientaltitude,proceedtoMLJ.Notethealtitude
restrictionsintheadjacentrestrictedarea,withgroundlevel
at5000meters.
(III)NavigationRoute:
(1)AftertheXiamenandFuzhou-YangzhouEMRID
routes,theV143routehasbeenaddedtotheOLRISflight
plan,withOBLAPincludedinthescheduledroutes.
AirlinesapproachingNanjingmayapplytoflyZJ.
(2)AfterthePOMOKflightfromZhoushantoYangzhou,
youcantakeadirectflighttoUNTAN.
(3)AftertheP179flightfromNanchangorZhuhaito
Yangzhou,passengerscantakeadirectflighttoMADUK.
(4)PassengerstravelingbetweenYangzhouandNanchang
orZhuhaimayrequestdirectflightstoMADUK-P468or
VEMEX-P468.
(5)Yangzhou-NanningAirRoute:Theairtrafficcontrol
noticespecifiestheuseoftheV107temporaryroute.
Duringoperationalperiods,theLLC-GOSMAsegmentof
theR343routeisrestricted.Accordingtothenotice,when
flightsfromYangzhoutoNanningareactive,theroute
shouldbeXishui-W80-IDGAG-W581-VIBUB-V107-LLC;
whenflightsfromNanningtoYangzhouareactive,the
```

### OBLAP - PDF page 1565

```text
版本：20260924 修订日期：2026.09.24 页码：1565
页码：1565
(1)Theaircraftautomaticallydisengagesfromthewavecontact
afterleavingthegroundandapproaches,withthespecific
frequencyprovidedbytheairtrafficcontrol.
(2)IftheSIDhasspeedrestrictions,youmayapplytocancel
them;otherwise,youmustcomply.
(3)DepartingfromLanzhoumaybedirectedtoflydirectlyto
P268orP118,thenjointheX64temporaryroutetoQP.
DepartingfromSoutheastAsiamaybedirectedtoflydirectlyto
P50,thenjointheX66temporaryroutetoBIGRO.
3.Precautions:
Forearlydepartureflights,selectthedeparturerunwaybasedon
real-timeairtrafficupdatesandclearancerequirements.
(3)Navigationroutes:
1.TheW19routesegmentMASGU-MABAG-OGABI-
NOMARwillbeadjustedtoMASGU-UPMIP-ATKAV-
OBLAP-NOMARforflightslandinginGuangzhouandthose
flyingoverthePearlRiverDeltaregionboundforEastChina.
2.TheGuangzhou-Langmanbordercrossingisdesignatedas
ASSAD.
3.TheflightfromGuangzhoutoNingbowillfirstjointhe
XEBULairroute,thentransfertotheH25routetoVETIB.After
VETIB,itwillswitchtotheW155routetoTEBON,thenrejoin
theA470andB221routesviaDSTbeforereturningtothe
originalroute.Duringthepreparationphase,passengersshould
mentallyprepareforpotentiallast-minuteairtrafficcontrol
changestoavoidpanic.
(4)Entry:
1.CommandCharacteristics:
(1)Afterenteringthefield,radarguidancewillbeusedto
calculatethealtitude-to-rangeratio.
(2)Thevesselshallmaintainaspeedof180to8knots,ensuring
sufficientspacingtoavoidinsufficientintervals.
3.Precautions:
(1)AftertheGuangzhou01Laircraftlanded,whendirectingthe
GREEN1aircraft,theEleft-turnsignalforT3wasabsentonthe
leftside,andnogroundindicatorshowedtheapproachtoT3.
OnlyanapproachtoT4wasindicated,withasignallightatT4,
whichcouldeasilycauseconfusion.
(5)Specialoperationalrequirements:
1.Noisereductionprocedure:RefertoRule2.21.2.
```

## BEFORE: every validation error

### BEFORE 2026-10-26 error 1 - 9C7289

9C7289：中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | navigation |
| fact_id | 曼谷素旺那普_core_record_36 |
| source_fact_ids | ['曼谷素旺那普_core_record_36'] |
| source_record_ids | ['曼谷素旺那普:core:e8ac663553b00606'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 巡航时在曼谷区域，近期多触发NAVADS-BRPTG 1+2 FAULT，NAVBKUPSPDFAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。 |
| source_original_texts | ['航路：巡航时在曼谷区域，近期多触发 NAV ADS-B RPTG 1+2 FAULT,NAV BKUP SPD FAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。'] |
| pairing_result | During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. |
| chinese_critical_tokens | ['BRPTG', 'FAULT', 'GPS', 'NAVADS'] |
| english_critical_tokens | ['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: For ZUTF-VTBS, if the post-SAGAG flight route changes, the MCDU and flight plan must be updated. After SAGAG, Vientiane will direct the direct flightto TOMIP. After the route point NAN, Bangkok control will direct the direct flight to TL.
- core/navigation sequence 1: During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. The crew should be thoroughly familiar with the technical notice, maintain awareness of the minimum safe altitude throughout the flight, and follow the technical notice for handling.

### BEFORE 2026-10-26 error 2 - 9C7289

9C7289：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6 |
| source_fact_ids | ['曼谷素旺那普_core_record_8', '曼谷素旺那普_core_record_9', '曼谷素旺那普_core_record_6'] |
| source_record_ids | ['曼谷素旺那普:core:f60636379b83e937', '曼谷素旺那普:core:1c3782b109bf6561'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 三跑道运行，原01R/19L，跑道更名为01/19跑道，原01L/19R跑道更名为02R/20L跑道。南面进出港：19用于起飞和落地，20L用于起飞，20R用于落地。北面进出港：01用于起飞和落地，02R用于起飞，02L用于落地。 |
| source_original_texts | ['南面进出港:19 用于起飞和落地，20L 用于起飞，20R 用于落地。北面进出港:01用于起飞和落地，02R 用于起飞，02L用于落地。', '三跑道运行，原01R/19L,跑道更名为 01/19跑道，原01L/19R 跑道更名为02R/20L 跑道。第三跑道02L/20R 将会 作为非精密进近跑道使用，可以使用RNP 进近程序。'] |
| pairing_result | South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing. Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. |
| chinese_critical_tokens | ['RWY19', 'RWY19R', 'RWY20L'] |
| english_critical_tokens | ['RWY19L', 'RWY19R'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-26 error 3 - 9C7289

9C7289：中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']

Classification: ['A', 'C']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ['曼谷素旺那普_core_record_10'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result | Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required. |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | ['1-50%'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']", "中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-26 error 4 - 9C7289

9C7289：中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']

Classification: ['A', 'C']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ['曼谷素旺那普_core_record_10'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result | Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required. |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | ['1-50%'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']", "中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-26 error 5 - 9C7289

9C7289：中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-WAY']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | 曼谷素旺那普_core_record_41 |
| source_fact_ids | ['曼谷素旺那普_core_record_41'] |
| source_record_ids | ['曼谷素旺那普:core:cb29f683c773c0a8'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 航图新增Z进近程序为主用程序，数据库也有变化，提示机组注意阅读对应进场图中Warning 中的说明，避免未经ATC许可转向五边加入进近程序。 |
| source_original_texts | ['进场：航图新增Z 进近程序为主用程序，数据库也有变化，提 示机组注意阅读对应进场图中Warning 中的说明，避免未经 ATC 许可转向五边加入进近程序。'] |
| pairing_result | Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance. |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | ['ATC'] |
| failure_reasons | ["中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-26 error 6 - 9C7289

9C7289：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ['曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46'] |
| source_record_ids | ['曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']", "中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-26 error 7 - 9C7289

9C7289：中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ['曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46'] |
| source_record_ids | ['曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']", "中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-26 error 8 - 9C7289

9C7289：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48：中文['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19']，英文['121.95', 'S123', 'T18', 'T19']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48 |
| source_fact_ids | ['曼谷素旺那普_core_record_47', '曼谷素旺那普_core_record_48'] |
| source_record_ids | ['曼谷素旺那普:core:d556808277f1afa7'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 02L落地后使用F W跑道外等，使用W穿越跑道Straight ahead D4换频121.95会直接给停机位和滑行路线例如S123 D滑行G前等，继续滑行T18或T19进位。机场细则中规定：02L/20R落地后不允许在快速脱离道停留去等待滑行指令，若无指令，02L落地后应延F、W、02R外等，20R落地后应延F、Z、20L外等。 |
| source_original_texts | ['进场：02L落地后使用F W 跑道外等，使用W 穿越跑道Straight ahead D4 换频 121.95会直接给停机位和滑行路线 例如 S123 D 滑行 G 前等，继续滑行 T18 或 T19 进位。机场细则中规定：02L/20R落地后不允许在快速脱离道停留去等待滑行指令，若无 指令，02L 落地后应延 F、W、02R 外等，20R 落地后应延 F、Z、20L外等。'] |
| pairing_result | For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway. |
| chinese_critical_tokens | ['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19'] |
| english_critical_tokens | ['121.95', 'S123', 'T18', 'T19'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48：中文['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19']，英文['121.95', 'S123', 'T18', 'T19']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-26 error 9 - 9C7289

9C7289：中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_25 |
| source_fact_ids | ['曼谷素旺那普_core_record_25'] |
| source_record_ids | ['曼谷素旺那普:core:bf30ad195abdbae5'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 有减噪程序，除非影响飞行安全，在1900-2300UTC时间内不得使用大反推。 |
| source_original_texts | ['地面：有减噪程序，除非影响飞行安全，在1900-2300UTC时间 内不得使用大反推。'] |
| pairing_result | Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety. |
| chinese_critical_tokens | [] |
| english_critical_tokens | ['UTC'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-26 error 10 - 9C7289

9C7289：最新版机场手册英文配对缺失：paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点

Classification: ['C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3 |
| source_fact_ids | ['曼谷素旺那普_core_record_11', '曼谷素旺那普_core_record_3'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca', '曼谷素旺那普:core:8aae0dcaa16ad3d5'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 如预计经过沥青道面，不建议单发滑行。滑行道不平整如果N1-50%时仍无法滑出，需要拖车。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。', '如预计经过沥青道面，不建议单发滑行。'] |
| pairing_result | Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement. |
| chinese_critical_tokens | ['1-50%'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-26 error 11 - 9C7420

9C7420：中英文关键概念不一致：广州白云_typical_record_1：英文缺少['windshear']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | typical |
| operational_phase | incident |
| fact_id | 广州白云_typical_record_1 |
| source_fact_ids | ['广州白云_typical_record_1'] |
| source_record_ids | ['广州白云:typical:0f475060f256b7a4'] |
| chinese_source_pages | [983] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／典型不安全事件 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['incident'] |
| selected_chinese_text | 该机场曾发生，鸟击，风切变，飞错离场事件，请机组注意识别相关风险。 |
| source_original_texts | ['该机场曾发生，鸟击，风切变，飞错离场事件，请机组注意识别相关风险。'] |
| pairing_result | The airport has experienced incidents including bird strikes, wind shear, and wrong takeoff events. Crew members are advised to remain vigilant in identifying these risks. |
| chinese_critical_tokens | [] |
| english_critical_tokens | [] |
| failure_reasons | ["中英文关键概念不一致：广州白云_typical_record_1：英文缺少['windshear']"] |

Same pairing-phase English candidates, in original extraction order:

- typical/incident sequence 0: The airport has experienced incidents including bird strikes, wind shear, and wrong takeoff events. Crew members are advised to remain vigilant in identifying these risks.

### BEFORE 2026-10-26 error 12 - 9C7420

9C7420：中英文关键事实不一致：曼谷素旺那普_core_record_17：中文['ATC', 'BY', 'OFF', 'STAND']，英文['BY', 'OFF', 'STAND']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_17 |
| source_fact_ids | ['曼谷素旺那普_core_record_17'] |
| source_record_ids | ['曼谷素旺那普:core:ef14b4f4a0147275'] |
| chinese_source_pages | [316] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 地面运行时，应确保Mode S应答机可用，并且打开应答机（例如：非STAND-BY或OFF位置），设置给定的Mode A代码（离港飞机，来自于收到的放行许可；进港飞机，继续原代码直至完全在停机位停好）。 |
| source_original_texts | ['地面：地面运行时，应确保 Mode S 应答机可用，并且打开应 答机（例如：非STAND-BY或 OFF位置），设置给定的Mode A 代 码（离港飞机，来自于收到的放行许可；进港飞机，继续原代码 直至完全在停机位停好）。'] |
| pairing_result | During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron). |
| chinese_critical_tokens | ['ATC', 'BY', 'OFF', 'STAND'] |
| english_critical_tokens | ['BY', 'OFF', 'STAND'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_17：中文['ATC', 'BY', 'OFF', 'STAND']，英文['BY', 'OFF', 'STAND']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-26 error 13 - 9C7420

9C7420：中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_25 |
| source_fact_ids | ['曼谷素旺那普_core_record_25'] |
| source_record_ids | ['曼谷素旺那普:core:bf30ad195abdbae5'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 有减噪程序，除非影响飞行安全，在1900-2300UTC时间内不得使用大反推。 |
| source_original_texts | ['地面：有减噪程序，除非影响飞行安全，在1900-2300UTC时间 内不得使用大反推。'] |
| pairing_result | Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety. |
| chinese_critical_tokens | [] |
| english_critical_tokens | ['UTC'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-26 error 14 - 9C7420

9C7420：中英文关键事实不一致：曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | unspecified |
| fact_id | 曼谷素旺那普_core_record_6 |
| source_fact_ids | ['曼谷素旺那普_core_record_6'] |
| source_record_ids | ['曼谷素旺那普:core:1c3782b109bf6561'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 三跑道运行，原01R/19L，跑道更名为01/19跑道，原01L/19R跑道更名为02R/20L跑道。 |
| source_original_texts | ['三跑道运行，原01R/19L,跑道更名为 01/19跑道，原01L/19R 跑道更名为02R/20L 跑道。第三跑道02L/20R 将会 作为非精密进近跑道使用，可以使用RNP 进近程序。'] |
| pairing_result | Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. |
| chinese_critical_tokens | ['RWY19', 'RWY19R', 'RWY20L'] |
| english_critical_tokens | ['RWY19L', 'RWY19R'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-26 error 15 - 9C7420

9C7420：中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | navigation |
| fact_id | 曼谷素旺那普_core_record_36 |
| source_fact_ids | ['曼谷素旺那普_core_record_36'] |
| source_record_ids | ['曼谷素旺那普:core:e8ac663553b00606'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 巡航时在曼谷区域，近期多触发NAVADS-BRPTG 1+2 FAULT，NAVBKUPSPDFAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。 |
| source_original_texts | ['航路：巡航时在曼谷区域，近期多触发 NAV ADS-B RPTG 1+2 FAULT,NAV BKUP SPD FAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。'] |
| pairing_result | During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. |
| chinese_critical_tokens | ['BRPTG', 'FAULT', 'GPS', 'NAVADS'] |
| english_critical_tokens | ['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: For ZUTF-VTBS, if the post-SAGAG flight route changes, the MCDU and flight plan must be updated. After SAGAG, Vientiane will direct the direct flightto TOMIP. After the route point NAN, Bangkok control will direct the direct flight to TL.
- core/navigation sequence 1: During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. The crew should be thoroughly familiar with the technical notice, maintain awareness of the minimum safe altitude throughout the flight, and follow the technical notice for handling.

### BEFORE 2026-10-26 error 16 - 9C7420

9C7420：中英文关键事实不一致：广州白云_core_record_40：中文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19']，英文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19']

Classification: ['D']

Page-review findings: ['D-ZGGG-W19']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | navigation |
| fact_id | 广州白云_core_record_40 |
| source_fact_ids | ['广州白云_core_record_40'] |
| source_record_ids | ['广州白云:core:c9f2ac8896ce0bac'] |
| chinese_source_pages | [987] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 将W19航线MASGU-MABAG-OGABI-NOMAR航段调整为MASGU-UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃珠三角航班使用。 |
| source_original_texts | ['航路：将W19航线MASGU-MABAG-OGABI-NOMAR 航段调整为MASGU-UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃 珠三角航班使用。'] |
| pairing_result | The W19 route segment MASGU-MABAG-OGABI- NOMAR will be adjusted to MASGU-UPMIP-ATKAV- OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China. |
| chinese_critical_tokens | ['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19'] |
| english_critical_tokens | ['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19'] |
| failure_reasons | ["中英文关键事实不一致：广州白云_core_record_40：中文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19']，英文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: The W19 route segment MASGU-MABAG-OGABI- NOMAR will be adjusted to MASGU-UPMIP-ATKAV- OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China.
- core/navigation sequence 1: The Guangzhou-Langman border crossing isdesignated as ASSAD.
- core/navigation sequence 2: The flight from Guangzhou to Ningbo will firstjoin the XEBUL air route, then transfer to the H25 route to VETIB. After VETIB, itwill switch to the W155 route to TEBON, then rejoin the A470 and B221 routes via DST before returning to the original route. During the preparation phase, passengers should mentally prepare for potential last-minute air trafficcontrol changes to avoid panic.

### BEFORE 2026-10-26 error 17 - 9C7420

9C7420：最新版机场手册英文配对缺失：广州白云_core_record_45：广州白云／广州/白云机场运行特点／核心威胁与运行特点／进场

Classification: ['D']

Page-review findings: ['D-ZGGG-180']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | arrival |
| fact_id | 广州白云_core_record_45 |
| source_fact_ids | ['广州白云_core_record_45'] |
| source_record_ids | ['广州白云:core:c86df9922ff0cc1f'] |
| chinese_source_pages | [987] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 会指挥速度180到8海里，尽量满足避免造成间隔不够。 |
| source_original_texts | ['进场：会指挥速度180到8海里，尽量满足避免造成间隔不够。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_45：广州白云／广州/白云机场运行特点／核心威胁与运行特点／进场'] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: After entering the field,radar guidance will be used to calculate the altitude-to-range ratio.
- core/arrival sequence 1: The vessel shall maintain a speed of 180 to 8 knots, ensuring sufficient spacing to avoid insufficient intervals.
- core/arrival sequence 2: After the Guangzhou 01L aircraft landed, when directing the GREEN 1 aircraft, the E left-turn signal for T3 was absent on the leftside, and no ground indicator showed the approach to T3. Only an approach to T4 was indicated, with a signal light at T4, which could easily cause confusion.

### BEFORE 2026-10-26 error 18 - 9C7420

9C7420：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5：广州白云／广州/白云机场运行特点／核心威胁与运行特点 | 广州/白云机场运行特点／核心威胁与运行特点／地面 | 广州/白云机场运行特点／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-ZGGG-919R']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | approach |
| fact_id | paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5 |
| source_fact_ids | ['广州白云_core_record_4', '广州白云_core_record_19', '广州白云_core_record_5'] |
| source_record_ids | ['广州白云:core:866ec61b16fc342a', '广州白云:core:74147675ed67abd8', '广州白云:core:a173ff5e7969d2ed'] |
| chinese_source_pages | [983, 984] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点 \| 广州/白云机场运行特点／核心威胁与运行特点／地面 \| 广州/白云机场运行特点／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['core', 'ground'] |
| selected_chinese_text | 公司对广州落地飞机有单发滑行要求，某些较短窄停机位进位时注意转弯速度，如J3上的停机位等。01L落地后，滑行道E J23到J14段有较明显上坡，建议在此之后执行单发滑行。 |
| source_original_texts | ['01L落地后，滑行道E J23到J14段有较明显上坡，建议 在此之后执行单发滑行。', '地面：公司对广州落地飞机有单发滑行要求，某些较短窄停 机位进位时注意转弯速度，如J3上的停机位等。', '广州 机位919R 不建议单发滑行.。'] |
| pairing_result | After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section. Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R. |
| chinese_critical_tokens | ['J14', 'J23', 'RWY01L'] |
| english_critical_tokens | ['J14', 'J23'] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5：广州白云／广州/白云机场运行特点／核心威胁与运行特点 \| 广州/白云机场运行特点／核心威胁与运行特点／地面 \| 广州/白云机场运行特点／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: The departure taxiway ismarked as "YELLOW", and the arrival taxiway is marked as "GREEN".
- core/core sequence 1: In case of discrepancy between the flight plan's re-flight altitude and the air traffic control command, the latter shall prevail.
- core/core sequence 2: After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section.
- core/core sequence 3: Meteorological characteristics: From late spring to summer, thunderstorms are frequent, with severe thunderstorms often accompanied by low-level wind shear. During summer and autumn, typhoons exert influence, bringing widespread strong winds, heavy rainfall, and thunderstorms.
- core/core sequence 4: The airport ishighly busy with multiple adjacent airports, requiring strict compliance with air trafficcontrol directives to prevent conflicts.
- core/core sequence 5: Adjust the single-shot acceleration altitude according to the fly Smart modification.
- core/core sequence 6: The new procedure involves adjustments to multiple programs and name changes, with height restrictions requiring modifications. Please refer to the air chart for MCDU data verification.
- core/core sequence 7: New airport runways pose risks of misidentification, misdirection, or land to wrong way. Crews must stay vigilant, enforce standardized announcements and cross-checking procedures, especially during low visibility, rain, or night operations, to prevent runway confusion.
- core/ground sequence 0: No need to recite PDC
- core/ground sequence 1: The departure taxiway is designated as "YELLOW", while the arrival taxiway is "GREEN". Pilots must familiarize themselves with the specific taxiway number before each run, as itcorresponds to the standard taxiway for both departure and arrival. During approach preparation, they should review the taxiway chart in advance. If the crew needs to deviate from the runway, they must promptly confirm the turn direction with air traffic control.
- core/ground sequence 2: Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.
- core/ground sequence 3: When the lead vehicle approaches, the ground commander acts as its driver. Upon reaching the target position, the commander must control the speed and guide the driver to disembark.
- core/ground sequence 4: The company requires single-engine taxiing for aircraft landing in Guangzhou, with particular attention to turning speed when approaching shorter and narrower aprons, such as those on the J3 apron.
- core/ground sequence 5: The green password for the covered bridge is 202510 (marked with a green√). For international flights entering through boarding gates, please call the access control phone (marked beside the gate) to open the door.
- core/ground sequence 6: At Guangzhou O2 R, the M taxiway is operational while the T64 taxiway lacks signage, with only ground taxiway markers visible. The T64 sign is actually positioned behind the taxiway, which may cause confusion.

### BEFORE 2026-10-26 error 19 - 9C7420

9C7420：中英文选定事实身份不一致：中文['曼谷素旺那普_typical_record_1', '广州白云_typical_record_1', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', '广州白云_core_record_40', '广州白云_core_record_45', '广州白云_core_record_6', '广州白云_core_record_15', 'paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5']，英文['曼谷素旺那普_typical_record_1', '广州白云_typical_record_1', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', '广州白云_core_record_40', '广州白云_core_record_15', 'paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

### BEFORE 2026-10-28 error 1 - 9C7419

9C7419：中英文关键概念不一致：广州白云_typical_record_1：英文缺少['windshear']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | typical |
| operational_phase | incident |
| fact_id | 广州白云_typical_record_1 |
| source_fact_ids | ['广州白云_typical_record_1'] |
| source_record_ids | ['广州白云:typical:0f475060f256b7a4'] |
| chinese_source_pages | [983] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／典型不安全事件 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['incident'] |
| selected_chinese_text | 该机场曾发生，鸟击，风切变，飞错离场事件，请机组注意识别相关风险。 |
| source_original_texts | ['该机场曾发生，鸟击，风切变，飞错离场事件，请机组注意识别相关风险。'] |
| pairing_result | The airport has experienced incidents including bird strikes, wind shear, and wrong takeoff events. Crew members are advised to remain vigilant in identifying these risks. |
| chinese_critical_tokens | [] |
| english_critical_tokens | [] |
| failure_reasons | ["中英文关键概念不一致：广州白云_typical_record_1：英文缺少['windshear']"] |

Same pairing-phase English candidates, in original extraction order:

- typical/incident sequence 0: The airport has experienced incidents including bird strikes, wind shear, and wrong takeoff events. Crew members are advised to remain vigilant in identifying these risks.

### BEFORE 2026-10-28 error 2 - 9C7419

9C7419：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_23+广州白云_core_record_27：广州白云／广州/白云机场运行特点／核心威胁与运行特点／地面

Classification: ['A']

Page-review findings: ['A-ZGGG-PUSHBACK']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | ground |
| fact_id | paragraph:广州白云_core_record_23+广州白云_core_record_27 |
| source_fact_ids | ['广州白云_core_record_23', '广州白云_core_record_27'] |
| source_record_ids | ['广州白云:core:9bbbbc56abd69b8b'] |
| chinese_source_pages | [986] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 广州T3，939附近机位，管制给推出指令，可以推开，推到R3，跑道01R。建议设计特定推出程序，或者给出明确清晰推出指令。 |
| source_original_texts | ['地面：广州T3，939附近机位，管制给推出指令，可以推 开，推到R3，跑道01R。机务可能只推到大概正对838到939 之间的位置。这个时候应提醒机务往前拉一点，尽量满足推 到R3上。因R3，R4，R5连接处有点滑行区域没有标注，在推 出过程中管制指令和机务行为有时候不够统一，务必多留心。建议设计特定推出程序，或者给出明确清晰推出指令。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_23+广州白云_core_record_27：广州白云／广州/白云机场运行特点／核心威胁与运行特点／地面'] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: No need to recite PDC
- core/ground sequence 1: The departure taxiway is designated as "YELLOW", while the arrival taxiway is "GREEN". Pilots must familiarize themselves with the specific taxiway number before each run, as itcorresponds to the standard taxiway for both departure and arrival. During approach preparation, they should review the taxiway chart in advance. If the crew needs to deviate from the runway, they must promptly confirm the turn direction with air traffic control.
- core/ground sequence 2: Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.
- core/ground sequence 3: When the lead vehicle approaches, the ground commander acts as its driver. Upon reaching the target position, the commander must control the speed and guide the driver to disembark.
- core/ground sequence 4: The company requires single-engine taxiing for aircraft landing in Guangzhou, with particular attention to turning speed when approaching shorter and narrower aprons, such as those on the J3 apron.
- core/ground sequence 5: The green password for the covered bridge is 202510 (marked with a green√). For international flights entering through boarding gates, please call the access control phone (marked beside the gate) to open the door.
- core/ground sequence 6: At Guangzhou O2 R, the M taxiway is operational while the T64 taxiway lacks signage, with only ground taxiway markers visible. The T64 sign is actually positioned behind the taxiway, which may cause confusion.

### BEFORE 2026-10-28 error 3 - 9C7419

9C7419：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_34+广州白云_core_record_35：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场

Classification: ['A']

Page-review findings: ['A-ZGGG-NORTH-DEPARTURE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | paragraph:广州白云_core_record_34+广州白云_core_record_35 |
| source_fact_ids | ['广州白云_core_record_34', '广州白云_core_record_35'] |
| source_record_ids | ['广州白云:core:2422ee6d04561eeb'] |
| chinese_source_pages | [986] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／离场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['departure'] |
| selected_chinese_text | 广州早出港航班，向北起飞，有时管制指挥使用跑道02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着的是P13并不是02R跑道头。 |
| source_original_texts | ['离场：广州早出港航班，向北起飞，有时管制指挥使用跑道 02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着 的是P13并不是02R跑道头。Y18为跑道02R跑道等待点，转向 Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC', 'P13', 'RWY02R'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_34+广州白云_core_record_35：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场'] |

Same pairing-phase English candidates, in original extraction order:

- core/departure sequence 0: The aircraft automatically disengages from the wave contact after leaving the ground and approaches, with the specific frequency provided by the airtraffic control.
- core/departure sequence 1: Ifthe SID has speed restrictions, you may apply to cancel them; otherwise, you must comply.
- core/departure sequence 2: Departing from Lanzhou may be directed to fly directly to P268 or P118, then join the X64 temporary route to QP. Departing from Southeast Asia may be directed to fly directly to P50, then join the X66 temporary route to BIGRO.
- core/departure sequence 3: Precautions: For early departure flights, select the departure runway based on real-time airtraffic updates and clearance requirements.

### BEFORE 2026-10-28 error 4 - 9C7419

9C7419：最新版机场手册英文配对缺失：广州白云_core_record_11：广州白云／广州/白云机场运行特点／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-ZGGG-BRAKE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | 广州白云_core_record_11 |
| source_fact_ids | ['广州白云_core_record_11'] |
| source_record_ids | ['广州白云:core:6328ded28cd58d53'] |
| chinese_source_pages | [983] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 广州涉及航线距离较长，飞机起飞重量大，从T3滑行至01R/19L地面滑行时间长，且道面坡度起伏和转弯多，易造成刹车温度高，导致航班延误或起飞后机轮温度超限情况，请机组注意。 |
| source_original_texts | ['广州涉及航线距离较长，飞机起飞重量大，从T3滑行 至01R/19L地面滑行时间长，且道面坡度起伏和转弯多，易 造成刹车温度高，导致航班延误或起飞后机轮温度超限情况，请机组注意。'] |
| pairing_result |  |
| chinese_critical_tokens | [] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_11：广州白云／广州/白云机场运行特点／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: The departure taxiway ismarked as "YELLOW", and the arrival taxiway is marked as "GREEN".
- core/core sequence 1: In case of discrepancy between the flight plan's re-flight altitude and the air traffic control command, the latter shall prevail.
- core/core sequence 2: After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section.
- core/core sequence 3: Meteorological characteristics: From late spring to summer, thunderstorms are frequent, with severe thunderstorms often accompanied by low-level wind shear. During summer and autumn, typhoons exert influence, bringing widespread strong winds, heavy rainfall, and thunderstorms.
- core/core sequence 4: The airport ishighly busy with multiple adjacent airports, requiring strict compliance with air trafficcontrol directives to prevent conflicts.
- core/core sequence 5: Adjust the single-shot acceleration altitude according to the fly Smart modification.
- core/core sequence 6: The new procedure involves adjustments to multiple programs and name changes, with height restrictions requiring modifications. Please refer to the air chart for MCDU data verification.
- core/core sequence 7: New airport runways pose risks of misidentification, misdirection, or land to wrong way. Crews must stay vigilant, enforce standardized announcements and cross-checking procedures, especially during low visibility, rain, or night operations, to prevent runway confusion.

### BEFORE 2026-10-28 error 5 - 9C7419

9C7419：最新版机场手册英文配对缺失：广州白云_core_record_36：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场

Classification: ['A']

Page-review findings: ['A-ZGGG-NORTH-DEPARTURE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | 广州白云_core_record_36 |
| source_fact_ids | ['广州白云_core_record_36'] |
| source_record_ids | ['广州白云:core:2422ee6d04561eeb'] |
| chinese_source_pages | [986] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／离场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['departure'] |
| selected_chinese_text | Y18为跑道02R跑道等待点，转向Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。 |
| source_original_texts | ['离场：广州早出港航班，向北起飞，有时管制指挥使用跑道 02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着 的是P13并不是02R跑道头。Y18为跑道02R跑道等待点，转向 Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。'] |
| pairing_result |  |
| chinese_critical_tokens | ['RWY02R', 'Y18'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_36：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场'] |

Same pairing-phase English candidates, in original extraction order:

- core/departure sequence 0: The aircraft automatically disengages from the wave contact after leaving the ground and approaches, with the specific frequency provided by the airtraffic control.
- core/departure sequence 1: Ifthe SID has speed restrictions, you may apply to cancel them; otherwise, you must comply.
- core/departure sequence 2: Departing from Lanzhou may be directed to fly directly to P268 or P118, then join the X64 temporary route to QP. Departing from Southeast Asia may be directed to fly directly to P50, then join the X66 temporary route to BIGRO.
- core/departure sequence 3: Precautions: For early departure flights, select the departure runway based on real-time airtraffic updates and clearance requirements.

### BEFORE 2026-10-28 error 6 - 9C7419

9C7419：中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | navigation |
| fact_id | 曼谷素旺那普_core_record_36 |
| source_fact_ids | ['曼谷素旺那普_core_record_36'] |
| source_record_ids | ['曼谷素旺那普:core:e8ac663553b00606'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 巡航时在曼谷区域，近期多触发NAVADS-BRPTG 1+2 FAULT，NAVBKUPSPDFAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。 |
| source_original_texts | ['航路：巡航时在曼谷区域，近期多触发 NAV ADS-B RPTG 1+2 FAULT,NAV BKUP SPD FAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。'] |
| pairing_result | During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. |
| chinese_critical_tokens | ['BRPTG', 'FAULT', 'GPS', 'NAVADS'] |
| english_critical_tokens | ['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: For ZUTF-VTBS, if the post-SAGAG flight route changes, the MCDU and flight plan must be updated. After SAGAG, Vientiane will direct the direct flightto TOMIP. After the route point NAN, Bangkok control will direct the direct flight to TL.
- core/navigation sequence 1: During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. The crew should be thoroughly familiar with the technical notice, maintain awareness of the minimum safe altitude throughout the flight, and follow the technical notice for handling.

### BEFORE 2026-10-28 error 7 - 9C7419

9C7419：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6 |
| source_fact_ids | ['曼谷素旺那普_core_record_8', '曼谷素旺那普_core_record_9', '曼谷素旺那普_core_record_6'] |
| source_record_ids | ['曼谷素旺那普:core:f60636379b83e937', '曼谷素旺那普:core:1c3782b109bf6561'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 三跑道运行，原01R/19L，跑道更名为01/19跑道，原01L/19R跑道更名为02R/20L跑道。南面进出港：19用于起飞和落地，20L用于起飞，20R用于落地。北面进出港：01用于起飞和落地，02R用于起飞，02L用于落地。 |
| source_original_texts | ['南面进出港:19 用于起飞和落地，20L 用于起飞，20R 用于落地。北面进出港:01用于起飞和落地，02R 用于起飞，02L用于落地。', '三跑道运行，原01R/19L,跑道更名为 01/19跑道，原01L/19R 跑道更名为02R/20L 跑道。第三跑道02L/20R 将会 作为非精密进近跑道使用，可以使用RNP 进近程序。'] |
| pairing_result | South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing. Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. |
| chinese_critical_tokens | ['RWY19', 'RWY19R', 'RWY20L'] |
| english_critical_tokens | ['RWY19L', 'RWY19R'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-28 error 8 - 9C7419

9C7419：中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']

Classification: ['A', 'C']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ['曼谷素旺那普_core_record_10'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result | Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required. |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | ['1-50%'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']", "中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-28 error 9 - 9C7419

9C7419：中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']

Classification: ['A', 'C']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ['曼谷素旺那普_core_record_10'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result | Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required. |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | ['1-50%'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_10：中文['STAR']，英文['1-50%']", "中英文关键概念不一致：曼谷素旺那普_core_record_10：英文缺少['runway', 'final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-28 error 10 - 9C7419

9C7419：中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-WAY']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | 曼谷素旺那普_core_record_41 |
| source_fact_ids | ['曼谷素旺那普_core_record_41'] |
| source_record_ids | ['曼谷素旺那普:core:cb29f683c773c0a8'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 航图新增Z进近程序为主用程序，数据库也有变化，提示机组注意阅读对应进场图中Warning 中的说明，避免未经ATC许可转向五边加入进近程序。 |
| source_original_texts | ['进场：航图新增Z 进近程序为主用程序，数据库也有变化，提 示机组注意阅读对应进场图中Warning 中的说明，避免未经 ATC 许可转向五边加入进近程序。'] |
| pairing_result | Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance. |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | ['ATC'] |
| failure_reasons | ["中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-28 error 11 - 9C7419

9C7419：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ['曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46'] |
| source_record_ids | ['曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']", "中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-28 error 12 - 9C7419

9C7419：中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ['曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46'] |
| source_record_ids | ['曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：中文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'VIA', 'VTBS']，英文['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS']", "中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-28 error 13 - 9C7419

9C7419：中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48：中文['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19']，英文['121.95', 'S123', 'T18', 'T19']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48 |
| source_fact_ids | ['曼谷素旺那普_core_record_47', '曼谷素旺那普_core_record_48'] |
| source_record_ids | ['曼谷素旺那普:core:d556808277f1afa7'] |
| chinese_source_pages | [318] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 02L落地后使用F W跑道外等，使用W穿越跑道Straight ahead D4换频121.95会直接给停机位和滑行路线例如S123 D滑行G前等，继续滑行T18或T19进位。机场细则中规定：02L/20R落地后不允许在快速脱离道停留去等待滑行指令，若无指令，02L落地后应延F、W、02R外等，20R落地后应延F、Z、20L外等。 |
| source_original_texts | ['进场：02L落地后使用F W 跑道外等，使用W 穿越跑道Straight ahead D4 换频 121.95会直接给停机位和滑行路线 例如 S123 D 滑行 G 前等，继续滑行 T18 或 T19 进位。机场细则中规定：02L/20R落地后不允许在快速脱离道停留去等待滑行指令，若无 指令，02L 落地后应延 F、W、02R 外等，20R 落地后应延 F、Z、20L外等。'] |
| pairing_result | For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway. |
| chinese_critical_tokens | ['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19'] |
| english_critical_tokens | ['121.95', 'S123', 'T18', 'T19'] |
| failure_reasons | ["中英文关键事实不一致：paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48：中文['121.95', 'RWY02L', 'RWY20R', 'S123', 'T18', 'T19']，英文['121.95', 'S123', 'T18', 'T19']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### BEFORE 2026-10-28 error 14 - 9C7419

9C7419：中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_25 |
| source_fact_ids | ['曼谷素旺那普_core_record_25'] |
| source_record_ids | ['曼谷素旺那普:core:bf30ad195abdbae5'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 有减噪程序，除非影响飞行安全，在1900-2300UTC时间内不得使用大反推。 |
| source_original_texts | ['地面：有减噪程序，除非影响飞行安全，在1900-2300UTC时间 内不得使用大反推。'] |
| pairing_result | Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety. |
| chinese_critical_tokens | [] |
| english_critical_tokens | ['UTC'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-28 error 15 - 9C7419

9C7419：最新版机场手册英文配对缺失：paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点

Classification: ['C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3 |
| source_fact_ids | ['曼谷素旺那普_core_record_11', '曼谷素旺那普_core_record_3'] |
| source_record_ids | ['曼谷素旺那普:core:2c9eb872ff8083ca', '曼谷素旺那普:core:8aae0dcaa16ad3d5'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 如预计经过沥青道面，不建议单发滑行。滑行道不平整如果N1-50%时仍无法滑出，需要拖车。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。', '如预计经过沥青道面，不建议单发滑行。'] |
| pairing_result | Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement. |
| chinese_critical_tokens | ['1-50%'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-28 error 16 - 9C7419

9C7419：中英文选定事实身份不一致：中文['广州白云_typical_record_1', '曼谷素旺那普_typical_record_1', 'paragraph:广州白云_core_record_23+广州白云_core_record_27', 'paragraph:广州白云_core_record_34+广州白云_core_record_35', '广州白云_core_record_30', '广州白云_core_record_11', '广州白云_core_record_36', '广州白云_core_record_42', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_10', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']，英文['广州白云_typical_record_1', '曼谷素旺那普_typical_record_1', '广州白云_core_record_30', '广州白云_core_record_42', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_10', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

### BEFORE 2026-10-28 error 17 - 9C7290

9C7290：中英文关键事实不一致：曼谷素旺那普_core_record_17：中文['ATC', 'BY', 'OFF', 'STAND']，英文['BY', 'OFF', 'STAND']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_17 |
| source_fact_ids | ['曼谷素旺那普_core_record_17'] |
| source_record_ids | ['曼谷素旺那普:core:ef14b4f4a0147275'] |
| chinese_source_pages | [316] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 地面运行时，应确保Mode S应答机可用，并且打开应答机（例如：非STAND-BY或OFF位置），设置给定的Mode A代码（离港飞机，来自于收到的放行许可；进港飞机，继续原代码直至完全在停机位停好）。 |
| source_original_texts | ['地面：地面运行时，应确保 Mode S 应答机可用，并且打开应 答机（例如：非STAND-BY或 OFF位置），设置给定的Mode A 代 码（离港飞机，来自于收到的放行许可；进港飞机，继续原代码 直至完全在停机位停好）。'] |
| pairing_result | During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron). |
| chinese_critical_tokens | ['ATC', 'BY', 'OFF', 'STAND'] |
| english_critical_tokens | ['BY', 'OFF', 'STAND'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_17：中文['ATC', 'BY', 'OFF', 'STAND']，英文['BY', 'OFF', 'STAND']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-28 error 18 - 9C7290

9C7290：中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | ground |
| fact_id | 曼谷素旺那普_core_record_25 |
| source_fact_ids | ['曼谷素旺那普_core_record_25'] |
| source_record_ids | ['曼谷素旺那普:core:bf30ad195abdbae5'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 有减噪程序，除非影响飞行安全，在1900-2300UTC时间内不得使用大反推。 |
| source_original_texts | ['地面：有减噪程序，除非影响飞行安全，在1900-2300UTC时间 内不得使用大反推。'] |
| pairing_result | Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety. |
| chinese_critical_tokens | [] |
| english_critical_tokens | ['UTC'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_25：中文[]，英文['UTC']"] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: On-site/Dispatch Frequency: BANGKOKBLUEPORT (BANG-KOKBLUEPORT), Frequency 129.050. Should our crew members have any inquiries at Suvarnabhumi Airport—such as requests for TOBT/TSAT/landing slot information, flight planning assistance, or special requests—please contact them via this frequency.
- core/ground sequence 1: During ground operations, ensure the Mode S transponder is operational and activated (e.g.,not in STAND-BY or OFF position). Set the designated Mode A code (for departing aircraft, use the code from the received clearance; forarriving aircraft,maintain the original code until fully parked in the apron).
- core/ground sequence 2: To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.
- core/ground sequence 3: Note that H6 and H3, as well as H5 and H2, are on the same taxiway.
- core/ground sequence 4: During refueling, passengers must input their name's pinyin on the electronic tablet as a signature. Suvarnabhumi Airport prohibits boarding during refueling. Ifboarding is necessary, notify the airport in advance to prepare fire trucks. For details, contact Spring Airlines Maintenance. The code for the jet bridge is 2580#.
- core/ground sequence 5: Noise reduction procedures are in effect. The use of heavy reverse thrust is prohibited between 1900 and 2300 UTC unless it compromises flight safety.
- core/ground sequence 6: At Terminal S126 in Bangkok, the approach guidance system frequently exhibits abrupt switching: it may instantaneously shift from 2 meters to 0, then display "Stop"; after pressing "OK," the number may switch again, posing a risk of overshooting or failing to reach the correct position. Both flight crew and ground maintenance personnel have encountered this issue on multiple occasions.

### BEFORE 2026-10-28 error 19 - 9C7290

9C7290：中英文关键事实不一致：曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | unspecified |
| fact_id | 曼谷素旺那普_core_record_6 |
| source_fact_ids | ['曼谷素旺那普_core_record_6'] |
| source_record_ids | ['曼谷素旺那普:core:1c3782b109bf6561'] |
| chinese_source_pages | [315] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 三跑道运行，原01R/19L，跑道更名为01/19跑道，原01L/19R跑道更名为02R/20L跑道。 |
| source_original_texts | ['三跑道运行，原01R/19L,跑道更名为 01/19跑道，原01L/19R 跑道更名为02R/20L 跑道。第三跑道02L/20R 将会 作为非精密进近跑道使用，可以使用RNP 进近程序。'] |
| pairing_result | Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. |
| chinese_critical_tokens | ['RWY19', 'RWY19R', 'RWY20L'] |
| english_critical_tokens | ['RWY19L', 'RWY19R'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_6：中文['RWY19', 'RWY19R', 'RWY20L']，英文['RWY19L', 'RWY19R']"] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### BEFORE 2026-10-28 error 20 - 9C7290

9C7290：中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | navigation |
| fact_id | 曼谷素旺那普_core_record_36 |
| source_fact_ids | ['曼谷素旺那普_core_record_36'] |
| source_record_ids | ['曼谷素旺那普:core:e8ac663553b00606'] |
| chinese_source_pages | [317] |
| production_source_page_metadata | N/A |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 巡航时在曼谷区域，近期多触发NAVADS-BRPTG 1+2 FAULT，NAVBKUPSPDFAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。 |
| source_original_texts | ['航路：巡航时在曼谷区域，近期多触发 NAV ADS-B RPTG 1+2 FAULT,NAV BKUP SPD FAULT，随后出现两侧GPS PRIMARYLOST，机组应当提前熟知技术通告，飞行全过程中知晓最低安全高度，按技术通告处理。'] |
| pairing_result | During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. |
| chinese_critical_tokens | ['BRPTG', 'FAULT', 'GPS', 'NAVADS'] |
| english_critical_tokens | ['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD'] |
| failure_reasons | ["中英文关键事实不一致：曼谷素旺那普_core_record_36：中文['BRPTG', 'FAULT', 'GPS', 'NAVADS']，英文['ADS', 'ADS-B', 'BKUP', 'FAULT', 'GPS', 'LOST', 'NAV', 'PRIMARY', 'RPTG', 'SPD']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: For ZUTF-VTBS, if the post-SAGAG flight route changes, the MCDU and flight plan must be updated. After SAGAG, Vientiane will direct the direct flightto TOMIP. After the route point NAN, Bangkok control will direct the direct flight to TL.
- core/navigation sequence 1: During a cruise in the Bangkok area, the aircraft recently experienced multiple failures including NAV ADS-B RPTG 1+2 FAULT and NAV BKUP SPD FAULT, followed by GPS PRIMARY LOST on both sides. The crew should be thoroughly familiar with the technical notice, maintain awareness of the minimum safe altitude throughout the flight, and follow the technical notice for handling.

### BEFORE 2026-10-28 error 21 - 9C7290

9C7290：中英文关键事实不一致：上海浦东_core_record_11：中文['ATC', 'ILS', 'RWY35L']，英文['ATC', 'ILS', 'RWY', 'RWY17R']

Classification: ['D']

Page-review findings: ['D-ZSPD-BASE-LEG']

| Field | Evidence |
|---|---|
| airport | 上海浦东 |
| icao | ZSPD |
| category | core |
| operational_phase | arrival |
| fact_id | 上海浦东_core_record_11 |
| source_fact_ids | ['上海浦东_core_record_11'] |
| source_record_ids | ['上海浦东:core:368f05545407d85b'] |
| chinese_source_pages | [585] |
| production_source_page_metadata | 448-451 |
| chinese_source_heading | 上海/浦东机场运行特点（ZSPD/PVG） |
| chinese_source_section | 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Shanghai/Pudong', 'iata': 'PVG', 'icao': 'ZSPD', 'start_page': 1354, 'end_page': 1358} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 浦东17R/35L跑道，ATC可能指挥短切五边或较晚发布盲降许可，机组做好预判并提前做好能量管理，积极沟通，按需接受ATC雷达引导的指令。 |
| source_original_texts | ['进场：浦东 17R/35L 跑道，ATC 可能指挥短切五边或较晚发布盲降许可，机组做好 预判并提前做好能量管理，积极沟通，按需接受 ATC 雷达引导的指令。当 需要实施"从上方截获下滑道"程序时，严格遵循 SOP 要求，如无法满足稳 定进近标准，果断复飞或中止进近。'] |
| pairing_result | For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. |
| chinese_critical_tokens | ['ATC', 'ILS', 'RWY35L'] |
| english_critical_tokens | ['ATC', 'ILS', 'RWY', 'RWY17R'] |
| failure_reasons | ["中英文关键事实不一致：上海浦东_core_record_11：中文['ATC', 'ILS', 'RWY35L']，英文['ATC', 'ILS', 'RWY', 'RWY17R']", "中英文关键概念不一致：上海浦东_core_record_11：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: For BK arrival:during north-bound operations, RWY 35L (western runway) is normally assigned; during south-bound operations, RWY 16L (eastern runway) is normally assigned.
- core/arrival sequence 1: Multiple arrival procedures are in use, with ad-hoc amendments possible. Direct-to clearances are common during off-peak periods. Maintain contingency plans.
- core/arrival sequence 2: Multiple TA/RA alerts have been recorded during south-bound approaches into Pudong. Prepare contingency measures during approach preparation and execute memory-item procedures per aircraft manual.
- core/arrival sequence 3: For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. When performing “glideslope capture from above” procedure, strictly comply with SOP. If stable-approach criteriacannot be satisfied, execute missed approach or discontinued approach without hesitation.
- core/arrival sequence 4: For RWY 34R approach, tall obstacles exist slightly right-of-track between waypoints PD083 and PD084. Over-flying ator maintaining 600 m may trigger GPWS caution alerts. Follow the operational advisory “Reminder on GPWS Caution Triggers for RWY 34R Approaches at Pudong” available in EFB.

### BEFORE 2026-10-28 error 22 - 9C7290

9C7290：中英文关键概念不一致：上海浦东_core_record_11：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-ZSPD-BASE-LEG']

| Field | Evidence |
|---|---|
| airport | 上海浦东 |
| icao | ZSPD |
| category | core |
| operational_phase | arrival |
| fact_id | 上海浦东_core_record_11 |
| source_fact_ids | ['上海浦东_core_record_11'] |
| source_record_ids | ['上海浦东:core:368f05545407d85b'] |
| chinese_source_pages | [585] |
| production_source_page_metadata | 448-451 |
| chinese_source_heading | 上海/浦东机场运行特点（ZSPD/PVG） |
| chinese_source_section | 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Shanghai/Pudong', 'iata': 'PVG', 'icao': 'ZSPD', 'start_page': 1354, 'end_page': 1358} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 浦东17R/35L跑道，ATC可能指挥短切五边或较晚发布盲降许可，机组做好预判并提前做好能量管理，积极沟通，按需接受ATC雷达引导的指令。 |
| source_original_texts | ['进场：浦东 17R/35L 跑道，ATC 可能指挥短切五边或较晚发布盲降许可，机组做好 预判并提前做好能量管理，积极沟通，按需接受 ATC 雷达引导的指令。当 需要实施"从上方截获下滑道"程序时，严格遵循 SOP 要求，如无法满足稳 定进近标准，果断复飞或中止进近。'] |
| pairing_result | For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. |
| chinese_critical_tokens | ['ATC', 'ILS', 'RWY35L'] |
| english_critical_tokens | ['ATC', 'ILS', 'RWY', 'RWY17R'] |
| failure_reasons | ["中英文关键事实不一致：上海浦东_core_record_11：中文['ATC', 'ILS', 'RWY35L']，英文['ATC', 'ILS', 'RWY', 'RWY17R']", "中英文关键概念不一致：上海浦东_core_record_11：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: For BK arrival:during north-bound operations, RWY 35L (western runway) is normally assigned; during south-bound operations, RWY 16L (eastern runway) is normally assigned.
- core/arrival sequence 1: Multiple arrival procedures are in use, with ad-hoc amendments possible. Direct-to clearances are common during off-peak periods. Maintain contingency plans.
- core/arrival sequence 2: Multiple TA/RA alerts have been recorded during south-bound approaches into Pudong. Prepare contingency measures during approach preparation and execute memory-item procedures per aircraft manual.
- core/arrival sequence 3: For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. When performing “glideslope capture from above” procedure, strictly comply with SOP. If stable-approach criteriacannot be satisfied, execute missed approach or discontinued approach without hesitation.
- core/arrival sequence 4: For RWY 34R approach, tall obstacles exist slightly right-of-track between waypoints PD083 and PD084. Over-flying ator maintaining 600 m may trigger GPWS caution alerts. Follow the operational advisory “Reminder on GPWS Caution Triggers for RWY 34R Approaches at Pudong” available in EFB.

### BEFORE 2026-10-28 error 23 - 9C7290

9C7290：中英文关键事实不一致：上海浦东_core_record_8：中文['BK', 'RWY35L']，英文['BK', 'RWY', 'RWY35L']

Classification: ['B/C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 上海浦东 |
| icao | ZSPD |
| category | core |
| operational_phase | arrival |
| fact_id | 上海浦东_core_record_8 |
| source_fact_ids | ['上海浦东_core_record_8'] |
| source_record_ids | ['上海浦东:core:4fc82505866f5d88'] |
| chinese_source_pages | [585] |
| production_source_page_metadata | 448-451 |
| chinese_source_heading | 上海/浦东机场运行特点（ZSPD/PVG） |
| chinese_source_section | 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Shanghai/Pudong', 'iata': 'PVG', 'icao': 'ZSPD', 'start_page': 1354, 'end_page': 1358} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 从BK进场，若向北运行时，通常用西跑道35L号，若向南运行时，通常东跑道16L。 |
| source_original_texts | ['进场：从BK 进场，若向北运行时，通常用西跑道 35L 号，若向南运行时，通常东 跑道 16L。'] |
| pairing_result | For BK arrival:during north-bound operations, RWY 35L (western runway) is normally assigned; |
| chinese_critical_tokens | ['BK', 'RWY35L'] |
| english_critical_tokens | ['BK', 'RWY', 'RWY35L'] |
| failure_reasons | ["中英文关键事实不一致：上海浦东_core_record_8：中文['BK', 'RWY35L']，英文['BK', 'RWY', 'RWY35L']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: For BK arrival:during north-bound operations, RWY 35L (western runway) is normally assigned; during south-bound operations, RWY 16L (eastern runway) is normally assigned.
- core/arrival sequence 1: Multiple arrival procedures are in use, with ad-hoc amendments possible. Direct-to clearances are common during off-peak periods. Maintain contingency plans.
- core/arrival sequence 2: Multiple TA/RA alerts have been recorded during south-bound approaches into Pudong. Prepare contingency measures during approach preparation and execute memory-item procedures per aircraft manual.
- core/arrival sequence 3: For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. When performing “glideslope capture from above” procedure, strictly comply with SOP. If stable-approach criteriacannot be satisfied, execute missed approach or discontinued approach without hesitation.
- core/arrival sequence 4: For RWY 34R approach, tall obstacles exist slightly right-of-track between waypoints PD083 and PD084. Over-flying ator maintaining 600 m may trigger GPWS caution alerts. Follow the operational advisory “Reminder on GPWS Caution Triggers for RWY 34R Approaches at Pudong” available in EFB.

### BEFORE 2026-10-28 error 24 - 9C7290

9C7290：最新版机场手册英文配对缺失：上海浦东_core_record_15：上海浦东／上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／着陆后地面

Classification: ['C']

Page-review findings: []

| Field | Evidence |
|---|---|
| airport | 上海浦东 |
| icao | ZSPD |
| category | core |
| operational_phase | landing_ground |
| fact_id | 上海浦东_core_record_15 |
| source_fact_ids | ['上海浦东_core_record_15'] |
| source_record_ids | ['上海浦东:core:3bfbd83ca010da05'] |
| chinese_source_pages | [586] |
| production_source_page_metadata | 448-451 |
| chinese_source_heading | 上海/浦东机场运行特点（ZSPD/PVG） |
| chinese_source_section | 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／着陆后地面 |
| matched_english_chapter | {'name': 'Shanghai/Pudong', 'iata': 'PVG', 'icao': 'ZSPD', 'start_page': 1354, 'end_page': 1358} |
| pairing_source_phases | ['landing_ground'] |
| selected_chinese_text | 请注意在此类停机位的进位速度。 |
| source_original_texts | ['着陆后地面：近期发生多次浦东机场 168 号停机位，因上坡和单发原因油门加至地面最 大可用推力仍不能移动飞机，而关车申请拖车。请注意在此类停机位的进 位速度。'] |
| pairing_result |  |
| chinese_critical_tokens | [] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：上海浦东_core_record_15：上海浦东／上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／着陆后地面'] |

Same pairing-phase English candidates, in original extraction order:

- core/landing_ground sequence 0: Several recent incidents occurred at Stand 168: due to uphill gradient and single-engine taxi condition, aircraft could not move even with maximum available ground thrust, requiring engine shutdown and tow-in service. Control taxi speed when docking at stands with such gradients.
- core/landing_ground sequence 1: Per Pudong Aerodrome Instructions AD2.20, 3.2.4: “Upon sighting marshalling vehicle, arriving crews shall switch off taxi lights and follow the marshalling vehicle”.
- core/landing_ground sequence 2: When taxiing towards stands equipped with Visual Docking Guidance System (VDGS): stop taxi immediately if receiving ambiguous guidance indications. When entering stands with manual marshalling, stop taxi if ground marshalling personnel are not on-site (frequently encountered after ad-hoc stand change post-landing). Notify ATC promptly, keep engines running and await further instructions.

### BEFORE 2026-10-28 error 25 - 9C7290

9C7290：中英文选定事实身份不一致：中文['曼谷素旺那普_typical_record_1', '上海浦东_typical_record_1', '上海浦东_typical_record_2', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', 'user_confirmed:f7577d379bd6317d8c4c2d68', '上海浦东_core_record_10', '上海浦东_core_record_11', '上海浦东_core_record_12', '上海浦东_core_record_8', '上海浦东_core_record_9', '上海浦东_core_record_15', '上海浦东_core_record_17', '上海浦东_core_record_14', '上海浦东_core_record_5', '上海浦东_core_record_16', '上海浦东_core_record_19']，英文['曼谷素旺那普_typical_record_1', '上海浦东_typical_record_1', '上海浦东_typical_record_2', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', 'user_confirmed:f7577d379bd6317d8c4c2d68', '上海浦东_core_record_10', '上海浦东_core_record_11', '上海浦东_core_record_12', '上海浦东_core_record_8', '上海浦东_core_record_9', '上海浦东_core_record_17', '上海浦东_core_record_14', '上海浦东_core_record_5', '上海浦东_core_record_16', '上海浦东_core_record_19']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

## AFTER: every validation error

### AFTER 2026-10-26 error 1 - 9C7289

9C7289：最新版机场手册英文配对缺失：曼谷素旺那普_core_record_10：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ('曼谷素旺那普_core_record_10',) |
| source_record_ids | ('曼谷素旺那普:core:2c9eb872ff8083ca',) |
| chinese_source_pages | [315] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result |  |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：曼谷素旺那普_core_record_10：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### AFTER 2026-10-26 error 2 - 9C7289

9C7289：中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-WAY']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | 曼谷素旺那普_core_record_41 |
| source_fact_ids | ('曼谷素旺那普_core_record_41',) |
| source_record_ids | ('曼谷素旺那普:core:cb29f683c773c0a8',) |
| chinese_source_pages | [318] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 航图新增Z进近程序为主用程序，数据库也有变化，提示机组注意阅读对应进场图中Warning 中的说明，避免未经ATC许可转向五边加入进近程序。 |
| source_original_texts | ['进场：航图新增Z 进近程序为主用程序，数据库也有变化，提 示机组注意阅读对应进场图中Warning 中的说明，避免未经 ATC 许可转向五边加入进近程序。'] |
| pairing_result | The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance. |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | ['ATC'] |
| failure_reasons | ["中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### AFTER 2026-10-26 error 3 - 9C7289

9C7289：中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ('曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46') |
| source_record_ids | ('曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec') |
| chinese_source_pages | [318] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### AFTER 2026-10-26 error 4 - 9C7289

9C7289：中英文选定事实身份不一致：中文['上海浦东_typical_record_1', '上海浦东_typical_record_2', '曼谷素旺那普_typical_record_1', '上海浦东_core_record_7', '上海浦东_core_record_3', '上海浦东_core_record_5', '上海浦东_core_record_6', 'user_confirmed:f7577d379bd6317d8c4c2d68', '上海浦东_core_record_19', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_10', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']，英文['上海浦东_typical_record_1', '上海浦东_typical_record_2', '曼谷素旺那普_typical_record_1', '上海浦东_core_record_7', '上海浦东_core_record_3', '上海浦东_core_record_5', '上海浦东_core_record_6', 'user_confirmed:f7577d379bd6317d8c4c2d68', '上海浦东_core_record_19', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

### AFTER 2026-10-26 error 5 - 9C7420

9C7420：中英文关键事实不一致：广州白云_core_record_40：中文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19']，英文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19']

Classification: ['D']

Page-review findings: ['D-ZGGG-W19']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | navigation |
| fact_id | 广州白云_core_record_40 |
| source_fact_ids | ('广州白云_core_record_40',) |
| source_record_ids | ('广州白云:core:c9f2ac8896ce0bac',) |
| chinese_source_pages | [987] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／航路 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['navigation'] |
| selected_chinese_text | 将W19航线MASGU-MABAG-OGABI-NOMAR航段调整为MASGU-UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃珠三角航班使用。 |
| source_original_texts | ['航路：将W19航线MASGU-MABAG-OGABI-NOMAR 航段调整为MASGU-UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃 珠三角航班使用。'] |
| pairing_result | The W19 route segment MASGU-MABAG-OGABI- NOMAR will be adjusted to MASGU-UPMIP-ATKAV- OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China. |
| chinese_critical_tokens | ['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19'] |
| english_critical_tokens | ['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19'] |
| failure_reasons | ["中英文关键事实不一致：广州白云_core_record_40：中文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OGABI', 'OLPAB', 'UPMIP', 'W19']，英文['ATKAV', 'MABAG', 'MASGU', 'NOMAR', 'OBLAP', 'OGABI', 'UPMIP', 'W19']"] |

Same pairing-phase English candidates, in original extraction order:

- core/navigation sequence 0: The W19 route segment MASGU-MABAG-OGABI- NOMAR will be adjusted to MASGU-UPMIP-ATKAV- OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China.
- core/navigation sequence 1: The Guangzhou-Langman border crossing isdesignated as ASSAD.
- core/navigation sequence 2: The flight from Guangzhou to Ningbo will firstjoin the XEBUL air route, then transfer to the H25 route to VETIB. After VETIB, itwill switch to the W155 route to TEBON, then rejoin the A470 and B221 routes via DST before returning to the original route. During the preparation phase, passengers should mentally prepare for potential last-minute air trafficcontrol changes to avoid panic.

### AFTER 2026-10-26 error 6 - 9C7420

9C7420：最新版机场手册英文配对缺失：广州白云_core_record_45：广州白云／广州/白云机场运行特点／核心威胁与运行特点／进场

Classification: ['D']

Page-review findings: ['D-ZGGG-180']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | arrival |
| fact_id | 广州白云_core_record_45 |
| source_fact_ids | ('广州白云_core_record_45',) |
| source_record_ids | ('广州白云:core:c86df9922ff0cc1f',) |
| chinese_source_pages | [987] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 会指挥速度180到8海里，尽量满足避免造成间隔不够。 |
| source_original_texts | ['进场：会指挥速度180到8海里，尽量满足避免造成间隔不够。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_45：广州白云／广州/白云机场运行特点／核心威胁与运行特点／进场'] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: After entering the field,radar guidance will be used to calculate the altitude-to-range ratio.
- core/arrival sequence 1: The vessel shall maintain a speed of 180 to 8 knots, ensuring sufficient spacing to avoid insufficient intervals.
- core/arrival sequence 2: After the Guangzhou 01L aircraft landed, when directing the GREEN 1 aircraft, the E left-turn signal for T3 was absent on the leftside, and no ground indicator showed the approach to T3. Only an approach to T4 was indicated, with a signal light at T4, which could easily cause confusion.

### AFTER 2026-10-26 error 7 - 9C7420

9C7420：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5：广州白云／广州/白云机场运行特点／核心威胁与运行特点 | 广州/白云机场运行特点／核心威胁与运行特点／地面 | 广州/白云机场运行特点／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-ZGGG-919R']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | approach |
| fact_id | paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5 |
| source_fact_ids | ('广州白云_core_record_4', '广州白云_core_record_19', '广州白云_core_record_5') |
| source_record_ids | ('广州白云:core:866ec61b16fc342a', '广州白云:core:74147675ed67abd8', '广州白云:core:a173ff5e7969d2ed') |
| chinese_source_pages | [983, 984] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点 \| 广州/白云机场运行特点／核心威胁与运行特点／地面 \| 广州/白云机场运行特点／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['core', 'ground'] |
| selected_chinese_text | 公司对广州落地飞机有单发滑行要求，某些较短窄停机位进位时注意转弯速度，如J3上的停机位等。01L落地后，滑行道E J23到J14段有较明显上坡，建议在此之后执行单发滑行。 |
| source_original_texts | ['01L落地后，滑行道E J23到J14段有较明显上坡，建议 在此之后执行单发滑行。', '地面：公司对广州落地飞机有单发滑行要求，某些较短窄停 机位进位时注意转弯速度，如J3上的停机位等。', '广州 机位919R 不建议单发滑行.。'] |
| pairing_result | After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section. The company requires single-engine taxiing for aircraft landing in Guangzhou, with particular attention to turning speed when approaching shorter and narrower aprons, such as those on the J3 apron. |
| chinese_critical_tokens | ['J14', 'J23', 'J3', 'RWY01L'] |
| english_critical_tokens | ['J14', 'J23', 'J3', 'RWY01L'] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5：广州白云／广州/白云机场运行特点／核心威胁与运行特点 \| 广州/白云机场运行特点／核心威胁与运行特点／地面 \| 广州/白云机场运行特点／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: The departure taxiway ismarked as "YELLOW", and the arrival taxiway is marked as "GREEN".
- core/core sequence 1: In case of discrepancy between the flight plan's re-flight altitude and the air traffic control command, the latter shall prevail.
- core/core sequence 2: After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section.
- core/core sequence 3: Meteorological characteristics: From late spring to summer, thunderstorms are frequent, with severe thunderstorms often accompanied by low-level wind shear. During summer and autumn, typhoons exert influence, bringing widespread strong winds, heavy rainfall, and thunderstorms.
- core/core sequence 4: The airport ishighly busy with multiple adjacent airports, requiring strict compliance with air trafficcontrol directives to prevent conflicts.
- core/core sequence 5: Adjust the single-shot acceleration altitude according to the fly Smart modification.
- core/core sequence 6: The new procedure involves adjustments to multiple programs and name changes, with height restrictions requiring modifications. Please refer to the air chart for MCDU data verification.
- core/core sequence 7: New airport runways pose risks of misidentification, misdirection, or land to wrong way. Crews must stay vigilant, enforce standardized announcements and cross-checking procedures, especially during low visibility, rain, or night operations, to prevent runway confusion.
- core/ground sequence 0: No need to recite PDC
- core/ground sequence 1: The departure taxiway is designated as "YELLOW", while the arrival taxiway is "GREEN". Pilots must familiarize themselves with the specific taxiway number before each run, as itcorresponds to the standard taxiway for both departure and arrival. During approach preparation, they should review the taxiway chart in advance. If the crew needs to deviate from the runway, they must promptly confirm the turn direction with air traffic control.
- core/ground sequence 2: Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.
- core/ground sequence 3: When the lead vehicle approaches, the ground commander acts as its driver. Upon reaching the target position, the commander must control the speed and guide the driver to disembark.
- core/ground sequence 4: The company requires single-engine taxiing for aircraft landing in Guangzhou, with particular attention to turning speed when approaching shorter and narrower aprons, such as those on the J3 apron.
- core/ground sequence 5: The green password for the covered bridge is 202510 (marked with a green√). For international flights entering through boarding gates, please call the access control phone (marked beside the gate) to open the door.
- core/ground sequence 6: At Guangzhou O2 R, the M taxiway is operational while the T64 taxiway lacks signage, with only ground taxiway markers visible. The T64 sign is actually positioned behind the taxiway, which may cause confusion.

### AFTER 2026-10-26 error 8 - 9C7420

9C7420：中英文选定事实身份不一致：中文['曼谷素旺那普_typical_record_1', '广州白云_typical_record_1', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', '广州白云_core_record_40', '广州白云_core_record_45', '广州白云_core_record_6', '广州白云_core_record_15', 'paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5']，英文['曼谷素旺那普_typical_record_1', '广州白云_typical_record_1', '曼谷素旺那普_core_record_17', '曼谷素旺那普_core_record_25', '曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_32', '曼谷素旺那普_core_record_28', '曼谷素旺那普_core_record_30', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_36', '广州白云_core_record_40', '广州白云_core_record_15', 'paragraph:广州白云_core_record_4+广州白云_core_record_19+广州白云_core_record_5']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

### AFTER 2026-10-28 error 1 - 9C7419

9C7419：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_23+广州白云_core_record_27：广州白云／广州/白云机场运行特点／核心威胁与运行特点／地面

Classification: ['A']

Page-review findings: ['A-ZGGG-PUSHBACK']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | ground |
| fact_id | paragraph:广州白云_core_record_23+广州白云_core_record_27 |
| source_fact_ids | ('广州白云_core_record_23', '广州白云_core_record_27') |
| source_record_ids | ('广州白云:core:9bbbbc56abd69b8b',) |
| chinese_source_pages | [986] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／地面 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['ground'] |
| selected_chinese_text | 广州T3，939附近机位，管制给推出指令，可以推开，推到R3，跑道01R。建议设计特定推出程序，或者给出明确清晰推出指令。 |
| source_original_texts | ['地面：广州T3，939附近机位，管制给推出指令，可以推 开，推到R3，跑道01R。机务可能只推到大概正对838到939 之间的位置。这个时候应提醒机务往前拉一点，尽量满足推 到R3上。因R3，R4，R5连接处有点滑行区域没有标注，在推 出过程中管制指令和机务行为有时候不够统一，务必多留心。建议设计特定推出程序，或者给出明确清晰推出指令。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC', 'R3', 'RWY01R', 'T3'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_23+广州白云_core_record_27：广州白云／广州/白云机场运行特点／核心威胁与运行特点／地面'] |

Same pairing-phase English candidates, in original extraction order:

- core/ground sequence 0: No need to recite PDC
- core/ground sequence 1: The departure taxiway is designated as "YELLOW", while the arrival taxiway is "GREEN". Pilots must familiarize themselves with the specific taxiway number before each run, as itcorresponds to the standard taxiway for both departure and arrival. During approach preparation, they should review the taxiway chart in advance. If the crew needs to deviate from the runway, they must promptly confirm the turn direction with air traffic control.
- core/ground sequence 2: Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.
- core/ground sequence 3: When the lead vehicle approaches, the ground commander acts as its driver. Upon reaching the target position, the commander must control the speed and guide the driver to disembark.
- core/ground sequence 4: The company requires single-engine taxiing for aircraft landing in Guangzhou, with particular attention to turning speed when approaching shorter and narrower aprons, such as those on the J3 apron.
- core/ground sequence 5: The green password for the covered bridge is 202510 (marked with a green√). For international flights entering through boarding gates, please call the access control phone (marked beside the gate) to open the door.
- core/ground sequence 6: At Guangzhou O2 R, the M taxiway is operational while the T64 taxiway lacks signage, with only ground taxiway markers visible. The T64 sign is actually positioned behind the taxiway, which may cause confusion.

### AFTER 2026-10-28 error 2 - 9C7419

9C7419：最新版机场手册英文配对缺失：paragraph:广州白云_core_record_34+广州白云_core_record_35：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场

Classification: ['A']

Page-review findings: ['A-ZGGG-NORTH-DEPARTURE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | paragraph:广州白云_core_record_34+广州白云_core_record_35 |
| source_fact_ids | ('广州白云_core_record_34', '广州白云_core_record_35') |
| source_record_ids | ('广州白云:core:2422ee6d04561eeb',) |
| chinese_source_pages | [986] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／离场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['departure'] |
| selected_chinese_text | 广州早出港航班，向北起飞，有时管制指挥使用跑道02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着的是P13并不是02R跑道头。 |
| source_original_texts | ['离场：广州早出港航班，向北起飞，有时管制指挥使用跑道 02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着 的是P13并不是02R跑道头。Y18为跑道02R跑道等待点，转向 Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。'] |
| pairing_result |  |
| chinese_critical_tokens | ['ATC', 'P13', 'RWY02L', 'RWY02R'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：paragraph:广州白云_core_record_34+广州白云_core_record_35：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场'] |

Same pairing-phase English candidates, in original extraction order:

- core/departure sequence 0: The aircraft automatically disengages from the wave contact after leaving the ground and approaches, with the specific frequency provided by the airtraffic control.
- core/departure sequence 1: Ifthe SID has speed restrictions, you may apply to cancel them; otherwise, you must comply.
- core/departure sequence 2: Departing from Lanzhou may be directed to fly directly to P268 or P118, then join the X64 temporary route to QP. Departing from Southeast Asia may be directed to fly directly to P50, then join the X66 temporary route to BIGRO.
- core/departure sequence 3: Precautions: For early departure flights, select the departure runway based on real-time airtraffic updates and clearance requirements.

### AFTER 2026-10-28 error 3 - 9C7419

9C7419：最新版机场手册英文配对缺失：广州白云_core_record_11：广州白云／广州/白云机场运行特点／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-ZGGG-BRAKE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | 广州白云_core_record_11 |
| source_fact_ids | ('广州白云_core_record_11',) |
| source_record_ids | ('广州白云:core:6328ded28cd58d53',) |
| chinese_source_pages | [983] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 广州涉及航线距离较长，飞机起飞重量大，从T3滑行至01R/19L地面滑行时间长，且道面坡度起伏和转弯多，易造成刹车温度高，导致航班延误或起飞后机轮温度超限情况，请机组注意。 |
| source_original_texts | ['广州涉及航线距离较长，飞机起飞重量大，从T3滑行 至01R/19L地面滑行时间长，且道面坡度起伏和转弯多，易 造成刹车温度高，导致航班延误或起飞后机轮温度超限情况，请机组注意。'] |
| pairing_result |  |
| chinese_critical_tokens | ['RWY01R', 'RWY19L', 'T3'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_11：广州白云／广州/白云机场运行特点／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: The departure taxiway ismarked as "YELLOW", and the arrival taxiway is marked as "GREEN".
- core/core sequence 1: In case of discrepancy between the flight plan's re-flight altitude and the air traffic control command, the latter shall prevail.
- core/core sequence 2: After landing at 01L, the taxiway from E J23 to J14 features a steep incline. We recommend performing a single-engine taxi after this section.
- core/core sequence 3: Meteorological characteristics: From late spring to summer, thunderstorms are frequent, with severe thunderstorms often accompanied by low-level wind shear. During summer and autumn, typhoons exert influence, bringing widespread strong winds, heavy rainfall, and thunderstorms.
- core/core sequence 4: The airport ishighly busy with multiple adjacent airports, requiring strict compliance with air trafficcontrol directives to prevent conflicts.
- core/core sequence 5: Adjust the single-shot acceleration altitude according to the fly Smart modification.
- core/core sequence 6: The new procedure involves adjustments to multiple programs and name changes, with height restrictions requiring modifications. Please refer to the air chart for MCDU data verification.
- core/core sequence 7: New airport runways pose risks of misidentification, misdirection, or land to wrong way. Crews must stay vigilant, enforce standardized announcements and cross-checking procedures, especially during low visibility, rain, or night operations, to prevent runway confusion.

### AFTER 2026-10-28 error 4 - 9C7419

9C7419：最新版机场手册英文配对缺失：广州白云_core_record_36：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场

Classification: ['A']

Page-review findings: ['A-ZGGG-NORTH-DEPARTURE']

| Field | Evidence |
|---|---|
| airport | 广州白云 |
| icao | ZGGG |
| category | core |
| operational_phase | departure |
| fact_id | 广州白云_core_record_36 |
| source_fact_ids | ('广州白云_core_record_36',) |
| source_record_ids | ('广州白云:core:2422ee6d04561eeb',) |
| chinese_source_pages | [986] |
| production_source_page_metadata | 983-987 |
| chinese_source_heading | 广州/白云机场运行特点 |
| chinese_source_section | 广州/白云机场运行特点／核心威胁与运行特点／离场 |
| matched_english_chapter | {'name': 'GUANGZHOU BAIYUN', 'iata': 'CAN', 'icao': 'ZGGG', 'start_page': 1563, 'end_page': 1566} |
| pairing_source_phases | ['departure'] |
| selected_chinese_text | Y18为跑道02R跑道等待点，转向Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。 |
| source_original_texts | ['离场：广州早出港航班，向北起飞，有时管制指挥使用跑道 02R起飞。需要穿越跑道02L，需要注意穿越跑道之后正对着 的是P13并不是02R跑道头。Y18为跑道02R跑道等待点，转向 Y时需要注意，Y18并非为Y尽头，注意滑行速度，避免滑过。'] |
| pairing_result |  |
| chinese_critical_tokens | ['RWY02R', 'Y18'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：广州白云_core_record_36：广州白云／广州/白云机场运行特点／核心威胁与运行特点／离场'] |

Same pairing-phase English candidates, in original extraction order:

- core/departure sequence 0: The aircraft automatically disengages from the wave contact after leaving the ground and approaches, with the specific frequency provided by the airtraffic control.
- core/departure sequence 1: Ifthe SID has speed restrictions, you may apply to cancel them; otherwise, you must comply.
- core/departure sequence 2: Departing from Lanzhou may be directed to fly directly to P268 or P118, then join the X64 temporary route to QP. Departing from Southeast Asia may be directed to fly directly to P50, then join the X66 temporary route to BIGRO.
- core/departure sequence 3: Precautions: For early departure flights, select the departure runway based on real-time airtraffic updates and clearance requirements.

### AFTER 2026-10-28 error 5 - 9C7419

9C7419：最新版机场手册英文配对缺失：曼谷素旺那普_core_record_10：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点

Classification: ['A']

Page-review findings: ['A-VTBS-STAR']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | approach |
| fact_id | 曼谷素旺那普_core_record_10 |
| source_fact_ids | ('曼谷素旺那普_core_record_10',) |
| source_record_ids | ('曼谷素旺那普:core:2c9eb872ff8083ca',) |
| chinese_source_pages | [315] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['core'] |
| selected_chinese_text | 曼谷进近只给出进场STAR程序，不告知跑道，虽然通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑道，机组建立五边之前务必证实跑道和进近方式。 |
| source_original_texts | ['曼谷进近只给出进场STAR 程序，不告知跑道，虽然 通波只告知一条进近跑道，但仍有可能使用通波没有列出的跑 道，机组建立五边之前务必证实跑道和进近方式。滑行道不平整如果 N1-50%时仍无法滑出，需要拖车。'] |
| pairing_result |  |
| chinese_critical_tokens | ['STAR'] |
| english_critical_tokens | [] |
| failure_reasons | ['最新版机场手册英文配对缺失：曼谷素旺那普_core_record_10：曼谷素旺那普／曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点'] |

Same pairing-phase English candidates, in original extraction order:

- core/core sequence 0: Special complex procedures: During the deployment of some aircraft positions, the system may temporarily halt to issue an engine startcommand, after which itwill resume aircraft traction. The crew must carefully heed the instructions and avoid sudden braking, as this could risk shearing pin fracture.
- core/core sequence 1: Single-engine taxiing is not recommended when the taxi route is expected to include asphalt pavement.
- core/core sequence 2: In case of communication failure, follow the airchart or airport regulations.
- core/core sequence 3: The airspace is abnormally busy with short intervals, and the waiting time may differ from standard waiting periods. Please verify this.
- core/core sequence 4: Three runways will be operational: The original 01R/19L runway will be renamed 01/19, and the former 01L/19R runway will be renamed 02R/20L. The third runway, 02L/20R, will serve as a non-precision approach runway, allowing the use of the RNP approach procedure.
- core/core sequence 5: South approach and departure: 19 for takeoff and landing, 20L for takeoff, 20R for landing. North approach and departure: 01 for takeoff and landing, 02R for takeoff, 02L for landing.
- core/core sequence 6: Pavement characteristics: If the skidway is uneven and the vehicle stillcannot be moved out when the N1-50% threshold isreached, a tow truck is required.
- core/core sequence 7: Meteorological characteristics: Frequent thunderstorms in summer
- core/core sequence 8: Navigation facilities: The SVB station has been inactive for an extended period due to relocation, resulting in the absence of VOR approach procedures. The blind landing range finder exhibits positional inaccuracies relative to the runway end, which may cause operational instability.
- core/core sequence 9: Frequent military exercises often involve route changes. Please check against the flight plan.
- core/core sequence 10: During RNP approach procedures at this airport, ATC instructions may differ from the procedure design logic. Compliance with company FOIB.

### AFTER 2026-10-28 error 6 - 9C7419

9C7419：中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-WAY']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | 曼谷素旺那普_core_record_41 |
| source_fact_ids | ('曼谷素旺那普_core_record_41',) |
| source_record_ids | ('曼谷素旺那普:core:cb29f683c773c0a8',) |
| chinese_source_pages | [318] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 航图新增Z进近程序为主用程序，数据库也有变化，提示机组注意阅读对应进场图中Warning 中的说明，避免未经ATC许可转向五边加入进近程序。 |
| source_original_texts | ['进场：航图新增Z 进近程序为主用程序，数据库也有变化，提 示机组注意阅读对应进场图中Warning 中的说明，避免未经 ATC 许可转向五边加入进近程序。'] |
| pairing_result | The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance. |
| chinese_critical_tokens | ['ATC'] |
| english_critical_tokens | ['ATC'] |
| failure_reasons | ["中英文关键概念不一致：曼谷素旺那普_core_record_41：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### AFTER 2026-10-28 error 7 - 9C7419

9C7419：中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-VTBS-FIVE-SIDES']

| Field | Evidence |
|---|---|
| airport | 曼谷素旺那普 |
| icao | VTBS |
| category | core |
| operational_phase | arrival |
| fact_id | paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46 |
| source_fact_ids | ('曼谷素旺那普_core_record_42', '曼谷素旺那普_core_record_43', '曼谷素旺那普_core_record_44', '曼谷素旺那普_core_record_45', '曼谷素旺那普_core_record_46') |
| source_record_ids | ('曼谷素旺那普:core:15735735141c21a3', '曼谷素旺那普:core:8c5489785e54caec') |
| chinese_source_pages | [318] |
| production_source_page_metadata | 315-327 |
| chinese_source_heading | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) |
| chinese_source_section | 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Suvarnabhumi', 'iata': 'BKK', 'icao': 'VTBS', 'start_page': 1163, 'end_page': 1176} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 执行VTBS 20R RNP进近需要注意。ATKIN之后转5边的航段， 管制可能会指令“maintain 5000ft，turn right HDG 165，intercept final course 20R，report established.”注意管制是要求先建立20R RNP的五边，而不是许可RNP进近，注意证实指令，防止误待命APPR。随后会让下3500ft，可以RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP进近不允许执行“高截获”程序。02L进近常指挥保持3边航向，控制前后机距离，之后指挥直飞BATEM或ABVER，在引入02LRNP进近计划时MCDU会提示选择VIA BATEM如果没有选择VIA计划上看不到BATEM点。 |
| source_original_texts | ['进场：执行 VTBS 20R RNP 进近需要注意。ATKIN 之后转 5 边的 航段， 管制可能会指令“maintain 5000ft，turn right HDG 165,intercept final course 20R,report established.”注意 管制是要求先建立20R RNP 的五边，而不是许可 RNP 进近,注意 证实指令，防止误待命APPR。随后会让下3500ft，可以 RNP20R，容易造成能量大，机组注意做好预案，防止不稳定。RNP 进近不 允许执行“高截获”程序。', '进场：02L进近 常指挥保持3 边航向，控制前后机距离，之后 指挥直飞BATEM 或ABVER，在引入02LRNP 进近计划时MCDU会提 示选择VIA BATEM 如果没有选择VIA 计划上看不到BATEM 点。'] |
| pairing_result | When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches. During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan. |
| chinese_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| english_critical_tokens | ['3500FT', '5000FT', 'ABVER', 'APPR', 'ATC', 'ATKIN', 'BATEM', 'HDG', 'MCDU', 'RNP', 'RWY02L', 'RWY20R', 'VIA', 'VTBS'] |
| failure_reasons | ["中英文关键概念不一致：paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: Common procedures: RNAV entry
- core/arrival sequence 1: The minimum horizontal spacing of radar is5nm, and itmay be reduced to 3nm inBKKTMA, BKKCTR, and Suvarnabhumi ATZ.
- core/arrival sequence 2: Speed limits: Refer to the speed limits in Bangkok Terminal Area Chart 20-1P5. At 10,000 feet or below... maintain 250 knots unless ATC issues a 'No ATC speed restrictions' clearance. During intermediate approach, fly at 210 knots. In final approach, intercept or approach ILS course at 160-180 knots. When establishing ILS, maintain 160 knots.
- core/arrival sequence 3: The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.
- core/arrival sequence 4: When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.
- core/arrival sequence 5: During 02L approach, the controller typically maintains a three-way approach while controlling the aircraft's distance from the front and rear. Subsequently, the controller directs the aircraft to fly directly to BATEM or ABVER. When initiating the 02LRNP approach plan, the MCDU will prompt the pilot to select VIA BATEM. If VIA is not selected, the BATEM point will not be visible on the plan.
- core/arrival sequence 6: For aircraft landing on 02L, execute F/W runway approach and wait outside the runway. Use W to cross the runway and proceed straight ahead. D4: Switch to 121.95 frequency to directly approach the parking position and taxi route. For example, S123 D taxi G, proceed forward, wait, then taxi to T18 or T19 for position change. Airport regulations specify: After landing on 02L/20R, do not remain on the quick departure runway to await taxi instructions. If no instructions are given, 02L should proceed toF/W approach and wait outside the runway, while 20R should proceed to F/Z approach and wait outside the runway.
- core/arrival sequence 7: Our aircraft is typically parked at Satellite-1 Hall-1. At Suvarnabhumi Airport, a PDC is available. Once the PDC is confirmed, there's no need for repetition — simply contact ground control to request the push-up command. The ground frequency corresponding to the parking position can be found on the AMM chart.
- core/arrival sequence 8: ILS Z 01 BS690 mandatory 1600 RNP 02L BS670 mandatory 1600 ILS Z 19 BS790 mandatory 1600 RNP 20R BS770 mandatory 1600

### AFTER 2026-10-28 error 8 - 9C7419

9C7419：中英文选定事实身份不一致：中文['广州白云_typical_record_1', '曼谷素旺那普_typical_record_1', 'paragraph:广州白云_core_record_23+广州白云_core_record_27', 'paragraph:广州白云_core_record_34+广州白云_core_record_35', '广州白云_core_record_30', '广州白云_core_record_11', '广州白云_core_record_36', '广州白云_core_record_42', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_10', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']，英文['广州白云_typical_record_1', '曼谷素旺那普_typical_record_1', '广州白云_core_record_30', '广州白云_core_record_42', '曼谷素旺那普_core_record_36', '曼谷素旺那普_core_record_13', 'paragraph:曼谷素旺那普_core_record_14+曼谷素旺那普_core_record_5', '曼谷素旺那普_core_record_18', 'paragraph:曼谷素旺那普_core_record_8+曼谷素旺那普_core_record_9+曼谷素旺那普_core_record_6', '曼谷素旺那普_core_record_41', 'paragraph:曼谷素旺那普_core_record_51+曼谷素旺那普_core_record_7+曼谷素旺那普_core_record_15', 'paragraph:曼谷素旺那普_core_record_42+曼谷素旺那普_core_record_43+曼谷素旺那普_core_record_44+曼谷素旺那普_core_record_45+曼谷素旺那普_core_record_46', 'paragraph:曼谷素旺那普_core_record_47+曼谷素旺那普_core_record_48', '曼谷素旺那普_core_record_25', 'paragraph:曼谷素旺那普_core_record_11+曼谷素旺那普_core_record_3']

Classification: ['C (dependent parity failure, guard unchanged)']

Page-review findings: []

Aggregate parity failure caused by the fact-level gaps above. Complete selected fact objects and both ID lists are included in the corresponding JSON expanded_errors entry.

### AFTER 2026-10-28 error 9 - 9C7290

9C7290：中英文关键概念不一致：上海浦东_core_record_11：英文缺少['final_approach']

Classification: ['D']

Page-review findings: ['D-ZSPD-BASE-LEG']

| Field | Evidence |
|---|---|
| airport | 上海浦东 |
| icao | ZSPD |
| category | core |
| operational_phase | arrival |
| fact_id | 上海浦东_core_record_11 |
| source_fact_ids | ('上海浦东_core_record_11',) |
| source_record_ids | ('上海浦东:core:368f05545407d85b',) |
| chinese_source_pages | [585] |
| production_source_page_metadata | 584-587 |
| chinese_source_heading | 上海/浦东机场运行特点（ZSPD/PVG） |
| chinese_source_section | 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点／进场 |
| matched_english_chapter | {'name': 'Shanghai/Pudong', 'iata': 'PVG', 'icao': 'ZSPD', 'start_page': 1354, 'end_page': 1358} |
| pairing_source_phases | ['arrival'] |
| selected_chinese_text | 浦东17R/35L跑道，ATC可能指挥短切五边或较晚发布盲降许可，机组做好预判并提前做好能量管理，积极沟通，按需接受ATC雷达引导的指令。 |
| source_original_texts | ['进场：浦东 17R/35L 跑道，ATC 可能指挥短切五边或较晚发布盲降许可，机组做好 预判并提前做好能量管理，积极沟通，按需接受 ATC 雷达引导的指令。当 需要实施"从上方截获下滑道"程序时，严格遵循 SOP 要求，如无法满足稳 定进近标准，果断复飞或中止进近。'] |
| pairing_result | For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. |
| chinese_critical_tokens | ['ATC', 'ILS', 'RWY17R', 'RWY35L'] |
| english_critical_tokens | ['ATC', 'ILS', 'RWY17R', 'RWY35L'] |
| failure_reasons | ["中英文关键概念不一致：上海浦东_core_record_11：英文缺少['final_approach']"] |

Same pairing-phase English candidates, in original extraction order:

- core/arrival sequence 0: For BK arrival:during north-bound operations, RWY 35L (western runway) is normally assigned; during south-bound operations, RWY 16L (eastern runway) is normally assigned.
- core/arrival sequence 1: Multiple arrival procedures are in use, with ad-hoc amendments possible. Direct-to clearances are common during off-peak periods. Maintain contingency plans.
- core/arrival sequence 2: Multiple TA/RA alerts have been recorded during south-bound approaches into Pudong. Prepare contingency measures during approach preparation and execute memory-item procedures per aircraft manual.
- core/arrival sequence 3: For RWY 17R / 35L, ATC may assign short base-leg vectors or issue ILS clearance at a late stage. Anticipate such scenarios, conduct proactive energy management, maintain active communication and accept ATC radar vectors as required. When performing “glideslope capture from above” procedure, strictly comply with SOP. If stable-approach criteriacannot be satisfied, execute missed approach or discontinued approach without hesitation.
- core/arrival sequence 4: For RWY 34R approach, tall obstacles exist slightly right-of-track between waypoints PD083 and PD084. Over-flying ator maintaining 600 m may trigger GPWS caution alerts. Follow the operational advisory “Reminder on GPWS Caution Triggers for RWY 34R Approaches at Pudong” available in EFB.
