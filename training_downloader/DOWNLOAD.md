# 单份 PDF 下载与私人交付

现有独立手动工作流仍只接受一次登录，复用原 CP 邮箱认证、企业 SSO 和目标学习任务定位。不会因发布代码自动运行。本次只下载已指定的模拟机复训 PDF。

## 下载与限制

点击实际目标文件名后，等待页面或其阅读器框架出现唯一、可见且可用的下载/保存/导出 PDF 控件，点击一次。接收正常 Playwright download 事件；如果正常保存操作返回内联完整 PDF，则接收该次页面导航响应。网站直接通过点击课件触发的正常下载也可接收。

不读取 PDF.js 缓存，不调用 getData/打印，不枚举隐藏地址，不猜下载 API，不重建 Range 分片，不复制 Cookie/Token，不绕过禁用按钮、DRM 或明确下载限制。没有可识别的正常保存方式时停止。

文件必须存在，包含 `%PDF-` 文件头及完整 EOF，以严格模式解析成功、无加密限制、准确 29 页，并能由独立渲染器逐页渲染。网页 PDF.js 页数不参与下载准入判断。

## 私人交付

公开仓库中**只上传加密包**。每次使用新的 AES-256-GCM 密钥加密原始 PDF，以本机收件人的 RSA-4096 公钥通过 OAEP-SHA256 包装密钥。加密文件写入后回读验证；随后删除临时明文。独立工作流只上传该次输出的准确 `.enc` 文件，保存 7 天，不上传 Profile、日志、trace、私钥或未加密 PDF。

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

- `PDF_DOWNLOADED_ENCRYPTED`：已下载、校验并加密；尚不代表用户已经取得文件，`delivery_completed` 保持 false。
- Actions 的 `ENCRYPTED_ARTIFACT_AVAILABLE; LOCAL_DECRYPTION_REQUIRED`：加密包上传成功，还需本机解密。
- `SITE_DOWNLOAD_PROHIBITED` / `SITE_DOWNLOAD_DISABLED`：页面明确限制或禁用下载，停止。
- `DOWNLOAD_CONTROL_NOT_FOUND` / `DOWNLOAD_CONTROL_AMBIGUOUS`：未识别到唯一正常下载入口，不能据此断言网站禁止下载。
- `DOWNLOAD_ACTION_NO_FILE`：已点击正常下载控件，但未取得下载文件或完整 PDF 保存响应。
- `NOT_A_PDF` / `PDF_TRUNCATED` / `PDF_PAGE_COUNT_MISMATCH` / `PDF_ENCRYPTION_OR_DRM_UNSUPPORTED` / `PDF_PARSE_OR_RENDER_FAILED`：文件校验失败，不上传。
- `DOWNLOAD_DELIVERY_ENVIRONMENT_NOT_READY`：依赖或公钥不可用，在登录和验证码申请前停止。

原始异常、请求地址、响应头正文和认证信息不写入报告。上传失败也不算交付成功；当前运行的隔离目录仍由原安全清理脚本处理。没有自动重试登录或再次申请验证码的逻辑。
