# 29 页截图 PDF 与私人交付

现有独立手动工作流仍只接受一次登录，复用原 CP 邮箱认证、企业 SSO 和目标学习任务定位。不会因发布代码自动运行。本次手动工作流采用 **29 张完整页面截图 → 图片型 PDF → 加密 Artifact**。所得文件是保留可见水印的图片型副本，不是网站原始 PDF。

## 截图与限制

人工触发前必须确认平台允许保存本课件并勾选 `confirm_platform_allows_capture`；默认 false，只有查看权限不能代替保存许可。缺少确认时工作流不会登录。页面明确禁止截图、复制或保存时仍停止，不规避截屏保护、DRM 或复制限制。

点击现有实际目标文件名后，寻找唯一的正常阅读页面（带 `data-page-number` 的 PDF.js/React PDF 页面容器），通过可见总页数或完整 1–29 页编号确认范围。使用阅读器正常页码输入、滚动及可见的“适合页面”缩放选项。不能识别页面结构时明确停止，不猜测内部 API。

按 1–29 顺序等待页面加载，检查页面、画布/图片及 iframe 边界，确认没有裁切或遮挡；连续三次截图稳定后保存整页元素截图。截图不含阅读器工具栏，不去除水印；拒绝低分辨率、空白、重复或缺失页。某页失败即报告 `failed_page` 和固定原因码，绝不补空白页。保守检测可能拒绝内容近似的页面或动态水印持续变化的页面；不会把这种情况宣称成功。

只使用正常浏览器截图，不读取 PDF.js 缓存、canvas 像素或隐藏 PDF 数据，不调用 getData/打印，不猜下载 API，不修改保护样式。截图仅写入当次隔离临时目录，按原始比例合成 29 页图片型 PDF，随后删除截图。任何截图清理失败都会阻止交付；原有安全清理流程仍会检查并处理当次隔离目录。

文件必须存在，包含 `%PDF-` 文件头及完整 EOF，以严格模式解析成功、准确 29 页，并能由独立渲染器逐页渲染。既有正常下载实现保留，但本工作流不再依赖下载按钮。

## 私人交付

公开仓库中**只上传加密包**。每次使用新的 AES-256-GCM 密钥加密合成 PDF，以本机收件人的 RSA-4096 公钥通过 OAEP-SHA256 包装密钥。加密文件写入后回读验证；随后删除临时明文。独立工作流只上传该次输出的准确 `.enc` 文件，保存 7 天，不上传截图、Profile、日志、trace、私钥或未加密 PDF。

收件公钥为 `training_downloader/recipient_public.pem`。配套私钥已在本机创建于 `training_downloader/.runtime/private-delivery/recipient-private.pem`，目录 ACL 仅允许当前 Windows 用户和 SYSTEM；私钥受 Git ignore 排除，未提交 GitHub。请在本机安全保管该私钥；丢失后无法解密已有交付包。不要把私钥贴到日志、聊天或仓库。

人工运行成功后，在该次 GitHub Actions 页的 Artifacts 下载 `training-pdf-encrypted-<Run ID>`，解压出 `training-pdf.enc`。在本机仓库目录执行以下命令（把输入和输出替换为实际本机路径）：

```powershell
$env:PYTHONPATH = Join-Path $PWD 'training_downloader/.runtime/download-deps'
python -B training_downloader/private_delivery.py --input 'C:\Users\chai\Downloads\training-pdf.enc' --output 'D:\GGITHUB\crew-calendar\training_downloader\.runtime\private-delivery\模拟机复训指导手册.pdf'
```

本次开发已将依赖安装到上述独立本机目录。如果该目录被清理，仅需重新安装到该独立目录：

```powershell
python -m pip install --target training_downloader/.runtime/download-deps -r training_downloader/download-requirements.txt
```

解密程序拒绝错误私钥、被篡改包和覆盖已有文件；解密后再次校验 29 页。只有输出 `PRIVATE_PDF_DELIVERY=COMPLETE PDF_PAGES=29` 且本机 PDF 已存在，才算完成文件交付。不要把解密后的文件提交到公开仓库。

## 状态说明

- `PDF_CAPTURED_ENCRYPTED`：完整 29 页截图已合成、逐页验证并加密，仍需上传成功和本机解密。
- `PAGE_CAPTURE_FAILED`：`failed_page` 指出失败页码；`capture_failure_reason` 区分未加载、裁切、空白或保护、重复、页码变化、结构不支持等。不会交付不完整 PDF。
- `CAPTURE_PERMISSION_NOT_CONFIRMED`：尚未确认平台允许截图保存，登录前停止。
- `PDF_DOWNLOADED_ENCRYPTED`：已下载、校验并加密；尚不代表用户已经取得文件，`delivery_completed` 保持 false。
- Actions 的 `ENCRYPTED_ARTIFACT_AVAILABLE; LOCAL_DECRYPTION_REQUIRED`：加密包上传成功，还需本机解密。
- `SITE_DOWNLOAD_PROHIBITED` / `SITE_DOWNLOAD_DISABLED`：页面明确限制或禁用下载，停止。
- `DOWNLOAD_CONTROL_NOT_FOUND` / `DOWNLOAD_CONTROL_AMBIGUOUS`：未识别到唯一正常下载入口，不能据此断言网站禁止下载。
- `DOWNLOAD_ACTION_NO_FILE`：已点击正常下载控件，但未取得下载文件或完整 PDF 保存响应。
- `NOT_A_PDF` / `PDF_TRUNCATED` / `PDF_PAGE_COUNT_MISMATCH` / `PDF_ENCRYPTION_OR_DRM_UNSUPPORTED` / `PDF_PARSE_OR_RENDER_FAILED`：文件校验失败，不上传。
- `DOWNLOAD_DELIVERY_ENVIRONMENT_NOT_READY`：依赖或公钥不可用，在登录和验证码申请前停止。

原始异常、请求地址、响应头正文和认证信息不写入报告。上传失败也不算交付成功；当前运行的隔离目录仍由原安全清理脚本处理。没有自动重试登录或再次申请验证码的逻辑。
