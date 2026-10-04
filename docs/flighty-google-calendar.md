# Flighty Google Calendar 镜像

`sync_flighty_google_calendar.py` 只读取根目录已生成、清洗后的日历文件：未来航空航段以 `crew_schedule.ics` 为唯一权威来源，历史普通航班沿用 `flight.ics`，不访问机组网站，不调用登录/OTP/Playwright，不写入 ICS、认证状态、GitHub 发布状态或航前准备文件。认证使用 `google-auth` 的 Service Account credentials，日历读写沿用现有 REST API；其他依赖仍为 `requests`、`tzdata` 和标准库。

## 首次设置

1. 在自己的 Google Calendar 网页创建**二级日历** `Flighty航班`，时区设为 `Asia/Shanghai`（北京时间）。
2. 打开该日历「设置和共享 → 集成日历」，复制实际 **Calendar ID**（以 `@group.calendar.google.com` 结尾）。不要使用名称、`primary`、公开网址或秘密 iCal URL。程序通过 ID 访问并核对名称和时区，不自动创建/重命名日历。
3. 在 Google Cloud 启用 Google Calendar API，创建服务账号并生成 JSON 密钥。此部署的服务账号为 `crew-calendar-flighty@crew-calendar-flighty.iam.gserviceaccount.com`。
4. 在 `Flighty航班` 的共享设置中添加该服务账号邮箱，权限选择「做出更改并查看所有活动详情」。日历仍归个人用户所有，只授权服务账号访问，无需模拟个人用户或设置全域委派。程序使用的 scopes 为：
   - `https://www.googleapis.com/auth/calendar.events`
   - `https://www.googleapis.com/auth/calendar.calendars.readonly`
5. 在 GitHub 仓库 Settings → Secrets and variables → Actions → Repository secrets 配置以下两项。

| Secret | 内容 |
| --- | --- |
| `FLIGHTY_GOOGLE_CALENDAR_ID` | 二级日历的实际 ID |
| `FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON` | 下载的完整 Service Account JSON 原文，包含 `private_key`、`client_email` 等字段；不是路径或 Base64 |

共享日历不是服务账号拥有的日历，因此事件 scope 必须为 `calendar.events`，不能改为仅限拥有者的 scope。JSON 从环境变量读入内存，经 `json.loads` 解析，交给 `service_account.Credentials.from_service_account_info`，再使用 `google.auth.transport.requests.Request` 刷新 access token。原 REST 客户端随后使用 `Authorization: Bearer ...`。参见 [google-auth Service Account 文档](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html)。

不要把 JSON、私钥或 token 放进仓库、issue、PR 或日志。解析失败、密钥无效和刷新失败只记录不含敏感内容的错误，退出非零；不会写凭据临时文件或修改 ICS。此实现不读取原有的个人 OAuth Secrets。

本地运行可在进程环境中提供同名变量。生产 workflow 只注入上述两个 Secrets，不读取仓库内凭据文件。`requirements.txt` 已增加 `google-auth`；self-hosted runner 使用的 Python 环境需安装该依赖（`python -m pip install google-auth`），或按现有方式安装 requirements。依赖只在实际认证时导入，未配置时仍安全跳过。

## 预览和启用

```text
python -B sync_flighty_google_calendar.py --dry-run
```

- 凭据完整：使用服务账号刷新 access token、核验日历、读取所有已管理事件，输出 create/update/delete/skip 计划，不调用事件写接口。
- 凭据缺失：输出 `FLIGHTY_DRY_RUN=OFFLINE_EMPTY_TARGET`，离线预览候选数。创建数假设目标为空，update/delete 为 0，不表示已检查真实 Google 状态。
- 不带 `--dry-run` 且缺少任意配置：输出 `FLIGHTY_SYNC=SKIPPED_NOT_CONFIGURED`，exit 0，不读取或修改源文件。

配置 Secrets 并合并功能分支后，正常「更新机组日历」workflow 在原有步骤末尾同步镜像。必须满足 scraper 成功、`AUTHENTICATED`、clean 成功、publish 成功且状态为 `PUBLISHED` 或 `NO_CHANGES`。该步骤 `continue-on-error: true`，限时 5 分钟。失败输出 warning、返回非零，不回滚/重新发布 ICS，不覆盖 last-good，不改变航前准备检查顺序。

首次请检查一个未来航班：标题如 `Spring Airlines 9C6731 DLC → HET`，地点 `DLC`，描述含航空公司、完整航班号、`From` / `To`、`Departure Airport` / `Arrival Airport`、英文地点和 `Crew`。起止时间来自 ICS，以 `+08:00` 与 `Asia/Shanghai` 提交。镜像无提醒，原 ICS 提醒不变。

手机系统日历账户中启用此 Google 日历，再在 Flighty 的日历导入设置中选取它。识别结果需在 Flighty 实机确认。航班号含 `X`/`Y` 等后缀时保留原值，不猜测替换成其他航班号。

## 持久化和同步行为

