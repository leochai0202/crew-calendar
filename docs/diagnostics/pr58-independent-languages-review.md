# PR #58：中英文独立原文选材验收（Draft）

基线 `de599876d650eb5788f60ae053aa2298c2e48ceb`。本轮按用户最新正式确认取消逐条双语对应的发布门槛，不修改 main，不合并，不触发生产。

**MERGE_READY=false。下面的真实正文仍为 FAILED_SAFE 诊断预览，不能发送或发布。**

## 当前权威输入

- 手册版本：20261019；SHA256：`e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`；手册本体未改。
- 实际任务使用只读 `26e9391e6053c7223386346f0e90be2dbc5b6644:flight.ics` 的临时复制件，以保持与前轮相同输入；没有覆盖工作区 ICS。
- 本轮重新扫描：177 个中文章节、83 个英文入口、82 个中文章节按 ICAO 绑定；身份错误 0，英文范围交叠 0，354 个中文角色探针中 opposite-only 0、重复文本 0。结构扫描不等于所有机场正文合格。
- 重点机场及扩展格式样本仍见两份 audit；ZPLJ 英文章节尚未可靠定位，保持 B 类解析/定位待核查，不能称为“英文不存在”。

## 通用实现

1. 完整英文章节恢复后保存独立英文来源记录（原文、文件、版本、页、章节、阶段、序号和自己的稳定 ID），不再从中文选中列表生成英文集合。
2. 中文选材链保持既有完整章节扫描、来源、角色、航线、条件及质量门槛。英文独立执行同类筛选，并保留原文和排除原因；不翻译、不借旧 CURATED、不用 concept fallback，不固定段落条数。
3. 明确的进离场阶段是硬门槛；跑道尺寸/标高是基础运行属性，PAPI 属进场；未知实际跑道的原文条件继续保留。英文独立检查方向性 ICAO 航线、配置航线、班号、完整日期窗口、季节/月范围和明确昼夜条件。
4. 通用行政过滤补充餐单、通关、接送、航站交通及孤立频率残片；机位引导、加油消防/上客限制、通信失效和特殊换频不随之删除。明确 `For AAAA-BBBB` 仍按方向筛选，不误套到其他航线。
5. 每种语言各自校验完整权威来源和原文投影；英文不得丢掉条件、改数字或插入无来源内容。输出层沿用主语省略，保留义务强度和历史事件主体；只去纯结构标签，不改运行数据。
6. 旧 `validate_bilingual_facts` / ID parity 只保留辅助诊断。缺少对应、段落数不同、顺序不同、ID 不同不再自动阻断。没有可靠英文必要机场资料仍阻断。
7. 对可明确定位到同一关键要求的真实冲突，独立执行时序、动作、跑道关联、程序/FIX、关键数量/单位保护。不能因某语言的角色筛选而掩盖另一语言已选要求的已知原文矛盾。额外英文事实或中文未写某生效日期本身不证明矛盾。
8. 所有组全部通过后才走既有正式写入门槛。连续/不连续分组、外籍双语、last-good 和 FAILED_SAFE 不变。

## 实际隔离结果

旧结果 14 / 19 的阻断项包含强制逐条对应。本轮将缺对应改为诊断，同时加入独立英文质量门槛；**不能把错误数量变化当作修复了同等数量的手册原文问题**。

| 日期 | 航班组 | 中文独立事实 | 英文独立事实 | 非阻断配对诊断 |
|---|---|---:|---:|---:|
| 2026-10-26 | 9C7289 | 39 | 42 | 5 |
| 2026-10-26 | 9C7420 | 47 | 53 | 9 |
| 2026-10-28 | 9C7419 | 57 | 60 | 16 |
| 2026-10-28 | 9C7290 | 36 | 41 | 3 |

两天各 **8 条阻断错误**；`.success=false`，新正式正文文件 0，四个 dated/latest 中英文 last-good 哨兵均逐项保留。当前不具备真实任务发布条件。

### 仍然阻断的来源问题

