# 一点知识独立登录检查

这是手动登录/课程访问测试，不是下载器。创建和发布工作流不代表已执行或已验证登录。

## 执行方式

等待用户另行确认执行后，在 GitHub Actions 选择 **一点知识独立登录检查** → **Run workflow** → `main`，勾选“确认仅执行一次独立登录，最多申请一次邮箱验证码”。

工作流只有 `workflow_dispatch`，没有定时、push、PR 或其他自动触发。输入默认不勾选；仅允许本仓库 `main` 的首次手动运行。GitHub 的 Re-run 会在注入登录 Secrets 前停止；如需再次测试，必须重新手动发起。不要重复点击运行。

## 文件范围

- `.github/workflows/training-login-check.yml`：手动入口、隔离源码获取、离线检查、并发检查、一次登录、临时目录清理。
- `training_downloader/login_probe.py`：复用原密码/邮箱认证，保持同一 context 访问课程和目标 PDF 阅读器。
- `training_downloader/workflow_guard.py`：只读检查 GitHub 活动任务和生产互斥配置。
- `training_downloader/cleanup_training.ps1`：严格验证独立运行目录后清理；`test_cleanup_training.ps1` 只使用合成目录测试。
- 两个 `test_*.py`：离线安全检查，包括直接调用经审阅原函数的模拟测试；不启动浏览器或连接邮箱。
- `.gitignore`：排除本地测试运行目录及字节码。

不修改生产 Python、`schedule.yml` 或其他工作流；不调用生产日历入口、发布、通知或认证恢复流程。

## 认证复用与次数限制

已只读核对 GitHub `main` 的 `crew_calendar_email_entry.py`、`password_email_auth.py`、`springair_email_otp.py`、`authenticate_crew_session.py`、`crew_auth_session.py`、`crew_calendar_main.py`、`imap_otp.py` 及 `schedule.yml`。

测试直接调用 `attempt_password_email_login(page)`，由其调用原账号界面切换和 `SpringAirEmailOtpReader`。不调用生产入口，因为生产入口会在邮箱失败后转手机认证并管理生产 Profile/备份。

原邮箱函数有两轮申请上限；测试只包装 reader 的 `connect()`，第二轮在申请按钮点击前立即抛出固定错误。邮件读取及验证码提取算法完全复用原实现。原函数、常量和源码均不修改。五个认证依赖固定 Git blob ID；版本改变就停止，需重新只读审阅。

四项既有 Secrets `CREW_USERNAME`、`CREW_PASSWORD`、`IMAP_EMAIL`、`IMAP_AUTH_CODE` 仅注入最后的登录步骤。另用短期 `github.token` 做只读源码/任务元数据查询；仓库权限只有 `contents: read`、`actions: read`。不读取 Secret API，不加载 `.env` 或生产状态。

## 并发与隔离

1. 已确认生产日历及机场手册同步工作流使用 `crew-calendar` 并发组。新工作流复用此互斥组，`cancel-in-progress: false`、`queue: max`，防止同时执行，也避免本测试入队时替换已排队生产任务。生产工作流自身原有队列策略不变。
2. 在登录步骤前及邮箱认证调用前各检查一次 GitHub 活动任务。只允许当前运行；其他任务处于运行、排队或等待状态时停止。API 不可用、分页不完整、生产工作流版本变化都停止。共享互斥组覆盖检查后新日历任务到来的竞争窗口。
3. 用现有 `[self-hosted, Windows, X64, crew-calendar]` runner。整个测试上限 12 分钟，登录步骤上限 6 分钟；不会取消正在执行的生产任务。后来到达的生产任务可能短暂排队，因此仍应选择空闲时段。
4. 不执行 checkout 或生产 bootstrap。仅从触发提交的不可变 `GITHUB_SHA` 获取明确列出的 Python 测试/依赖文件与本工作流，放在 `RUNNER_TEMP/training-login-<run_id>-<随机ID>/source`。不切换或清理生产仓库。
5. 每次浏览器 Profile 位于该副本的 `training_downloader/.runtime/<随机ID>/edge-profile`；浏览器 TEMP/TMP 也指向本次临时目录。只写独立的 `auth-status.json`（固定状态及布尔值），不导出 storage_state、Cookie 或 Session。不会读取、挂载或覆盖生产 Profile、备份、auth-control 或缓存。
6. `always()` 清理只允许当前 run_id 对应、直接位于 RUNNER_TEMP 下且带本次所有权标记的目录；根目录、祖先或子项有重解析点时拒绝操作。逐层检查，不跟随目录联接。仅文件占用/访问拒绝可进行最多三次清理尝试，每次重新检查全部边界，不结束浏览器进程、不修改权限。标记最后删除，避免失败重试失去归属证据。机器断电、runner 强制终止仍可能留下测试状态，需要本机人工核查；不要上传残留 Profile。

