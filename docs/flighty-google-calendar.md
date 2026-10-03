# Flighty Google Calendar 镜像

`sync_flighty_google_calendar.py` 只读取根目录已生成、清洗后的 `flight.ics`，不访问机组网站，不调用登录/OTP/Playwright，不写入 ICS、认证状态、GitHub 发布状态或航前准备文件。依赖沿用现有 `requests`、`tzdata` 和标准库，无需修改 requirements。

## 首次设置

1. 在自己的 Google Calendar 网页创建**二级日历** `Flighty航班`，时区设为 `Asia/Shanghai`（北京时间）。
2. 打开该日历「设置和共享 → 集成日历」，复制实际 **Calendar ID**（以 `@group.calendar.google.com` 结尾）。不要使用名称、`primary`、公开网址或秘密 iCal URL。程序通过 ID 访问并核对名称和时区，不自动创建/重命名日历。
3. 在 Google Cloud 启用 Google Calendar API，设置 OAuth consent screen 和 OAuth client。由拥有该日历的账户完成一次 offline 授权，取得 refresh token。所需 scopes：
   - `https://www.googleapis.com/auth/calendar.events.owned`
   - `https://www.googleapis.com/auth/calendar.calendars.readonly`
4. 在 GitHub 仓库 Settings → Secrets and variables → Actions → Repository secrets 配置以下四项。

| Secret | 内容 |
| --- | --- |
| `FLIGHTY_GOOGLE_CALENDAR_ID` | 二级日历的实际 ID |
| `GOOGLE_CALENDAR_CLIENT_ID` | 自己的 OAuth client ID |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | 对应的 OAuth client secret |
| `GOOGLE_CALENDAR_REFRESH_TOKEN` | 该账户授权此 client 后取得的 refresh token |