- TCAS 启停时序（中文 314 / 英文 1171）、起飞滑跑与 taxiing（315 / 1171）不是同义表达。
- 跑道分配（987 / 1581）、W19 OLPAB/OBLAP（990 / 1582）、180 至 8 海里与 180 to 8 knots（991 / 1583）保持冲突，不选择任一拼写或单位。
- PAPI 跑道/MEHT 关联（586 / 1367）保持冲突。英文原页确有 `RWY 17R: 35L:` 的歧义结构，不能擅改成正确表格。
- 英文原页 `five-way turns`（1172）、`RNP five sides`（1172–1173）、`Automatic wave separation`（1171）及 `disengages from the wave contact`（1582）无法可靠当作对应运行概念，保持英文质量 FAILED_SAFE，不自动润色为新含义。
- 原先仅缺对应的 STAR/跑道证实、919R、T61/Y19 等中文条目不因英文无对应而失败；也不把别的英文条目或模型翻译塞入其位置。
- 雅加达扩展回归仍保护 AMBOY 2F/2M 冲突（391 / 1201）。取消 parity 没有使其放行。

### 人工正文审阅与未完成项

已读两天四组实际渲染正文，并再次查看 1171、1172、1173、1367、1581–1583 等原始页。英文行政内容和明确其他 ICAO 航线已剔除；机坪/ATC 主体、运行条件、关键值保留，未添加机场内部二级标题/编号。

仍不能宣称正文合格：
- 英文仍有手册原印的错误运行表达、OCR 连词和不自然措辞；不得把“有来源”直接等同“可发布”。
- 某些英文只写城市名的航线（没有可靠机场别名/ICAO）仍需补充可靠身份解析，不能猜城市对应哪个机场。来源方向语义如 `Departing from` / 中文“往某方向离场”也不能自行统一。
- 长列表提示尾句、轻度重复、来源本身的术语问题尚需源文证据支持的整理；本轮未假报全部机场质量已通过。
- 不能可靠定位的英文机场章节仍需原始目录/页面核查。缺失候选不是源文件无英文的证据。
- 确认的关键矛盾需公司权威修订/可靠资料，不可通过继续调整算法或删除中文事实掩盖。

## 每一条当前阻断错误的来源证据

这是诊断，不写入正式正文。以下英文独立事实无需有中文对应；引用中文对应仅用于已确认关键矛盾核查。

### 2026-10-26

#### 1. 9C7289 / 曼谷素旺那普

9C7289：中英文权威来源关键运行冲突：曼谷素旺那普_core_record_17：['system_activation_temporal_polarity']；中文页314；英文页1171

- fact ID：`曼谷素旺那普_core_record_17`
- source record：`曼谷素旺那普:core:6785143081757f96`
- category / phase：core / ground
- 来源栏目：曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) / 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点
- 中文页：314；英文页：1171

中文选中原文：

> 为防止可能的干扰，对离港飞机，直到收到进入或者对 正跑道指令才打开 TCAS；对于进港飞机，直到脱离跑道再关闭。

用于核查关键冲突的英文原文：

> To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.

#### 2. 9C7289 / 曼谷素旺那普

9C7289英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:762728438175820a；源页1172

- fact ID：`曼谷素旺那普:en:762728438175820a`
- source record：`曼谷素旺那普:en:762728438175820a`
- category / phase：core / arrival
- 来源栏目：Suvarnabhumi / VTBS / English / core / arrival
- 中文页：不要求逐条对应；英文页：1172

英文独立来源原文：

> The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.

#### 3. 9C7289 / 曼谷素旺那普

9C7289英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:b6c12b97473d3ea3；源页1172-1173

- fact ID：`曼谷素旺那普:en:b6c12b97473d3ea3`
- source record：`曼谷素旺那普:en:b6c12b97473d3ea3`
- category / phase：core / arrival
- 来源栏目：Suvarnabhumi / VTBS / English / core / arrival
- 中文页：不要求逐条对应；英文页：1172-1173

英文独立来源原文：

> When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.

#### 4. 9C7420 / 曼谷素旺那普

9C7420：中英文权威来源关键运行冲突：曼谷素旺那普_core_record_23：['takeoff_roll']；中文页315；英文页1171

- fact ID：`曼谷素旺那普_core_record_23`
- source record：`曼谷素旺那普:core:098da864b419e70f`
- category / phase：core / departure
- 来源栏目：曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) / 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点
- 中文页：315；英文页：1171