[GitHub 并发规则](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)说明了共享互斥组及 `queue: max` 的行为。

## 只读访问及输出

CP 成功与一点知识成功分别判断。CP 通过后在同一 context 打开指定课程；出现登录要求时只走一次既定 CAS→一点知识服务跳转。若仍要求认证则停止，不申请第二个验证码，不绕过额外验证。

仅报告课程路由、目录标记、模块链接数量及精确目标文件名的可见性。只有目标名称在页面中唯一可见时才点击该条课件，读取已加载 PDF.js 的页数元数据；不抓取或导出 PDF 文件，不调用下载 API。浏览器下载保存被禁用，下载事件立即取消。非 PDF.js 阅读器、歧义链接或未就绪页面会报告未确认；不会把列表可见当成内容可访问。

通用标题/目录标记不能证明完整课程标题或完整模块列表，相关确认字段保留为未确认，待真实页面检查后再完善。这些限制不会被当作认证成功证据。29 页确认只针对本次点击后可识别的目标阅读器。

不打印凭据、Cookie、Token、验证码、logincache、完整 URL、异常堆栈或页面正文；原认证函数输出丢弃。没有截图、trace、HAR、完整 Network 日志或 artifact 上传步骤。

新会话仍可能触发服务端账号级限流或使其他会话失效；Profile 隔离不能消除此服务端风险。

## 本地离线检查

```powershell
python -B training_downloader/login_probe.py
python -B -m unittest discover -s training_downloader -p 'test_*.py'
pwsh -File training_downloader/test_cleanup_training.ps1
```

默认只做预检查；不会启动浏览器或申请验证码。当前本地 checkout 较旧且未注入四项环境变量，因此真实登录仍未执行。独立工作流按 GitHub 提交获取已审阅源码，不替换本地生产文件。

## 失败原因诊断

两次并发检查均保留：独立步骤输出 `TRAINING_CONCURRENCY_REASON` / `TRAINING_CONCURRENCY_CHECK`；登录前检查在脱敏 JSON 中输出 `concurrency_failure_reason` / `concurrency_check`。固定原因码区分其他活动任务、生产工作流变更、响应不完整、HTTP 401/403/429/5xx、超时、TLS、网络、JSON 错误及本地导入失败。所有未知异常仍停止，且只报固定代码，不打印异常文本、URL 或请求头。不重试认证，也不因为 API 故障放行。

清理输出固定 `TRAINING_TEMP_CLEANUP_REASON`、数字 `TRAINING_TEMP_CLEANUP_NATIVE_CODE` 和尝试次数。原始异常文本、文件内容及认证状态不写日志。缺少所有权标记的旧目录不自动删除。

Run `40501322255` / Job `122179435036`：第一次检查于 2026-10-27 12:08:06 UTC 通过，12:08:20 第二次检查停止，`login_attempted=false`。当天 Actions 时间线未显示与这段时间重叠的其他任务，但旧日志吞掉了异常，无法唯一还原第二次阻止或清理失败的具体底层原因。2026-10-28 只读检查确认日志中那个准确目录已经不存在，同 Run ID 下也没有残留目录；未删除任何实际测试或生产目录。新原因码用于下一次人工运行给出可核查结论，文件锁测试只能证明该场景已受控，不能证明它就是历史故障原因。