- stable key 为 `北京时间出发日期 | 完整航班号 | 出发 IATA | 到达 IATA` 的 SHA-256，不包含时分、源 UID、人员或版本时间。
- Google 自行分配 event ID。`extendedProperties.private` 保存 `flighty_owner`、`flighty_key`、`flighty_service`（日期和航班号）、`flighty_route`，未来事件另存 `flighty_source_key`，与 ID 同属一条持久化事件。每次运行分页读取，重建 `event_id ↔ stable key` 索引，不依赖本地文件、Actions cache 或 Git 提交。
- 相同 key 的时间变化更新原 ID。同日期同航班号只有一个新旧候选时，航线变化也更新原 ID 和 key。多段航班分别建事件，不按返回顺序猜匹配。
- 航班号改变先创建正确镜像，再删除旧镜像。跨午夜改时刻时，若同航班号同航线的新旧候选唯一且相差不超过 24 小时，也更新原 ID。更大日期移动或多候选情况按新增/移除处理，不猜测配对。
- 未来航段从 `crew_schedule.ics` 消失或标为 `STATUS:CANCELLED`：删除本模块拥有的对应未来镜像；仅类型变化不删除。合法空未来源只清除未来镜像，已经过去的镜像保留。
- 只处理带本模块 owner 标记的事件，不删除手工事件；已管理镜像的手工字段改动会在下次同步恢复。
- 完成所有新增/更新后才删除过期镜像。API 失败立即停止后续写入，不盲目重试 POST。插入响应丢失时，下一次仍可用 Google 上原子保存的 key 找回事件；重复镜像在成功同步时合并。
- 缺失、截断、非法时间/时区的源文件直接报错，不执行远端删除。历史航班机场不明确或同 key 有冲突时刻时 warning/skip，保留该服务已有历史镜像，等待数据明确后修复；未来航班按下述 Future Strict 规则处理，不受历史保护逻辑阻挡。
- 过去的普通航班继续按 `flight.ics` 的既有规则维护，不从统一日程批量补入历史置位。已镜像但不在历史候选中的过去事件保留；由统一日程导入的置位在起飞后也保留，不会因从未进入 `flight.ics` 而被删除，后续同号重复航段不能挪用它的 ID。

工作流沿用现有 `crew-calendar` concurrency group 串行执行。手工同步应等待 workflow 结束，避免并发写入。