可通过 [Google OAuth Playground](https://developers.google.com/oauthplayground/) 的 “Use your own OAuth credentials” 授权：按工具要求在 OAuth client 中登记 redirect URI，选择上述 scopes，启用 offline access，使用自己的 client 凭据及其对应 refresh token。不要把凭据放进代码、issue、PR 或日志，不要用服务账号 JSON 代替用户 OAuth。

外部 OAuth 应用处于 Testing 状态时，涉及 Calendar scopes 的 refresh token 通常在 7 天后到期。长期运行前按 Google 控制台要求配置发布状态；token 到期或撤销不影响 ICS。参见 [Google OAuth 文档](https://developers.google.com/identity/protocols/oauth2)。

本地运行可在进程环境中提供同名变量。生产 workflow 使用上述 GitHub Secrets，不读取仓库内凭据文件；无需 Base64 JSON 或新的 runner 安装步骤。

## 预览和启用

```text
python -B sync_flighty_google_calendar.py --dry-run
```

- 凭据完整：刷新 token、核验日历、读取所有已管理事件，输出 create/update/delete/skip 计划，不调用事件写接口。
- 凭据缺失：输出 `FLIGHTY_DRY_RUN=OFFLINE_EMPTY_TARGET`，离线预览候选数。创建数假设目标为空，update/delete 为 0，不表示已检查真实 Google 状态。
- 不带 `--dry-run` 且缺少任意配置：输出 `FLIGHTY_SYNC=SKIPPED_NOT_CONFIGURED`，exit 0，不读取或修改源文件。

配置 Secrets 并合并功能分支后，正常「更新机组日历」workflow 在原有步骤末尾同步镜像。必须满足 scraper 成功、`AUTHENTICATED`、clean 成功、publish 成功且状态为 `PUBLISHED` 或 `NO_CHANGES`。该步骤 `continue-on-error: true`，限时 5 分钟。失败输出 warning、返回非零，不回滚/重新发布 ICS，不覆盖 last-good，不改变航前准备检查顺序。

首次请检查一个未来航班：标题如 `Spring Airlines 9C6731 DLC → HET`，地点 `DLC`，描述含航空公司、完整航班号、出发/到达 IATA、英文地点和 `Crew`。起止时间来自 ICS，以 `+08:00` 与 `Asia/Shanghai` 提交。镜像无提醒，原 ICS 提醒不变。

手机系统日历账户中启用此 Google 日历，再在 Flighty 的日历导入设置中选取它。识别结果需在 Flighty 实机确认。航班号含 `X`/`Y` 等后缀时保留原值，不猜测替换成其他航班号。

## 持久化和同步行为

- stable key 为 `北京时间出发日期 | 完整航班号 | 出发 IATA | 到达 IATA` 的 SHA-256，不包含时分、源 UID、人员或版本时间。
- Google 自行分配 event ID。`extendedProperties.private` 保存 `flighty_owner`、`flighty_key`、`flighty_service`（日期和航班号）、`flighty_route`，与 ID 同属一条持久化事件。每次运行分页读取，重建 `event_id ↔ stable key` 索引，不依赖本地文件、Actions cache 或 Git 提交。
- 相同 key 的时间变化更新原 ID。同日期同航班号只有一个新旧候选时，航线变化也更新原 ID 和 key。多段航班分别建事件，不按返回顺序猜匹配。
- 航班号改变先创建正确镜像，再删除旧镜像。跨午夜改时刻时，若同航班号同航线的新旧候选唯一且相差不超过 24 小时，也更新原 ID。更大日期移动或多候选情况按新增/移除处理，不猜测配对。
- 从有效源文件消失、`STATUS:CANCELLED` 或改为非航班：删除本模块拥有的旧镜像。合法空 VCALENDAR 会清除全部本模块镜像。
- 只处理带本模块 owner 标记的事件，不删除手工事件；已管理镜像的手工字段改动会在下次同步恢复。
- 完成所有新增/更新后才删除过期镜像。API 失败立即停止后续写入，不盲目重试 POST。插入响应丢失时，下一次仍可用 Google 上原子保存的 key 找回事件；重复镜像在成功同步时合并。
- 缺失、截断、非法时间/时区的源文件直接报错，不执行远端删除。机场不明确或同 key 有冲突时刻时 warning/skip，保留该服务已有镜像，等待数据明确后修复。
- 同步范围为当前文件全部有效航班，包括其保留的历史事件，没有额外时间窗口。

工作流沿用现有 `crew-calendar` concurrency group 串行执行。手工同步应等待 workflow 结束，避免并发写入。

依据 [Google 私有扩展属性](https://developers.google.com/workspace/calendar/api/guides/extended-properties) 和 [Events resource](https://developers.google.com/workspace/calendar/api/v3/reference/events)，业务 key 不作为 Google 自定义 ID。

## 机场转换与跳过

中文名→ICAO 读取现有 `crew_calendar_main.py` 静态映射、可选 `airports.csv` 和 `airport_aliases.json`；不会导入/执行 scraper。仅精确匹配，冲突别名不选择其中之一。`(+1)` 仅从机场文字移除，时间始终来自 DTSTART/DTEND。

`config/airport_iata.json` 仅补充现有 ICAO 的 IATA/英文地点，不复制中文机场数据库。来自 [OurAirports 公共领域数据](https://ourairports.com/data/)，保存来源、检查日期、原数据 SHA-256，只收录唯一、非关闭机场的精确 ICAO 对照。运行时不联网自动改映射。

本次有 135 个对照。既有 `ZSYZ`、`ZUTC` 未获得可靠对应，不改原映射，涉及航班跳过。缺少中文→ICAO 的安顺黄果树、广元盘龙、张掖甘州、恩施许家坪，以及不能确定具体机场的“大阪”也跳过。扩展覆盖时应先核实并维护仓库既有中文→ICAO 来源，再补充有来源的 IATA 对照。

基线 `799ebbaa0e465409a1a168aa98c345085e46de63` 离线预览：206 条源事件，161 个候选镜像、45 条跳过。其中包括 4 组存在冲突时刻的历史航班。计数随正常 ICS 发布变化。

## 停用

移除 `FLIGHTY_GOOGLE_CALENDAR_ID` Secret，后续 workflow 将安全跳过。需要撤销 OAuth 时，在 Google 账户中撤销应用授权。停用不自动删除现有镜像；彻底清除可在 Google Calendar 删除专用 `Flighty航班` 二级日历。
