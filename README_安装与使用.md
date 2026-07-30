# Crew Calendar 双 Agent 安装与使用

本包新增两个相互独立的 Agent，并且**不修改现有 `schedule.yml`、`crew_calendar_main.py`、`clean_ics_people.py`、ICS 订阅链接或现有定时抓取流程**。

## 一、包含内容

### 1. Crew Calendar 维护 Agent

入口：`Actions → Crew Calendar Maintenance Agent → Run workflow`

作用：
- 可选先运行一次当前爬虫，生成最新 `debug_output` 和运行日志；
- 自动检查 Actions 失败、漏航段、人员/签到/注册号串段、置位误分类、历史任务丢失和 Apple ICS 格式；
- 只在临时候选目录修改副本；
- 语法和回归检查全部通过后，才在 Artifact 中输出完整候选文件；
- **不会自动覆盖或提交正式主程序和清洗脚本**。

安全状态：
- `SUCCESS`：候选完整文件已生成；
- `NO_CHANGE`：未发现需要修改的问题；
- `FAILED_SAFE`：API、额度、工具或测试失败，正式文件完全不变。

### 2. 航前准备 Agent

入口：`Actions → Generate Flight Preparation`

自动时间（北京时间）：
- D-2 18:17：初稿；
- D-1 00:37：刷新；
- D-1 09:07：最终稿。

GitHub Actions cron 使用 UTC，工作流内已经换算为：`10:17 / 16:37 / 01:07 UTC`。

成功后可在三个位置查看：
1. Actions 本次运行的 Summary；
2. Artifact：`flight-preparation-运行编号`；
3. 仓库中的：
   - `flight_preparation/latest.txt`
   - `flight_preparation/YYYY-MM-DD_航前准备.txt`

失败或没有任务时不会覆盖已有 `latest.txt`。

## 二、首次设置

### 1. 添加 API Key

进入仓库：

`Settings → Secrets and variables → Actions → New repository secret`

名称：

```text
OPENAI_API_KEY
```

值：你的 OpenAI API Key。

ChatGPT Plus 与 API 分开计费。建议在 OpenAI API 项目里设置月度预算和用量提醒。

### 2. 检查个人资料

编辑：

```text
config/pilot_profile.json
```

以下字段只由你手动更新，Agent 不会根据排班猜测：
- 经历时间；
- 起落数；
- 近90天/近一月起落；
- 最近操纵落地机场和日期；
- PF/PM 讲评；
- 值勤第几天。

### 3. 添加完整机场特点文件

把现有文件：

```text
AirDropManual-机场特点汇总(Airport Information)20260511-Manual.txt
```

上传到：

```text
knowledge/airport_information.txt
```

暂时不上传也能运行，但只会使用 `config/airport_supplements.json` 中已有的机场补充资料。

## 三、机场经历自动更新

`config/airport_experience.json` 会根据 `flight.ics` 中已经结束的航班更新机场最近运行日期，并自动判断是否在近90天内。

它不会自动更新：
- 操纵落地；
- 经历小时；
- 起落数。

如航班取消或实际未执行，请手动修正对应机场日期。

## 四、天气来源

Agent 通过 AviationWeather.gov 的 Data API 获取机场 METAR/TAF。获取失败或 TAF 未覆盖航班时段时，正文会明确写“以航前最新 TAF/METAR 及放行资料为准”，不会编造天气。

## 五、模型与费用

默认：
- 航前准备：`gpt-5-mini`
- 维护 Agent：`gpt-5.1`

手动运行时可以在 Actions 页面修改模型。维护 Agent 比航前准备更耗用量，因为它需要检查源码和调试文件。

## 六、现有流程保护

安装包不会覆盖：

```text
.github/workflows/schedule.yml
crew_calendar_main.py
clean_ics_people.py
airport_aliases.json
```

维护 Agent 也不会直接提交候选修复。你确认候选文件后，再自行改回正式文件名覆盖。

## 七、Windows self-hosted runner

正式的 `Update Crew Calendar` 只在专用 Windows runner 上运行，浏览器
profile 保存在仓库外的：

```text
C:\crew-calendar-data\browser-profile
```

最简安装步骤：

1. 在 GitHub 仓库进入 `Settings → Actions → Runners → New self-hosted runner`，
   生成一次性注册 Token。
2. 在准备用作 runner 的 Windows 电脑上，以管理员身份打开 PowerShell。
3. 在仓库目录执行：

```powershell
.\scripts\setup_self_hosted_runner.ps1 `
  -RepositoryUrl "https://github.com/leochai0202/crew-calendar"
```

脚本会隐藏提示输入一次性 Token，安装依赖、注册
`self-hosted, Windows, X64, crew-calendar` runner，并启动服务。

runner 注册完成后只做两次验收：

1. 第一次允许动态密码登录并写入持久 profile；
2. 第二次必须直接复用会话，不连接 QQ IMAP、不再申请验证码。

两次都成功后，才把分支合并到 `main` 并启用正式定时。
