# VibeSMS 产品定义

## 定位

VibeSMS 是“用户自带 Android 手机与 SIM 的 Agent SMS Gateway”。用户无需注册独立平台账户，由管理员手工签发 Key；Key 对应一个手机号，Android Terminal 负责上传，Agent Skill 负责隔离读取短信和来电。

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

1. 用户申请 Key，管理员在 VibeSMS 管理端手工签发。
2. 用户从 GitHub Releases 下载并校验 VibeSMS APK。
3. APK 中输入 Key、选择 SIM 卡槽并确认手机号。
4. 服务端绑定 Key、设备与 SIM，并为 APK 换发设备凭据。
5. 用户把 Key 保存到 Agent 的 Secret 或环境变量。
6. Agent 安装 VibeSMS Skill，查询在线状态并等待短信、验证码或来电记录。

## 凭据边界

用户体验只有一个 Key，但服务端内部必须区分：

- 用户 Key：绑定号码、供 Agent 读取，可由管理员轮换或撤销。
- 设备凭据：首次绑定后下发给 APK，仅可上传该设备事件和心跳。
- 管理员认证：签发 Key、解除设备绑定、查看审计，不与用户 Key 共用。

这样既保持接入简单，也避免用户 Key 泄露后直接伪造手机上报事件。

## GitHub Release 要求

- 正式下载页：`https://github.com/guanxiong/VibeSMS/releases`。
- CI 使用固定 JDK/Gradle 版本构建 release APK。
- 签名密钥只存于 GitHub Actions Secrets，不进入仓库。
- Release 同时发布 APK、版本说明和 `SHA256SUMS`。
- Android App 内展示版本、API 域名、绑定号码和最后上传状态。
