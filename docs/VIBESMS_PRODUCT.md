# VibeSMS 产品定义

## 定位

VibeSMS 是“用户自带 Android 手机与 SIM 的 Agent SMS Gateway”。用户无需注册独立平台账户；管理员在后台开放一定数量的自动签发名额，同一匿名领取设备首次提交邮箱、本人手机号和用途后立即获得 Key。每个设备只能使用一次自动额度；重复设备、额度用尽或关闭时进入人工队列，由管理员交付一次性激活码。Key 对应一个手机号，Android Terminal 负责上传，Agent Skill 负责隔离读取短信和来电。

VibeSMS 不提供公共共享号码池，不面向绕过第三方平台风控或账号限制的用途。

## 已确认决策

- 产品名称：`VibeSMS`
- 云端入口：`https://sms.shareapi.ai`
- 身份方式：无独立用户账户，Key 即当前访问边界
- 默认映射：一个用户 Key 对应一个手机号
- Android 接入：用户可在 APK 中手工输入 Key，也可让 Agent 通过已授权 ADB 自动安装和绑定；服务端换发仅具上传权限的设备凭据
- Agent 接入：用户 Key 只读取对应号码的短信、来电与验证码
- APK 分发：GitHub Releases，必须使用签名 APK 并发布 SHA-256 校验值
- 公开仓库：`https://github.com/guanxiong/VibeSMS`
- 未来统一身份：Key 记录预留 `owner_ref`，后续可关联 `llm.shareapi.ai` 或 `panel.shareapi.ai` 的用户主体

## 最小用户流程

1. 管理员在 `/admin/` 开启自动签发，并设置可公开领取的剩余名额。
2. 用户在首页弹框或 `/apply/` 提交邮箱、本人手机号、用途和预计终端数量；浏览器首次使用匿名领取标识且有额度时，立即获得仅显示一次的真实 Key。
3. 自动额度关闭或用尽时，申请进入人工队列；管理员可签发一次性激活码，并通过邮箱或微信交付，用户再到 `/activate/` 兑换。
4. 用户把 Key 保存到 Agent 的 Secret 或环境变量，不把它粘贴到 Prompt、聊天记录或源码。
5. 用户安装 VibeSMS Skill，连接并解锁 Android 手机、授权 USB 调试，再复制首页提供的不含 Key 的配置 Prompt。
6. Agent 询问 SIM 卡槽，下载并校验签名 APK，通过 ADB 安装、授权和绑定，再以 Key-scoped `status` 验证在线；用户也可在 APK 中手工完成相同流程。
7. 用户可用 Key 登录 `/inbox/`，或让 Agent 查询状态并等待短信、验证码与来电记录。

## 凭据边界

用户体验只有一个 Key，但服务端内部必须区分：

- 用户 Key：绑定号码、供 Agent 读取，可由管理员轮换或撤销。
- 一次性激活码：只用于首次生成用户 Key；服务端仅保存哈希，过期、兑换或作废后不再有效。
- 设备凭据：首次绑定后下发给 APK，仅可上传该设备事件和心跳。
- 管理员认证：签发 Key、解除设备绑定、查看审计，不与用户 Key 共用。

这样既保持接入简单，也避免用户 Key 泄露后直接伪造手机上报事件。

## GitHub Release 要求

- 正式下载页：`https://github.com/guanxiong/VibeSMS/releases`。
- CI 使用固定 JDK/Gradle 版本构建 release APK。
- 签名密钥只存于 GitHub Actions Secrets，不进入仓库。
- Release 同时发布 APK、版本说明和 `SHA256SUMS`。
- Android App 内展示版本、API 域名、绑定号码和最后上传状态。

## 已实现的 Agent API

- 管理员可在 `/admin/` 签发、轮换、禁用和解绑用户 Key，明文只显示一次。
- `POST /api/v1/bindings` 使用用户 Key 绑定 `device_id + sim_slot`，首次返回仅具上传权限的设备 Token。
- `GET /api/v1/status` 返回绑定状态、设备在线状态和任务游标。
- `GET /api/v1/inbox` 按 Key 绑定隔离读取短信与来电。
- `/inbox/` 提供无需账户、仅当前标签页保存 Key 的用户只读收件箱。
- `GET /api/v1/otp/wait` 支持最长 60 秒长轮询和 4–8 位验证码提取。
- `skills/vibesms/` 提供 Secret-only、零第三方依赖的 Agent 工作流与客户端。

## MVP-004 目标目录

新增实现按产品边界进入独立目录，避免把移动端、Agent 端和服务端混在一起：

```text
android/                     VibeSMS Terminal 原生 Android 工程
skills/vibesms/              可安装的 Agent Skill
.github/workflows/           Android 校验、签名与 Release 流水线
server/                      Key、绑定、Inbox 与现有设备上传 API
```

在对应实现开始前不创建空模块或占位 APK；每个目录随首个可测试的纵向功能切片一并加入仓库。

## 两期商业化路径

### 第一期：额度控制的自动签发与人工兜底（已实现）

- 站内申请表取代 GitHub Issue，收集邮箱、本人手机号、用途和终端数，不收集短信正文或任何已有凭据。
- 管理员控制自动签发开关和剩余名额；只在 Key 成功创建后原子扣减一个额度。
- 浏览器持久化随机匿名领取标识，服务端仅保存加域 SHA-256 摘要；数据库唯一索引和事务共同保证每个标识最多自动签发一次。重复领取保留为人工申请且不扣额度。该机制不采集硬件参数，但清除站点数据可重置本地标识，因此属于轻量防滥用而非强设备证明。
- 自动额度用尽后保留申请，管理员可生成默认 14 天有效的一次性激活码，通过邮箱或微信人工交付。
- 自动签发和激活码兑换产生的真实 Key 都只向用户显示一次；管理员只能看到 Key ID。
- 这一期不接入收款、邮件自动发送或第三方账户体系。

### 第二期：Dujiao 自动化交付（待启动）

- 将 VibeSMS 测试/付费资格作为 Dujiao 商品，库存单元为未使用的 VibeSMS 激活码。
- 支付成功后由受签名保护的回调保留一枚库存激活码并完成交付；失败、超时和退款需要释放或作废库存。
- 保持 Dujiao 的订单、支付和发卡记录为商业系统事实来源；VibeSMS 只负责激活码生命周期与用户 Key 兑换。
- 设计前先确定价格、退款政策、支付渠道和 Dujiao 部署环境；这些决策不在第一期假定。