中文选中原文：

> 为减少跑道占用时间，飞行员应确保在收到起飞 许可后能立即开始起飞滑跑。

用于核查关键冲突的英文原文：

> To minimize runway time, pilots must ensure they can begin taxiing immediately upon receiving the takeoff clearance.

#### 5. 9C7420 / 广州白云

9C7420：中英文权威来源关键运行冲突：广州白云_core_record_42：['operating_quantity_or_unit_conflict']；中文页991；英文页1583

- fact ID：`广州白云_core_record_42`
- source record：`广州白云:core:c86df9922ff0cc1f`
- category / phase：core / arrival
- 来源栏目：广州/白云机场运行特点 / 广州/白云机场运行特点／核心威胁与运行特点
- 中文页：991；英文页：1583

中文选中原文：

> 会指挥速度180到8海里，尽量满足避免造成间隔不够。

用于核查关键冲突的英文原文：

> The vessel shall maintain a speed of 180 to 8 knots, ensuring sufficient spacing to avoid insufficient intervals.

#### 6. 9C7420 / 广州白云

9C7420：中英文权威来源关键运行冲突：广州白云_core_record_22：['procedure_or_waypoint_conflict', 'runway_requirement_conflict']；中文页987；英文页1581

- fact ID：`广州白云_core_record_22`
- source record：`广州白云:core:ecc6ab7e4fca5257`
- category / phase：core / ground
- 来源栏目：广州/白云机场运行特点 / 广州/白云机场运行特点／核心威胁与运行特点
- 中文页：987；英文页：1581

中文选中原文：

> 跑道运行规则：向北运行：RWYO1L主要用于进场；RWYO1R 主要用于离场；RWYO2L主要用于离场；RWYO2R 主要 用于进场；RWY03进、离场混合运行。向南运行：RWY19R 主要用于进场；RWY19L 主要用于离场；RWY20R 主要用于离场；RWY20L 主要用于进场；RWY21 进、离场混合运行。

用于核查关键冲突的英文原文：

> Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.

#### 7. 9C7420 / 广州白云

9C7420：中英文权威来源关键运行冲突：广州白云_core_record_37：['procedure_or_waypoint_conflict']；中文页990；英文页1582

- fact ID：`广州白云_core_record_37`
- source record：`广州白云:core:c9f2ac8896ce0bac`
- category / phase：core / navigation
- 来源栏目：广州/白云机场运行特点 / 广州/白云机场运行特点／核心威胁与运行特点
- 中文页：990；英文页：1582

中文选中原文：

> 将W19航线MASGU-MABAG-OGABI-NOMAR 航段调整为MASGU-UPMIP-ATKAV-OLPAB-NOMAR供华东方向落地广州航班及飞跃 珠三角航班使用。

用于核查关键冲突的英文原文：

> The W19 route segment MASGU-MABAG-OGABI- NOMAR will be adjusted to MASGU-UPMIP-ATKAV- OBLAP-NOMAR for flights landing in Guangzhou and those flying over the Pearl River Delta region bound for East China.

#### 8. 9C7420 / 曼谷素旺那普

9C7420英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:730e7517374f441e；源页1171

- fact ID：`曼谷素旺那普:en:730e7517374f441e`
- source record：`曼谷素旺那普:en:730e7517374f441e`
- category / phase：core / departure
- 来源栏目：Suvarnabhumi / VTBS / English / core / departure
- 中文页：不要求逐条对应；英文页：1171

英文独立来源原文：

> Automatic wave separation from the ground 119.25.

### 2026-10-28

#### 1. 9C7419 / 广州白云

9C7419：中英文权威来源关键运行冲突：广州白云_core_record_22：['procedure_or_waypoint_conflict', 'runway_requirement_conflict']；中文页987；英文页1581

- fact ID：`广州白云_core_record_22`
- source record：`广州白云:core:ecc6ab7e4fca5257`
- category / phase：core / ground
- 来源栏目：广州/白云机场运行特点 / 广州/白云机场运行特点／核心威胁与运行特点
- 中文页：987；英文页：1581

中文选中原文：

