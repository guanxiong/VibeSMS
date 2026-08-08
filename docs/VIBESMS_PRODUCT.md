# VibeSMS 产品定义

## 定位

VibeSMS 是“用户自带 Android 手机与 SIM 的 Agent SMS Gateway”。用户无需注册独立平台账户；用户提交站内申请，管理员手工交付一次性激活码，用户自行兑换 Key。Key 对应一个手机号，Android Terminal 负责上传，Agent Skill 负责隔离读取短信和来电。

VibeSMS 不提供公共共享号码池，不面向绕过第三方平台风控或账号限制的用途。

## 已确认决策

- 产品名称：`VibeSMS`
- 云端入口：`https://sms.shareapi.ai`
- 身份方式：无独立用户账户，Key 即当前访问边界
- 默认映射：一个用户 Key 对应一个手机号
- Android 接入：用户在 APK 首次输入 Key，服务端换发仅具上传权限的设备凭据
- Agent 接入：用户 Key 只读取对应号码的短信、来电与验证码
- APK 分发：GitHub Releases，必须使用签名 APK 并发布 SHA-256 校验值
- 公开仓库：`https://github.com/guanxiong/VibeSMS`
- 未来统一身份：Key 记录预留 `owner_ref`，后续可关联 `llm.shareapi.ai` 或 `panel.shareapi.ai` 的用户主体

## 最小用户流程

1. 用户在 `/apply/` 申请测试资格，仅提交邮箱、用途和预计终端数量。
2. 管理员在 VibeSMS 管理端签发一次性激活码，并通过邮箱或微信人工交付。
3. 用户在 `/activate/` 输入激活码和自己的手机号，兑换仅显示一次的真实 Key。
4. 用户从 GitHub Releases 下载并校验 VibeSMS APK。
5. APK 中输入 Key、选择 SIM 卡槽并确认手机号；服务端绑定 Key、设备与 SIM，并为 APK 换发设备凭据。
6. 用户把 Key 保存到 Agent 的 Secret 或环境变量，也可用它登录 `/inbox/` 查看终端状态、短信和来电。
7. Agent 安装 VibeSMS Skill，查询在线状态并等待短信、验证码或来电记录。

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

### 第一期：人工审核与安全交付（已进入实现）

- 站内申请表取代 GitHub Issue；不在申请阶段收集手机号、短信正文或任何凭据。
- 管理员生成默认 14 天有效的一次性激活码，使用邮箱或微信人工交付。
- 用户自己在站内兑换真实 Key；管理员只能看到 Key ID 和兑换状态，不接触明文 Key。
- 这一期不接入收款、邮件自动发送或第三方账户体系。

### 第二期：Dujiao 自动化交付（待启动）

- 将 VibeSMS 测试/付费资格作为 Dujiao 商品，库存单元为未使用的 VibeSMS 激活码。
- 支付成功后由受签名保护的回调保留一枚库存激活码并完成交付；失败、超时和退款需要释放或作废库存。
- 保持 Dujiao 的订单、支付和发卡记录为商业系统事实来源；VibeSMS 只负责激活码生命周期与用户 Key 兑换。
- 设计前先确定价格、退款政策、支付渠道和 Dujiao 部署环境；这些决策不在第一期假定。
