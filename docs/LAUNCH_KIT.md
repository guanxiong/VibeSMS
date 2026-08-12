# VibeSMS Public Beta 首发物料包

本物料包用于邀请早期测试者，不用于暗示 VibeSMS 提供公共接码、共享号码或规避第三方服务规则。每篇对外内容都应链接到官网、申请页和数据与隐私说明；不要承诺免费名额数量、价格、支持响应时间或数据保留期，除非这些已经确定。

## 首发目标与唯一转化

- **对象**：已经在使用 Codex、Claude Code、Cursor 或同类 Agent 的开发者；他们有自己的 Android 手机与 SIM，并有合法的短信/来电自动化需求。
- **唯一 CTA**：`https://sms.shareapi.ai/apply/` 申请测试 Key。先在 VibeSMS 管理后台创建活动，再使用后台生成的 `?campaign=…` 链接；服务仅接受已启用活动，不保存完整 URL 或访客标识。
- **首发验证事件**：申请 Key → 完成设备绑定 → Agent 成功收到一条新事件。不要只把 Star 或页面访问量当作成功。
- **信任链接**：[官网](https://sms.shareapi.ai/) · [数据与隐私说明](https://sms.shareapi.ai/privacy/) · [源码](https://github.com/guanxiong/VibeSMS) · [签名 APK](https://github.com/guanxiong/VibeSMS/releases/tag/v0.2.0)

## 发布前检查

1. 在管理端确认自动签发名额与人工审核渠道；额度不足时，申请页会进入人工队列。
2. 用一台真实 Android 设备完成一次「申请 → 绑定 → Agent 等待新 OTP」端到端演示，并录制 30–45 秒无敏感信息的视频/GIF。
3. 演示中使用测试号码、模拟验证码和已脱敏设备信息；不要展示真实 Key、手机号或短信内容。
4. 发布时准确说明许可：Android Terminal 与 VibeSMS Skill 采用 Apache-2.0；服务端、控制台与部署代码保留商业许可。不要把整个仓库宣传为开源。
5. 为公开讨论准备固定答复：仅限自有/授权号码；不提供共享号码池；不协助规避平台规则；Beta 期间请勿用于关键业务。

## 14 天首发节奏

| 时间 | 动作 | 成功信号 |
| --- | --- | --- |
| D-2 至 D0 | 完成演示、确认名额、发布 GitHub Release / Announcement | 任一新用户能独立完成接入 |
| D1 | 同步 GitHub、skills.sh、中文开发者社区和 X | 10 个合格申请，而非泛流量 |
| D2–D4 | 逐一跟进首批申请，修复第一个卡点 | 至少 3 个用户完成绑定 |
| D5 | 发布“从手机到 Agent”的完整 Demo | 首次真实 Agent 收件事件 |
| D7 | 汇总常见问题，更新 README / Skill | 激活率高于纯申请数 |
| D10–D14 | 选择表现最好的一个中英文渠道复投 | 形成可复用的获客渠道 |

## GitHub Announcement / README 摘要

```md
## VibeSMS Public Beta is open

VibeSMS turns **your own Android phone and SIM** into an SMS and call terminal that an agent can use. It is built for Agent Skills clients such as Codex, Claude Code, Cursor, GitHub Copilot and OpenCode.

- One Key, one bound number: events are isolated by device and SIM slot.
- Offline queue and heartbeat: events can be retried after a connection returns.
- Agent-ready OTP workflow: record a cursor, then wait for the next message instead of reading a stale code.
- Separate device upload credentials and Agent read credentials.

This is a limited Public Beta. It is for numbers you own or are authorized to manage—not shared number pools, bulk registration, resale, or bypassing third-party rules.

Request a test Key: https://sms.shareapi.ai/apply/
Privacy and data notice: https://sms.shareapi.ai/privacy/
```

## 中文社区帖（V2EX / 即刻 / 开发者社群）

**标题：** VibeSMS：把自己的 Android 手机和 SIM 变成 Agent 可调用的短信终端，开放 Public Beta

```text
我做了 VibeSMS：让自己的 Android 手机和 SIM 变成 Agent 可调用的短信与来电终端。

它解决的不是“找一个接码号码”，而是把你自己的号码以可控的方式交给 Agent：一个 Key 只读取已绑定设备和 SIM 卡槽的事件；手机断网后会补发；Agent 可以先记录游标，再等待任务开始后的下一条验证码，避免误读历史短信。

支持 Codex、Claude Code、Cursor 等 Agent Skills 客户端。安装 Skill 后，可以直接让 Agent：
“记录当前游标，然后等待下一条验证码。”

目前开放限量 Public Beta，适合已经有自己 Android 手机和 SIM、希望让 Agent 协助处理合法自有账号流程的开发者。

不提供共享号码池，不面向批量注册、转售或绕过第三方平台规则。

官网：https://sms.shareapi.ai/
申请测试 Key：https://sms.shareapi.ai/apply/
数据与隐私说明：https://sms.shareapi.ai/privacy/
源码与签名 APK：https://github.com/guanxiong/VibeSMS
```

## X / English short post

```text
VibeSMS Public Beta is open.

Turn your own Android phone + SIM into an SMS/call terminal for your agent.

• Key-scoped inbox, bound to a device + SIM slot
• Offline queue + heartbeat
• Wait for the next OTP with a cursor—no stale-code reads
• Agent Skill for Codex, Claude Code, Cursor & more

BYO number only. No shared pools, resale, bulk signups, or bypassing platform rules.

Try it: https://sms.shareapi.ai/apply/
```

## Hacker News / Reddit 英文帖

**Title:** Show HN: VibeSMS – use your own Android phone and SIM as an agent SMS gateway

```text
I built VibeSMS because agent workflows sometimes need to wait for a message sent to a number the user already owns. Existing SMS services often mean shared numbers or a separate identity boundary; this is deliberately BYO Android phone and SIM instead.

The Android terminal stores an offline queue and sends heartbeats. The server issues a Key scoped to one bound device and SIM slot. An Agent Skill records the latest cursor before a task, then waits for the next OTP so it does not accidentally return an old message. Device upload credentials are separate from the Key used to read the inbox.

It is an early Public Beta, not a shared-number service. It is only for numbers the user owns or is authorized to manage, and it is not intended for bulk signups, resale, or bypassing third-party rules.

Demo / request a test Key: https://sms.shareapi.ai/apply/
Source: https://github.com/guanxiong/VibeSMS
Privacy / data notice: https://sms.shareapi.ai/privacy/

I would especially value feedback on onboarding friction, Android permission handling, and the Key/terminal security boundary.
```

## 首条演示视频脚本（40 秒）

| 时间 | 画面 | 旁白 / 字幕 |
| --- | --- | --- |
| 0–5s | 展示官网标题与自己的已脱敏 Android 手机 | “这是 VibeSMS：把自己的号码交给 Agent。” |
| 5–12s | 申请 Key、保存为 `VIBESMS_KEY`，全程遮住真实值 | “一个 Key 对应一个绑定号码，Key 不写进 Prompt。” |
| 12–22s | Agent 安装 Skill，Android 终端在线 | “手机成为终端，上传凭据和 Agent 的读取 Key 分离。” |
| 22–34s | 先记录游标，再触发一条模拟/测试短信，Agent 收到新 OTP | “Agent 只等待任务开始后的新事件，不误读历史验证码。” |
| 34–40s | 官网 CTA、隐私页与申请页 | “Public Beta 开放申请：只接入你拥有或获授权的号码。” |

## 常见问题：可直接回复

**这是接码平台吗？** 不是。VibeSMS 不提供共享号码池；它连接的是用户自己的 Android 手机和 SIM。

**会读取所有短信吗？** 已绑定 Key 的 Agent 只能读取该 Key 绑定设备与 SIM 卡槽的事件。服务管理员为运维和安全审计可以访问部署实例中存储的记录，详情见数据与隐私说明。

**支持哪些 Agent？** Skill 按开放 Agent Skills 方式分发，可用于 Codex、Claude Code、Cursor、GitHub Copilot、OpenCode 及兼容客户端。

**能用于批量注册或绕过短信验证吗？** 不可以。此类用途不在 Beta 范围内，也不应申请测试资格。

## 首发后应记录的最小指标

- 合格申请数（真实自有/授权号码需求）
- Key 签发数、绑定完成数、首个成功事件数
- 从申请到成功绑定的中位耗时
- 首次失败原因：ADB、权限、APK 安装、SIM 选择、网络、Key 保存
- 每个渠道带来的合格申请与成功绑定数

这些指标可先通过申请记录、管理控制台和人工反馈维护；在未明确用户同意前，不要为推广目的把短信内容写入分析系统。