> 跑道运行规则：向北运行：RWYO1L主要用于进场；RWYO1R 主要用于离场；RWYO2L主要用于离场；RWYO2R 主要 用于进场；RWY03进、离场混合运行。向南运行：RWY19R 主要用于进场；RWY19L 主要用于离场；RWY20R 主要用于离场；RWY20L 主要用于进场；RWY21 进、离场混合运行。

用于核查关键冲突的英文原文：

> Typically, aircraft take off from 01R/19L or 02L/20R, and land from 01L/20R or 02L/20R.

#### 2. 9C7419 / 曼谷素旺那普

9C7419：中英文权威来源关键运行冲突：曼谷素旺那普_core_record_17：['system_activation_temporal_polarity']；中文页314；英文页1171

- fact ID：`曼谷素旺那普_core_record_17`
- source record：`曼谷素旺那普:core:6785143081757f96`
- category / phase：core / ground
- 来源栏目：曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) / 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点
- 中文页：314；英文页：1171

中文选中原文：

> 为防止可能的干扰，对离港飞机，直到收到进入或者对 正跑道指令才打开 TCAS；对于进港飞机，直到脱离跑道再关闭。

用于核查关键冲突的英文原文：

> To prevent potential interference, TCAS should remain activated for departing aircraft until receiving the go-to or go-around command, and deactivated for arriving aircraft until the aircraft has left the runway.

#### 3. 9C7419 / 广州白云

9C7419英文版：英文关键运行表达无法可靠确认：广州白云:en:86382f3678c87672；源页1582

- fact ID：`广州白云:en:86382f3678c87672`
- source record：`广州白云:en:86382f3678c87672`
- category / phase：core / departure
- 来源栏目：GUANGZHOU BAIYUN / ZGGG / English / core / departure
- 中文页：不要求逐条对应；英文页：1582

英文独立来源原文：

> The aircraft automatically disengages from the wave contact after leaving the ground and approaches, with the specific frequency provided by the air traffic control.

#### 4. 9C7419 / 曼谷素旺那普

9C7419英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:762728438175820a；源页1172

- fact ID：`曼谷素旺那普:en:762728438175820a`
- source record：`曼谷素旺那普:en:762728438175820a`
- category / phase：core / arrival
- 来源栏目：Suvarnabhumi / VTBS / English / core / arrival
- 中文页：不要求逐条对应；英文页：1172

英文独立来源原文：

> The new Z approach procedure has been designated as the primary procedure in the air chart, with corresponding database updates. Crews are advised to carefully review the Warning section in the relevant approach chart to prevent unauthorized five-way turns into the approach procedure without ATC clearance.

#### 5. 9C7419 / 曼谷素旺那普

9C7419英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:b6c12b97473d3ea3；源页1172-1173

- fact ID：`曼谷素旺那普:en:b6c12b97473d3ea3`
- source record：`曼谷素旺那普:en:b6c12b97473d3ea3`
- category / phase：core / arrival
- 来源栏目：Suvarnabhumi / VTBS / English / core / arrival
- 中文页：不要求逐条对应；英文页：1172-1173

英文独立来源原文：

> When executing a VTBS 20R RNP approach, note the following: After the ATKIN, the control may instruct to "maintain 5000ft, turn right HDG 165, intercept final course 20R, report established." Note that the control requires establishing the 20R RNP five sides first, not granting permission for the RNP approach. Pay attention tothe confirmation instructions toavoid mistakenly awaiting the APPR. Subsequently, the control may descend 3500ft, allowing the RNP 20R approach, which could cause excessive energy. The crew should prepare contingency plans to prevent instability. The "high intercept" procedure is not permitted during RNP approaches.

#### 6. 9C7290 / 曼谷素旺那普

9C7290：中英文权威来源关键运行冲突：曼谷素旺那普_core_record_23：['takeoff_roll']；中文页315；英文页1171

- fact ID：`曼谷素旺那普_core_record_23`
- source record：`曼谷素旺那普:core:098da864b419e70f`
- category / phase：core / departure
- 来源栏目：曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS) / 曼谷素万那普机场运行特点 BANGKOK(BKK/VTBS)／核心威胁与运行特点
- 中文页：315；英文页：1171

中文选中原文：

