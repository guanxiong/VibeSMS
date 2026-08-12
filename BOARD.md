# SMS Gateway MVP Board

## Active

| Task ID | Priority | Task | Assignee | Session ID | Status |
| --- | --- | --- | --- | --- | --- |
| MVP-001 | Critical | 实现单台双卡 Android 的短信与来电事件采集、上传、持久化和管理页面 | Codex | root-20260804-mvp1 | APPROVED |
| MVP-002 | High | 使用运营商真实短信和来电完成最终端到端验收 | User + Codex | root-20260804-mvp1 | APPROVED |
| MVP-003 | Medium | 补充断网恢复后的自动补发、主动设备心跳、设备独立密钥、管理端认证与 HTTPS 公网部署 | Codex | root-20260804-mvp3 | IN PROGRESS |
| MVP-004 | High | 将项目品牌化为 VibeSMS，实现无账户 Key 接入、Android Terminal 和 Agent Skill | Codex | root-20260808-mvp4 | READY FOR REVIEW |

## MVP-001 Acceptance Criteria

- Android 10 真机可安装并完成短信、电话、网络与通知权限配置。
- 收到短信后，将发送方、正文、接收时间、SIM 槽位和设备 ID 上传到自部署服务。
- 来电振铃、接通或结束事件可上传；无法可靠取得号码时允许标记为 unknown。
- 服务端持久化事件，重复上传不会生成重复记录。
- 浏览器可查看设备状态、短信和来电事件。
- 请求失败时 Android 端执行有限次数重试；断网恢复后的自动补发在 MVP-003 完成。

## MVP-003 Acceptance Criteria

- Android 每 15 分钟扫描并补发最近 24 小时内失败的短信/来电转发记录。
- Android 主动上报设备心跳，管理端可区分在线与离线设备。
- 每台设备使用独立上传密钥，密钥不能跨设备 ID 使用或从管理接口读回。
- 管理页面和查询/设备管理 API 必须经过管理员认证。
- 提供不直接暴露应用端口的 Caddy HTTPS 公网部署配置。
- 当前 Android 切换到非 USB 地址，移除 `adb reverse` 后仍可上传事件和心跳。

## MVP-004 Acceptance Criteria

- 产品名称统一为 `VibeSMS`，云端入口保持 `sms.shareapi.ai`。
- 管理员可手工签发、轮换、禁用一个手机号对应的用户 Key。
- Android Terminal 通过用户 Key 首次绑定 SIM，换取仅具上传权限的设备凭据。
- Agent 使用用户 Key 隔离读取对应号码的短信与来电记录，并支持长轮询等待验证码。
- 提供可安装的 VibeSMS Skill，Key 仅从环境变量或 Secret 配置读取。
- Android APK 使用签名构建，并通过 GitHub Releases 提供校验值和下载。
- 不引入独立用户账户体系，预留 `owner_ref` 供后续与 `llm.shareapi.ai`、`panel.shareapi.ai` 统一身份。

## Review Notes