依据 [Google 私有扩展属性](https://developers.google.com/workspace/calendar/api/guides/extended-properties) 和 [Events resource](https://developers.google.com/workspace/calendar/api/v3/reference/events)，业务 key 不作为 Google 自定义 ID。

## 机场转换与跳过

中文名→ICAO 读取现有 `crew_calendar_main.py` 静态映射、可选 `airports.csv` 和 `airport_aliases.json`；不会导入/执行 scraper。仅精确匹配，冲突别名不选择其中之一。`(+1)` 仅从机场文字移除，时间始终来自 DTSTART/DTEND。

`config/airport_iata.json` 仅补充现有 ICAO 的 IATA/英文地点，不复制中文机场数据库。来自 [OurAirports 公共领域数据](https://ourairports.com/data/)，保存来源、检查日期、原数据 SHA-256，只收录唯一、非关闭机场的精确 ICAO 对照。运行时不联网自动改映射。

本次有 135 个对照。既有 `ZSYZ`、`ZUTC` 未获得可靠对应，不改原映射，历史涉及航班跳过，未来使用该唯一 ICAO。缺少中文→ICAO 的安顺黄果树、广元盘龙、张掖甘州、恩施许家坪，以及不能确定具体机场的“大阪”，历史仍跳过，未来保留原始机场名。扩展覆盖时应先核实并维护仓库既有中文→ICAO 来源，再补充有来源的 IATA 对照。

基线 `799ebbaa0e465409a1a168aa98c345085e46de63` 离线预览：206 条源事件，161 个候选镜像、45 条跳过。其中包括 4 组存在冲突时刻的历史航班。计数随正常 ICS 发布变化。

## Future Strict（默认启用）

每次读取源文件时固定一次北京时间 `as_of`，`DTSTART >= as_of` 为当前/未来航段。未来只使用 `crew_schedule.ics`；`flight.ics` 只贡献已过去的普通航班，绝不读取或自行合并 `positioning.ics`。两个源文件都必须完整，统一日程缺失或损坏时明确失败，不回退到分类日历后误报未来完整。

未来候选只要求 DESCRIPTION 中有唯一可靠的 `航班：<flight number>`、唯一可解析的 `航线：<origin> → <destination>`，且 DTSTART/DTEND 有效。不要求 `类型：航班`，也不以标题里的“置位 / positioning”等字样过滤；类型为置位、其他、训练、摆渡或类型缺失，只要满足上述条件都导入。DESCRIPTION 是身份来源，不要求标题重复航班号。已明确取消的记录仍不导入。

只有路线而无可靠航班号的火车/车辆摆渡不会被伪造成航空航段：输出 `FLIGHTY_ROUTE_NO_FLIGHT_NUMBER`，不加入 future source/missing；也不从标题推测航班号。缺失、空值、多个或无法解析的航班号都不可靠。有可靠航班号但没有航线时输出 `FLIGHTY_FLIGHT_NO_ROUTE`；航线字段存在但内容歧义、候选时间无效等情况明确失败。

航班号接受唯一的航空公司代码（两位 IATA 字母/数字或三字 ICAO）加 1–4 位非全零航班数字及可选字母后缀，保留完整值。9C 继续写 `Spring Airlines`；其他航空公司只使用源航班号中的明确代码作为 Airline，不猜公司全名或把其他航班标成春秋。

同步结束仍用同一个边界核对，避免运行过程中跨过起飞时刻而漏验。历史事件不因新类型规则批量补入置位；历史事件格式不追溯升级。

未来每个真实航段必须生成事件。出发与到达分别使用可靠 IATA；没有 IATA 时使用现有数据库中唯一的 ICAO；仍不明确时直接使用 `flight.ics` 的原始机场名，不模糊匹配、不猜代码、不额外创建机场数据库。ICAO/原名回退输出 `FLIGHTY_FUTURE_AIRPORT_FALLBACK` warning，不算丢弃。没有可解析的源航线、非法时刻或航班号则明确失败，不把无法计数的源记录静默排除后报告成功。

未来事件示例（无提醒，时刻直接来自 DTSTART/DTEND）：

```text
Summary: Spring Airlines 9C8935 PVG → CGQ
Location: PVG
Description:
Airline: Spring Airlines
Flight: 9C8935
From: PVG
To: CGQ
Departure Airport: PVG
Arrival Airport: CGQ
Route: Shanghai (Pudong) → Changchun
Crew
```

任务类型和标题均不进入身份。航班与置位互相变更，只要完整航班号、时刻和原始航线不变，source key、事件内容和 Google ID 都不变。`flighty_source_key` 为 JSON 数组 `[完整航班号, 北京时间 DTSTART, 北京时间 DTEND, 原始出发机场, 原始到达机场]` 的 SHA-256（UTF-8、无额外分隔空格）。包含 DTEND，因此同一起飞时刻但落地时刻不同也各自可追踪；不包含 IATA/ICAO 结果，因此机场映射改善不会改变源身份。完全相同的源记录去重为同一航段，不按 UID 或文件顺序分配身份。

同一业务 key 的未来源记录若时刻冲突，输出 `FLIGHTY_FUTURE_SOURCE_CONFLICT`，每条不同源身份都建立事件，不选择“正确”的一条。冲突组的 `flighty_key` 进一步结合源 key 区分。先匹配 `flighty_source_key`，再匹配原业务 key 和现有唯一候选规则，旧版未来事件可原位更新；映射完善、冲突出现/解除时尽量保留已明确对应的 Google ID。未来事件不会因同服务历史记录的保护状态而遗留重复镜像。

新增输出：

```text
FLIGHTY_FUTURE_SOURCE count=6 as_of=2026-10-04T00:00:00+08:00
FLIGHTY_FUTURE_SEGMENTS source=6 positioning=1 route_without_flight_number=1
FLIGHTY_FUTURE_FALLBACK iata=6 icao=0 raw=0
FLIGHTY_FUTURE_CHECK source=6 google=6 missing=0
FLIGHTY_FUTURE_DUPLICATES count=0
FLIGHTY_SYNC=SUCCESS
```

数字只是示例，按最新统一日程和运行时刻计算。`source` 包含置位等所有合格未来航空航段；`positioning` 只作为置位计数，不参与筛选或身份；`route_without_flight_number` 是未来有路线但无可靠航班号的记录数，不计入 source 或 missing。机场计数以**未来航段**为单位、三类互斥：两端均为 IATA 记 iata；至少一端 ICAO 且没有原名记 icao；任一端为原名记 raw。`--dry-run` 输出源数量、机场回退数量和同步计划，绝不输出代表写入成功的 Future Check；离线预览不能代替实机验收。

实际 `apply_plan` 成功后，再次分页 `list_owned()`，逐条以 `flighty_source_key` 核对同 owner、未取消且有 Google ID 的事件。`google` 为匹配这些未来身份的远端事件总数。缺失时输出 `FLIGHTY_FUTURE_GAP missing=N` 及每条 `MISSING=日期|航班号|原始出发→原始到达|DTSTART|DTEND`，返回非零；重复身份也返回非零。只有完整性检查通过后才输出 `FLIGHTY_SYNC=SUCCESS`。Google 列表读取失败同样不报告成功，不打印响应正文、credential 或 token。

失败不会回滚 Google 已完成的写入，也不会改写 ICS 或认证状态；下次同步通过持久化身份恢复。workflow 原有 `continue-on-error: true`、认证/clean/publish 门控及发布隔离保持不变。

仅需运行专项回归：

```text
python -B -m pytest tests/test_flighty_google_calendar.py tests/test_workflow_auth_safety.py
```

## 停用

移除 `FLIGHTY_GOOGLE_CALENDAR_ID` 或 `FLIGHTY_GOOGLE_SERVICE_ACCOUNT_JSON` Secret，后续 workflow 将安全跳过。需要撤销访问时，取消日历对服务账号的共享，并在 Google Cloud 删除对应的服务账号密钥。停用不自动删除现有镜像；彻底清除可在 Google Calendar 删除专用 `Flighty航班` 二级日历。