> 为减少跑道占用时间，飞行员应确保在收到起飞 许可后能立即开始起飞滑跑。

用于核查关键冲突的英文原文：

> To minimize runway time, pilots must ensure they can begin taxiing immediately upon receiving the takeoff clearance.

#### 7. 9C7290 / 上海浦东

9C7290：中英文权威来源关键运行冲突：上海浦东_core_record_5：['papi_runway_value_association']；中文页586；英文页1367

- fact ID：`上海浦东_core_record_5`
- source record：`上海浦东:core:b694bf006b9795c9`
- category / phase：core / unspecified
- 来源栏目：上海/浦东机场运行特点（ZSPD/PVG） / 上海/浦东机场运行特点（ZSPD/PVG）／核心威胁与运行特点
- 中文页：586；英文页：1367

中文选中原文：

> PAPI信息：16L：跑道左侧入口内 454 米，3°，MEHT 20.9m；34R：跑道左 侧入口内 455 米，3°，MEHT 21.5m；16R：跑道左侧入口内 452 米，3°，MEHT 21.9m；34L：跑道左侧入口内 452 米，3°，MEHT 22.4m；17L：跑 道左侧入口内 464 米，3°，MEHT 21.7m；35R：跑道左侧入口内 464 米，3°，MEHT 22.5m；17R：跑道左侧入口内 452 米，3°，MEHT 21.4m；35L：跑道左侧入口内 452 米，3°，MEHT 21.0m。

用于核查关键冲突的英文原文：

> PAPI Information: RWY 16L: 454 m inside runway threshold on left side, glidepath angle 3°, MEHT 20.9 m - RWY 34R: 455 m inside runway threshold on left side, glidepath angle 3°, MEHT 21.5 m - RWY 16R: 452 m inside runway threshold on left side, glidepath angle 3°, MEHT 21.9 m - RWY 34L: 452 m inside runway threshold on leftside, glidepath angle 3°, MEHT 22.4 m - RWY 17L: 464 m inside runway threshold on left side, glidepath angle 3°, MEHT 21.7 m - RWY 35R: 464 m inside runway threshold on left side, glidepath angle 3°, MEHT 22.5 m - RWY 17R: 35L: 452 m inside runway threshold on leftside, glidepath angle 3°, MEHT 21.4 m - RWY 35L: 452 m inside runway threshold on left side, glidepath angle 3°, MEHT 21.0 m

#### 8. 9C7290 / 曼谷素旺那普

9C7290英文版：英文关键运行表达无法可靠确认：曼谷素旺那普:en:730e7517374f441e；源页1171

- fact ID：`曼谷素旺那普:en:730e7517374f441e`
- source record：`曼谷素旺那普:en:730e7517374f441e`
- category / phase：core / departure
- 来源栏目：Suvarnabhumi / VTBS / English / core / departure
- 中文页：不要求逐条对应；英文页：1171

英文独立来源原文：

> Automatic wave separation from the ground 119.25.

## 可复查的实际样稿

- [2026-10-26 中英文全文、源记录和进离场样例](independent-language-20261026-audit.md)；[完整来源 JSON](independent-language-20261026-audit.json)。
- [2026-10-28 中英文全文、扩展机场和进离场样例](independent-language-20261028-audit.md)；[完整来源 JSON](independent-language-20261028-audit.json)。
- 旧报告仅作历史证据，不能继续把“缺逐条对应”算成本轮发布失败。

## 验证

- 定向 173 passed（独立语言、配对辅助、源投影、记录边界、整章取材、主语省略、适用性/英语质量）。
- 完整验证命令：`python -B -m pytest -o addopts= --tb=short -q -p no:cacheprovider`；最终完整测试数量和新 HEAD 的两项 CI 结果记录在 PR 最新验收段，不复用上一提交的结果。
- `git diff --check`：PASS。
- 新增合成测试证明中英文不同 ID/数量可各自通过；英文必要资料缺失或明确关键冲突仍整套回滚；连续 7605/7606 合并、不连续 7289/7420 分组且每组完整中英文。
- 未触发正式航前、日历、手册同步、认证或 OTP；未改 main、ICS、调度、用户资料和发布基础设施。

**继续 Draft，不合并、不上线。**