- 2026-08-04：首轮目标锁定为单机双卡、入站短信和来电事件；集群调度、远程发短信、MDM 和 HA 延后。
- 2026-08-04：SEA-AL10 已安装 SmsForwarder 3.5.0，短信/来电开关、双卡标识、Webhook 和全量规则配置完成。
- 2026-08-04：规则级模拟验收已覆盖短信 SIM1/SIM2 与来电 SIM1/SIM2，4 条事件均成功入库；等待运营商真实短信与真实来电做最终验收。
- 2026-08-04：Android 请求重试设置为最多 3 次、递增间隔从 1 秒开始、单次超时 10 秒；应用会保留失败日志，但断网恢复自动补发仍需后续实现。
- 2026-08-04：运营商真实来电产生来电过程与结束事件，发送方和设备标记完整；结束事件正确关联 SIM1。
- 2026-08-04：运营商真实短信已识别为 `sms`，正文、发送方、接收时间、设备标记、SIM1 和订阅 ID 均完整。
- 2026-08-04：质量门禁复核通过：5 项服务端自动化测试、Python 编译检查、前端 JavaScript 语法检查和 Git diff 检查均通过。当前环境未安装 `quality-gate-auditor` skill，使用上述可重复检查作为人工审核依据。
- 2026-08-04：MVP-003 服务端已实现设备独立 Token、管理员 Basic Auth、主动心跳、在线状态和安全响应头；7 项自动化测试通过。
- 2026-08-04：SEA-AL10 已切换到局域网 Webhook；移除 `adb reverse` 后事件通道连续测试成功，证明上传链路不依赖 USB。
- 2026-08-04：`Gateway Reliability` 已设置为每 15 分钟重发最近 24 小时的失败记录并发送心跳；无人操作时在 15:59:59 自动更新心跳，后台调度验收通过。
- 2026-08-04：Caddy/Compose HTTPS 配置已通过静态解析；实际公网证书签发仍等待用户提供域名、DNS 和公网 Linux 主机，因此 MVP-003 保持进行中。
- 2026-08-08：从 Obsidian Infra 实时审计四台候选服务器后选择 `us`：可用内存约 1.3GB、磁盘剩余 27GB，并复用 `shareapi.ai` 的 OpenResty 与 DNS 运维链。
- 2026-08-08：`sms.shareapi.ai` 已部署到 `us`，Namecheap A 记录指向 `5.253.38.114`，Let’s Encrypt DNS-01 证书签发成功；应用只绑定 `127.0.0.1:8787`。
- 2026-08-08：公网验收通过：健康检查 200、管理端未认证 401/认证 200、错误设备 Token 401/正确设备 Token 200，历史 12 条事件和 1 台设备迁移完整。
- 2026-08-08：当前手机未连接 USB 且不在本机局域网，待再次连接后把事件与心跳 Webhook 切换到 `https://sms.shareapi.ai`，MVP-003 暂保持进行中。
- 2026-08-08：用户确认手机端更新延后执行；公网部署状态和下次连接后的 6 步切换/验收清单已写入 `docs/REAL_DEVICE_ACCEPTANCE.md`，本轮不操作手机。
- 2026-08-08：产品正式命名为 `VibeSMS`，APK 决定通过 GitHub Releases 分发；无账户 Key 接入设计纳入 MVP-004。
- 2026-08-08：管理页、服务标识与产品文档已完成 VibeSMS 品牌化并部署到 `sms.shareapi.ai`，公网健康检查返回 `name=VibeSMS`；现有 API、Key、数据库和 Android 响应关键字保持兼容。
- 2026-08-08：当前仓库尚无 GitHub remote，本机也未安装 Android SDK/Gradle；在建立仓库和签名构建流水线前不发布占位 APK。
- 2026-08-08：公开仓库 `guanxiong/VibeSMS` 已创建，`main` 已推送并绑定 `origin`，仓库主页指向 `sms.shareapi.ai`；Release 保持为空，等待签名 Android APK 和校验值。
- 2026-08-08：公开项目主页与管理控制台完成分离：`/` 无需登录，`/admin/` 与管理 API 保持 Basic Auth；静态资源按 `site/`、`admin/` 分层，未完成的 Key Inbox API 均明确标注为 MVP-004 规划能力。
- 2026-08-08：成熟项目主页已部署到 `sms.shareapi.ai`；生产验收为首页/样式/分享图 200、管理台未认证 401/认证 200，容器健康且原有 1 台设备与 12 条事件完整保留。
- 2026-08-08：MVP-004 服务端纵向切片完成：用户 Key 签发/轮换/禁用/解绑、首次设备与 SIM 绑定、上传凭据交换、隔离 Inbox、状态游标、OTP 长轮询和 VibeSMS Skill；17 项自动化测试通过。
- 2026-08-08：VibeSMS 0.3.0 已部署生产，迁移前备份为 `gateway-20260808T042127Z.db`；生产验收确认 user_keys 表、Key 管理 UI、管理员/Agent 认证边界与 Agent API 正常，原 12 条事件和 1 台设备完整保留。
- 2026-08-08：VibeSMS Android Terminal 原生工程完成，覆盖双卡短信、来电状态、SQLite 离线队列、指数退避补发、15 分钟心跳、Android Keystore 设备凭据与 Key 首次绑定；Android CI 的 API 36 Release 编译及 lint 全部通过。
- 2026-08-08：签名 APK `VibeSMS-0.1.0.apk` 已发布至 GitHub Release `v0.1.0`，随附 `SHA256SUMS`；线上回下载 SHA-256 为 `13346cd206c68c96454622f5e9513b9b0c394ef595fc8e4677c4724975b96813`，APK Signature Scheme v3 与 4096-bit RSA 发布证书复核通过。发布私钥仅保存在维护者机器，未上传 GitHub。
- 2026-08-08：VibeSMS 0.4.0 已部署生产，部署前在线备份为 `gateway-20260808T083043Z.db`；公网健康检查、首页 APK 直链、管理端 401 边界和原 1 台设备/12 条事件均验收通过，首页不再包含“即将发布”。
- 2026-08-08：MVP-004 进入 READY FOR REVIEW；当前手机未连接，v0.1.0 APK 的真机安装、SIM 绑定和运营商短信/来电回归并入下次 MVP-003 手机切换验收。
- 2026-08-09：VibeSMS 0.8.0 已部署生产：首页申请 Key 改为原地弹框，自动名额与人工队列两条路径均完成桌面/移动端交互验收；Key 签发后直接提供 Skill 安装命令和不含 Key 的 Android 配置 Prompt。
- 2026-08-09：Android Terminal v0.2.0 与 VibeSMS Skill v1.1.0 已发布。Android CI 的 API 36 编译与 lint、服务端/Skill 27 项测试、签名证书与线上回下载 SHA-256 均通过；ADB 自动安装、显式双卡选择、权限授予、绑定和心跳验证已实现，等待当前手机重新连接后完成真机脱离 USB 验收。
- 2026-08-13：VibeSMS 0.9.0 已部署生产。首页、Key 申请、激活、收件箱和隐私页支持中英文切换、语言持久化及英文站内链接延续；1440px/390px 公网页面完成无中文残留和无横向滚动验收。部署前备份为 `gateway-20260812T185202Z.db`；同时修复旧版 `key_requests` 表在创建归因索引前未先补列的迁移顺序问题，30 项自动化测试通过，生产健康接口确认 2 台设备与 23 条事件保留完整。
