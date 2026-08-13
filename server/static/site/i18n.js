(() => {
  "use strict";

  const STORAGE_KEY = "vibesms.locale";
  const translations = {
    "跳到主要内容": "Skip to main content",
    "跳到申请表单": "Skip to application form",
    "跳到兑换表单": "Skip to activation form",
    "工作方式": "How it works",
    "安全": "Security",
    "隐私": "Privacy",
    "Key 收件箱": "Key Inbox",
    "申请测试 Key": "Request a test Key",
    "兑换激活码": "Redeem activation code",
    "下载 APK": "Download APK",
    "下载 Android APK": "Download Android APK",
    "已有激活码？兑换 Key": "Have an activation code? Redeem it",
    "让你的 Agent，": "Your phone number,",
    "安全接收": "ready for",
    "手机短信。": "your agent.",
    "把一台 Android 手机变成可靠的短信与来电终端。一个 Key 绑定一个号码，Agent 只读取属于它的事件。": "Turn an Android phone into a reliable SMS and incoming-call terminal. One Key maps to one number, and each agent sees only its own events.",
    "VibeSMS Agent 接码示例": "VibeSMS agent verification example",
    "正在检查服务": "Checking service",
    "核心能力": "Core capabilities",
    "三步，": "Three steps",
    "把你的": "to connect",
    "号码": "your number",
    "把你的号码": "to connect your number",
    "交给 Agent。": "to an agent.",
    "没有新的账户体系。自动名额可用时前台直接签发 Key；额度用尽后进入人工审核。Android 首次绑定后换取独立设备凭据。": "No new account system. When public capacity is available, a Key is issued immediately; otherwise the request enters manual review. Android receives a separate device credential after first binding.",
    "自动获得 Key": "Get a Key automatically",
    "管理员控制公开名额；有额度时立即签发，无额度时保留为人工申请。": "Public capacity is admin-controlled. Available slots issue a Key immediately; otherwise your request is kept for review.",
    "连接 Android": "Connect Android",
    "安装 VibeSMS Terminal，输入 Key、选择 SIM，并按下方说明允许锁屏后台运行；离线事件会在网络恢复后补发。": "Install VibeSMS Terminal, enter the Key, choose a SIM, and allow lock-screen background operation. Offline events are delivered when the network returns.",
    "配置 Agent Skill": "Configure the Agent Skill",
    "Key 放入 Secret，Agent 即可等待新短信、提取验证码或读取来电状态。": "Store the Key as a secret so your agent can wait for new messages, extract verification codes, and read incoming-call status.",
    "安装 Skill": "Install Skill",
    "华为手机请允许 VibeSMS 后台启动": "Allow VibeSMS to run in the background on Huawei phones",
    "华为系统可能在断开电源并锁屏后暂停第三方应用。完成绑定后，请额外检查以下设置；菜单名称会因 EMUI 版本略有不同。": "Huawei may pause third-party apps after power is disconnected and the screen is locked. After binding, check these settings; menu names can vary by EMUI version.",
    "打开": "Open",
    "设置 → 应用 → 应用启动管理": "Settings → Apps → App launch",
    "，找到 VibeSMS。": " and find VibeSMS.",
    "关掉": "Turn off ",
    "自动管理": "Manage automatically",
    "，打开": ", then turn on ",
    "允许自启动、允许关联启动、允许后台活动": "Auto-launch, Secondary launch, and Run in background",
    "。": ".",
    "在": "Under ",
    "电池优化": "Battery optimization",
    "中将 VibeSMS 设为": ", set VibeSMS to ",
    "不允许优化": "Don't allow",
    "；再进入": ". Then go to ",
    "设置 → 电池 → 更多电池设置": "Settings → Battery → More battery settings",
    "，开启": " and enable ",
    "休眠时始终保持网络连接": "Stay connected while asleep",
    "返回 VibeSMS，确认终端状态显示": "Return to VibeSMS and confirm the terminal says ",
    "已允许后台运行": "Background operation allowed",
    "；Web 收件箱可查看最后在线时间。": ". The web inbox shows the last online time.",
    "说明：": "Note: ",
    "终端约每 9 分钟尝试一次锁屏心跳，15 分钟任务作为兜底。厂商节能策略仍可能延迟执行；固定终端保持供电更稳定。": "The terminal attempts a lock-screen heartbeat about every 9 minutes, with a 15-minute fallback job. Vendor power policies can still delay execution; a dedicated terminal is more reliable when kept powered.",
    "先用自己的号码，": "Bring your own number.",
    "把真实需求带进 Beta。": "Bring real needs to the beta.",
    "VibeSMS 正在邀请需要把自己 Android 手机和 SIM 接入 Agent 的开发者参与测试。自动名额开放时可立即领取 Key；名额暂停后，我们会人工审核申请。": "VibeSMS invites developers who want to connect their own Android phone and SIM to an agent. Claim a Key immediately while public capacity is open; otherwise we will review your request.",
    "仅接入你拥有或获授权管理的号码": "Connect only numbers you own or are authorized to manage",
    "不提供共享号码池，也不面向批量注册、转售或规避平台规则": "No shared number pool, bulk registration, resale, or bypassing platform rules",
    "Beta 仍在迭代；请先在非关键工作流中验证": "The beta is still evolving; validate it in a non-critical workflow first",
    "查看数据与隐私说明": "Read the data & privacy notice",
    "不是一个": "Not a",
    "“短信列表”，": "message dump,",
    "而是一条清晰的": "but a clear",
    "接码会话。": "verification session.",
    "游标确保 Agent 只处理任务开始后到达的": "A cursor ensures that the agent handles only ",
    "新事件。": "new events that arrive after the task begins.",
    "每次读取受": " Every read is",
    "Key 隔离": "isolated by Key",
    "，并保留": ", with a ",
    "最小审计记录。": "minimal audit trail.",
    "长轮询等待，无需高频请求": "Long polling without frequent requests",
    "短信、来电和心跳统一事件模型": "One event model for SMS, calls, and heartbeats",
    "4–8 位验证码自动提取": "Automatic extraction of 4–8 digit codes",
    "设备上传凭据与 Agent Key 分离": "Separate device upload credentials and agent Keys",
    "复制": "Copy",
    "给 Agent 一项": "Give your agent",
    "真正可执行的": "an actionable",
    "接码能力。": "SMS capability.",
    "VibeSMS Skill 会先记录事件游标，再等待任务开始后的新短信，避免把历史验证码误当成当前结果。": "The VibeSMS Skill records the event cursor before waiting for new messages, so an old code is never mistaken for the current result.",
    "查看 Skill 源码": "View Skill source",
    "Skills.sh 仓库页": "Skills.sh listing",
    "一条命令安装": "Install with one command",
    "复制命令": "Copy command",
    "GitHub CLI：": "GitHub CLI: ",
    "Secret：": "Secret: ",
    "把 Key 保存为": "Store the Key as",
    "，不要放进提示词、源码或聊天记录。": "; never put it in prompts, source code, or chat history.",
    "安装后可以直接对 Agent 说：": "After installation, ask your agent:",
    "“检查我的 VibeSMS 终端是否在线。”": "“Check whether my VibeSMS terminal is online.”",
    "“先记录游标，然后等待下一条验证码。”": "“Record the cursor, then wait for the next verification code.”",
    "“等待下一条新短信，并提取其中的验证码。”": "“Wait for the next new SMS and extract its verification code.”",
    "“读取这个 Key 最近的来电记录。”": "“Read the recent incoming calls for this Key.”",
    "Codex · Claude Code · Cursor · GitHub Copilot · OpenCode · 其他 Agent Skills 客户端": "Codex · Claude Code · Cursor · GitHub Copilot · OpenCode · other Agent Skills clients",
    "一个简单的 Key，": "One simple Key.",
    "三条明确的": "Three explicit",
    "安全边界。": "security boundaries.",
    "Key 只显示一次": "Keys are shown once",
    "用户 Key 与设备凭据均仅保存 SHA-256 哈希，泄露后可立即轮换或禁用。": "User Keys and device credentials are stored only as SHA-256 hashes and can be rotated or disabled after exposure.",
    "设备只能上传": "Devices can only upload",
    "首次绑定换取独立设备凭据；设备凭据可上传事件，但不能读取 Inbox。": "First binding returns a separate device credential. It can upload events but cannot read the Inbox.",
    "Agent 只能读自己的号码": "Agents can read only their number",
    "Key 与设备及 SIM 卡槽绑定，查询层只返回该绑定下的短信与来电。": "A Key is bound to a device and SIM slot; queries return only SMS and calls from that binding.",
    "从手机到 Agent，": "From phone to agent,",
    "完整链路": "the complete path",
    "已经可用。": "is ready.",
    "公网 HTTPS、设备心跳、断网补发": "Public HTTPS, device heartbeats, offline retry",
    "独立设备密钥与管理认证": "Separate device credentials and admin authentication",
    "Key Inbox API 与 Agent Skill": "Key Inbox API and Agent Skill",
    "关键词过滤的飞书 Webhook 转发": "Keyword-filtered Feishu webhook forwarding",
    "VibeSMS Android Terminal": "VibeSMS Android Terminal",
    "签名 APK 与 GitHub Release": "Signed APK and GitHub Release",
    "打开 Key 收件箱": "Open Key Inbox",
    "管理员登录": "Admin sign in",
    "关闭申请窗口": "Close request dialog",
    "无需注册账户。每个设备只可自动领取一次；有名额时立即显示真实 Key，重复领取或额度用尽后转入人工审核。": "No account required. Each device can claim one instant Key; repeat requests or requests after capacity is exhausted enter manual review.",
    "正在检查自动签发名额…": "Checking instant-issue capacity…",
    "邮箱": "Email",
    "必填": "Required",
    "要接入的手机号": "Phone number to connect",
    "用途": "Use case",
    "例如：让 Agent 完成我自己账号的注册验证；不会用于批量注册或转售。": "Example: let my agent verify registration for my own account; not for bulk registration or resale.",
    "Android 终端数": "Android terminals",
    "预计接入的 Android 终端": "Expected Android terminals",
    "1 台": "1 terminal",
    "2–5 台": "2–5 terminals",
    "6 台以上": "6+ terminals",
    "补充联系方式": "Additional contact",
    "可选": "Optional",
    "可选，例如微信号": "Optional, such as WeChat",
    "例如微信号": "For example, WeChat ID",
    "便于人工交付激活码": "For delivery of a manually issued code",
    "网站": "Website",
    "提交并获取 Key": "Submit and get a Key",
    "提交申请": "Submit request",
    "仅限你拥有或获授权管理的号码。不要提交短信正文、验证码或凭据。": "Only for numbers you own or are authorized to manage. Do not submit message bodies, verification codes, or credentials.",
    "Key 已生成，接下来交给 Agent。": "Your Key is ready. Hand it to your agent.",
    "先复制 Key 并保存为本机 Secret": "Copy the Key and store it as the local secret",
    "。为避免泄露，下面的 Prompt 不包含你的 Key。": ". To prevent exposure, the prompt below does not contain your Key.",
    "复制 Key": "Copy Key",
    "安装 VibeSMS Skill": "Install the VibeSMS Skill",
    "让 Agent 获得受约束的 Android 配置和接码流程。": "Give your agent a constrained Android setup and SMS workflow.",
    "手机解锁并连接 USB": "Unlock the phone and connect USB",
    "打开 USB 调试，在手机上确认这台电脑的 ADB 授权。": "Enable USB debugging and approve this computer for ADB on the phone.",
    "把配置任务交给 Agent": "Hand setup to your agent",
    "Agent 会询问 SIM 1 或 SIM 2，安装并校验签名 APK、绑定终端，再验证在线状态。": "The agent asks for SIM 1 or SIM 2, installs and verifies the signed APK, binds the terminal, and confirms it is online.",
    "复制 Prompt": "Copy prompt",
    "使用 VibeSMS Skill 的 Android USB 配置流程设置我的手机。手机已解锁并通过 USB 连接；请先检查 ADB 授权，再询问我使用 SIM 1 还是 SIM 2。请仅从本机的 VIBESMS_KEY Secret 或环境变量读取 Key，不要让我把 Key 粘贴到聊天或命令行。自动下载并校验官方签名 APK、安装、授予必要权限、完成绑定，并用 status 验证终端在线后报告结果。": "Use the VibeSMS Skill to set up my Android phone over USB. The phone is unlocked and connected. Check ADB authorization first, then ask whether I want SIM 1 or SIM 2. Read the Key only from the local VIBESMS_KEY secret or environment variable; do not ask me to paste it into chat or a command. Download and verify the official signed APK, install it, grant the required permissions, bind the terminal, and report only after status confirms it is online.",
    "打开 Key 收件箱 →": "Open Key Inbox →",
    "完成": "Done",
    "申请已进入审核队列。": "Your request is in the review queue.",
    "。当前自动名额不可用，审核后会通过你填写的联系方式发送一次性激活码。": ". Instant issue is currently unavailable. After review, a one-time activation code will be sent using your contact details.",
    "兑换激活码 →": "Redeem activation code →",
    "关闭": "Close",

    "申请一个": "Request a",
    "测试 Key，": "test Key",
    "把自己的号码": "and connect your number",
    "无需新建账户。每个设备只可自动领取一次；有名额时立即生成真实 Key，重复领取或额度暂停时进入人工审核。": "No new account is required. Each device can claim one instant Key; repeat requests or requests while capacity is paused enter manual review.",
    "你需要提交": "You provide",
    "邮箱、自己的手机号和简要用途": "Email, your phone number, and a short use case",
    "首次设备领取": "First claim on this device",
    "有名额时获得只显示一次的真实 Key": "Receive a real Key shown once when capacity is open",
    "下一步": "Next",
    "在自己的 Android 终端首次绑定 SIM": "Bind the SIM on your Android terminal",
    "告诉我们你的": "Tell us how",
    "使用方式": "you will use it",
    "请确认这是你拥有或获授权管理的号码。请勿发送任何短信正文、验证码或凭据。提交前请阅读": "Confirm that you own or are authorized to manage this number. Do not send message bodies, verification codes, or credentials. Before submitting, read the ",
    "你的测试 Key 已生成。": "Your test Key is ready.",
    "Key 已临时保存在当前浏览器标签页。请立即复制到 Secret 管理器；关闭标签页后，本地状态会清除。": "The Key is stored temporarily in this browser tab. Copy it to your secret manager now; local state is cleared when the tab closes.",
    "用 Agent 自动配置 Android": "Configure Android with your agent",
    "把 Key 保存为本机 Secret": "Store the Key as the local secret",
    "，不要粘贴进 Prompt。然后连接并解锁手机、打开 USB 调试。": ". Do not paste it into a prompt. Then connect and unlock the phone and enable USB debugging.",
    "交给 Agent": "Hand to agent",
    "申请编号": "Request ID",
    "当前自动名额不可用。审核通过后，我们会通过邮箱或你留下的联系方式发送一次性激活码。": "Instant issue is currently unavailable. After approval, we will send a one-time activation code by email or your provided contact method.",
    "我已经有激活码 →": "I already have an activation code →",

    "兑换激活码，": "Redeem a code",
    "生成只属于": "to generate a Key",
    "你的 Key。": "that belongs to you.",
    "激活码不是 Key，也只能兑换一次。填写你要接入的手机号后，系统会生成一个只显示一次的 VibeSMS Key。": "An activation code is not a Key and can be redeemed only once. Enter the phone number you want to connect to generate a VibeSMS Key that is shown once.",
    "一枚激活码": "One activation code",
    "只生成一个用户 Key": "Generates one user Key",
    "一个 Key": "One Key",
    "只读取一个号码对应的事件": "Reads events for one number",
    "请立即保存": "Save it now",
    "Key 不会再次以明文显示": "The Key will not be shown again",
    "输入激活码和": "Enter an activation code",
    "手机号": "and phone number",
    "手机号只在此时提交，用于创建号码与 Key 的隔离关系。": "The phone number is submitted only here to establish isolation between the number and its Key.",
    "一次性激活码": "One-time activation code",
    "兑换我的 Key": "Redeem my Key",
    "请确认这是你拥有或获授权管理的号码。不要把激活码或生成后的 Key 发给他人。": "Confirm that you own or are authorized to manage this number. Do not share the activation code or generated Key.",
    "现在就保存你的 Key。": "Save your Key now.",
    "此 Key 已临时保存在当前浏览器标签页，打开收件箱即可继续。关闭标签页后本地状态会清除。": "This Key is stored temporarily in the current browser tab. Open the inbox to continue; local state is cleared when the tab closes.",

    "返回 VibeSMS 首页": "Back to the VibeSMS homepage",
    "只看属于": "See only messages",
    "这个 Key 的": "that belong to",
    "消息。": "this Key.",
    "无需注册新账户。输入管理员签发的 VibeSMS Key，即可查看它所绑定号码的终端状态、短信和来电。": "No new account is required. Enter an issued VibeSMS Key to see the terminal status, messages, and calls for its bound number.",
    "隔离范围": "Isolation",
    "一个 Key · 一个号码": "One Key · one number",
    "凭据保存": "Credential storage",
    "仅当前浏览器标签页": "Current browser tab only",
    "权限": "Permissions",
    "读取消息与管理本 Key 的转发": "Read messages and manage forwarding for this Key",
    "打开我的收件箱": "Open my inbox",
    "手机跳转使用不会发送给服务器的 URL 片段传入 Key，页面读取后会立即清除地址栏片段。关闭当前标签页后，本地登录状态自动清除。": "Phone handoff passes the Key in a URL fragment that is never sent to the server. The fragment is removed immediately after reading, and local sign-in state is cleared when this tab closes.",
    "还没有 Key？": "Need a Key?",
    "申请测试 Key →": "Request a test Key →",
    "我的收件箱": "My inbox",
    "退出并清除 Key": "Sign out and clear Key",
    "绑定号码": "Bound number",
    "终端状态": "Terminal status",
    "SIM 卡槽": "SIM slot",
    "当前游标": "Current cursor",
    "最后在线": "Last online",
    "飞书 Webhook 转发": "Feishu webhook forwarding",
    "尚未配置": "Not configured",
    "展开设置": "Expand settings",
    "收起设置": "Collapse settings",
    "服务端只转发命中关键词的新短信。多个关键词按“任一命中”处理；例如仅填写“验证码”，其他短信不会发送到飞书。": "The server forwards only new messages matching a keyword. Multiple keywords use any-match logic; if you enter only “verification code,” other messages are not sent to Feishu.",
    "飞书机器人 Webhook 地址": "Feishu bot webhook URL",
    "首次配置必填": "Required for first setup",
    "转发关键词": "Forwarding keywords",
    "验证码": "verification code",
    "必填，逗号或换行分隔，最多 10 个": "Required; comma or line separated, up to 10",
    "启用自动转发": "Enable automatic forwarding",
    "关闭后保留配置和历史投递记录": "Keep settings and delivery history when paused",
    "短信正文会发送到你配置的飞书群机器人。Webhook 地址包含访问凭据，服务端需要保存它用于投递，但查询接口不会返回完整地址。": "Message bodies are sent to the Feishu group bot you configure. The webhook URL contains a credential and must be stored for delivery, but query APIs never return the full URL.",
    "保存转发设置": "Save forwarding settings",
    "发送测试消息": "Send test message",
    "删除配置": "Delete settings",
    "最近投递": "Recent deliveries",
    "刷新状态": "Refresh status",
    "配置后，这里会显示命中关键词的投递结果。": "Keyword-matched delivery results appear here after setup.",
    "检查中": "Checking",
    "事件类型": "Event type",
    "全部": "All",
    "短信": "SMS",
    "来电": "Calls",
    "正在读取…": "Loading…",
    "立即刷新": "Refresh now",
    "项目主页": "Homepage",
    "安全说明": "Security",

    "数据与隐私说明": "Data & Privacy Notice",
    "生效日期：2026 年 8 月 13 日。VibeSMS 是一个仍在迭代中的 Public Beta；本页用清晰、可核验的语言说明当前服务处理什么数据，以及你在申请前应当知道什么。": "Effective August 13, 2026. VibeSMS is an evolving public beta. This notice explains in clear, verifiable terms what data the service processes and what you should know before applying.",
    "使用边界": "Acceptable use",
    "仅连接你拥有或明确获授权管理的 Android 手机与 SIM。VibeSMS 不提供公共或共享号码池，不用于批量注册、转售、绕过第三方服务的规则或任何未经授权的访问。": "Connect only Android phones and SIMs that you own or are explicitly authorized to manage. VibeSMS does not provide a public or shared number pool and must not be used for bulk registration, resale, bypassing third-party rules, or unauthorized access.",
    "服务会处理的数据": "Data the service processes",
    "申请信息：": "Application data:",
    "邮箱、要绑定的手机号、用途、预计终端数，以及你选择提供的联系方式。": "Email, the phone number to bind, use case, expected terminal count, and any contact details you choose to provide.",
    "终端与事件信息：": "Terminal and event data:",
    "设备标识、SIM 卡槽及标签、应用版本、电量、网络类型、心跳时间、来电号码，以及短信的发送方、正文和接收时间。": "Device identifier, SIM slot and label, app version, battery level, network type, heartbeat time, incoming-call number, and SMS sender, body, and received time.",
    "访问凭据：": "Access credentials:",
    "用户 Key、设备上传凭据和激活码的哈希值。真实 Key 与设备凭据只在签发或绑定时显示一次；服务端不以明文保存它们。": "Hashed user Keys, device upload credentials, and activation codes. Real Keys and device credentials are shown once when issued or bound and are not stored as plaintext.",
    "转发配置：": "Forwarding settings:",
    "你为当前 Key 主动配置的飞书机器人 Webhook 地址、关键词、启用状态，以及投递时间、状态、重试次数和错误摘要。Webhook 地址是服务端代你投递所需的第三方凭据。": "The Feishu bot webhook URL, keywords, enabled state, and delivery timestamps, status, retry count, and error summaries that you configure for the current Key. The webhook URL is a third-party credential required for server-side delivery.",
    "数据如何被使用与存放": "How data is used and stored",
    "数据用于签发和管理 Key、将事件按已绑定的设备与 SIM 隔离、向对应 Key 的 Agent 或收件箱提供读取能力、按用户配置的关键词向飞书投递短信，以及维护终端在线状态和安全审计。当前服务把这些数据保存在部署实例的 SQLite 数据库中。": "Data is used to issue and manage Keys, isolate events by bound device and SIM, provide access to the corresponding agent or inbox, forward messages to Feishu according to user-configured keywords, maintain terminal presence, and support security auditing. The current service stores this data in the deployment's SQLite database.",
    "当前版本": "The current version ",
    "不会自动删除": "does not automatically delete",
    "短信事件、申请记录或设备记录，也没有面向用户的自助删除界面。请只接入你接受由该部署实例处理的号码；不要通过申请表发送短信正文、验证码或其他凭据。": " SMS events, applications, or device records, and there is no user-facing self-service deletion interface. Connect only numbers you accept this deployment processing, and never submit message bodies, verification codes, or other credentials through the application form.",
    "访问控制与安全": "Access control and security",
    "一个用户 Key 仅可读取其绑定号码、设备与 SIM 卡槽的事件，并管理这个 Key 自己的转发配置。Android 终端使用独立的上传凭据，不能读取收件箱或修改转发。管理认证可查看运维所需的记录，因此服务管理员可能接触存储的事件内容和 Webhook 配置。Key 泄露时，请立即在管理端轮换或禁用，或联系部署运营者处理。": "A user Key can read only events for its bound number, device, and SIM slot and manage forwarding for that Key. Android terminals use separate upload credentials and cannot read the inbox or change forwarding. Administrative access can view operational records, so service operators may access stored event content and webhook settings. If a Key is exposed, rotate or disable it immediately or contact the deployment operator.",
    "浏览器与第三方": "Browser storage and third parties",
    "当前公开站点不加载广告、统计像素或第三方分析脚本。为了执行“每个设备仅自动领取一次”，申请页面会在浏览器": "The public site does not load ads, tracking pixels, or third-party analytics. To enforce one instant claim per device, the application page generates a random anonymous claim identifier in browser",
    "中生成一个随机匿名领取标识；服务端只保存加域 SHA-256 摘要，不采集硬件参数、完整 URL、IP 或 User-Agent。清除浏览器站点数据会删除本地标识，因此它不是不可绕过的硬件指纹。推广链接中的": ". The server stores only a domain-separated SHA-256 digest and does not collect hardware attributes, the full URL, IP address, or User-Agent. Clearing site data removes the local identifier, so it is not an unresettable hardware fingerprint. The",
    "仅在提交申请时作为后台预设活动标签写入记录。Key 收件箱会将你主动输入或通过 URL 片段导入的 Key 临时放在当前标签页的": "value in a campaign link is written to the request only as an operator-defined campaign label. The Key Inbox temporarily stores a Key you enter or import through a URL fragment in the current tab's",
    "；关闭标签页后清除，Key 不会被放入发送给服务端的 URL 查询参数。": ". It is cleared when the tab closes, and the Key is never placed in a URL query parameter sent to the server.",
    "只有当你主动保存并启用飞书 Webhook 后，命中关键词的新短信才会发送到该飞书机器人。飞书是独立第三方，收到的数据将受其服务条款、群权限和数据保留规则约束；删除 VibeSMS 中的转发配置不会撤回已经发送到飞书的消息。": "Only after you save and enable a Feishu webhook are new keyword-matched messages sent to that bot. Feishu is an independent third party, and received data is governed by its terms, group permissions, and retention rules. Deleting the VibeSMS forwarding configuration does not retract messages already sent to Feishu.",
    "问题、数据请求与变更": "Questions, data requests, and changes",
    "本项目仍处于 Beta，数据删除、导出和保留周期尚未产品化。若需要处理已提交的申请信息、绑定或存储事件，请通过项目的": "The project remains in beta, and deletion, export, and retention controls are not yet productized. To request action on submitted application data, bindings, or stored events, contact the maintainers through",
    "联系维护者；请勿在公开 Issue 中附上 Key、手机号、短信正文或验证码。安全问题请遵循": ". Do not include Keys, phone numbers, message bodies, or verification codes in a public Issue. For security issues, follow the private reporting process in the",
    "的私密报告方式。": ".",
    "服务能力或数据处理方式发生实质变更时，本页会更新生效日期。本说明是当前 Beta 的产品说明，不替代适用法律下可能需要的正式隐私政策或用户协议。": "This page will update its effective date when service capabilities or data practices change materially. This is a product notice for the current beta and does not replace any formal privacy policy or user agreement required by applicable law.",
    "我了解，申请测试 Key": "I understand — request a test Key",
    "返回首页": "Back to homepage"
  };

  const pageMeta = {
    "/": {
      zh: ["VibeSMS — 让 Agent 安全接收手机短信", "VibeSMS 把你自己的 Android 手机和 SIM 变成 Agent 可调用的短信与来电网关。"],
      en: ["VibeSMS — Your phone number, ready for your agent", "Turn your own Android phone and SIM into an SMS and incoming-call gateway for AI agents."]
    },
    "/apply/": {
      zh: ["申请测试 Key · VibeSMS", "申请 VibeSMS 测试 Key；自动名额可用时立即获得 Key。"],
      en: ["Request a test Key · VibeSMS", "Request a VibeSMS test Key and receive it instantly when public capacity is available."]
    },
    "/activate/": {
      zh: ["兑换激活码 · VibeSMS", "兑换 VibeSMS 一次性激活码，获得只显示一次的用户 Key。"],
      en: ["Redeem an activation code · VibeSMS", "Redeem a one-time VibeSMS activation code for a user Key that is shown once."]
    },
    "/inbox/": {
      zh: ["Key 收件箱 · VibeSMS", "使用 VibeSMS Key 查看对应号码的短信、验证码、来电和终端状态。"],
      en: ["Key Inbox · VibeSMS", "Use a VibeSMS Key to view messages, verification codes, calls, and terminal status for its number."]
    },
    "/privacy/": {
      zh: ["数据与隐私说明 · VibeSMS", "VibeSMS Public Beta 的数据与隐私说明。"],
      en: ["Data & Privacy Notice · VibeSMS", "Data and privacy notice for the VibeSMS public beta."]
    }
  };

  const normalizePath = () => {
    const path = window.location.pathname;
    if (path === "/") return "/";
    return path.endsWith("/") ? path : `${path}/`;
  };

  const params = new URLSearchParams(window.location.search);
  const requested = params.get("lang");
  let saved = "";
  try { saved = window.localStorage.getItem(STORAGE_KEY) || ""; } catch (_) { /* storage may be unavailable */ }
  const language = requested === "en" || requested === "zh"
    ? requested
    : saved === "en" || saved === "zh"
      ? saved
      : (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";

  const text = (zh, en) => language === "en" ? en : zh;
  window.VibeSMSI18n = { language, isEnglish: language === "en", text };
  document.documentElement.lang = language === "en" ? "en" : "zh-CN";

  const translateNode = (node) => {
    if (language !== "en" || !node.nodeValue) return;
    const value = node.nodeValue;
    const trimmed = value.trim();
    const translated = translations[trimmed];
    if (!translated) return;
    const leading = value.match(/^\s*/)?.[0] || "";
    const trailing = value.match(/\s*$/)?.[0] || "";
    node.nodeValue = `${leading}${translated}${trailing}`;
  };

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "CODE", "PRE"].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
      return node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(translateNode);

  if (language === "en") {
    document.querySelectorAll(".keep-together").forEach((element) => {
      if (element.nextElementSibling?.classList.contains("keep-together")) {
        element.append(document.createTextNode(" "));
      }
    });
    document.querySelectorAll("[placeholder]").forEach((element) => {
      const translated = translations[element.getAttribute("placeholder")];
      if (translated) element.setAttribute("placeholder", translated);
    });
    document.querySelectorAll("[aria-label]").forEach((element) => {
      const translated = translations[element.getAttribute("aria-label")];
      if (translated) element.setAttribute("aria-label", translated);
    });
  }

  const meta = pageMeta[normalizePath()]?.[language];
  if (meta) {
    document.title = meta[0];
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = meta[1];
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", meta[0]);
    document.querySelector('meta[property="og:description"]')?.setAttribute("content", meta[1]);
  }

  const switcher = document.createElement("div");
  switcher.className = "locale-switch";
  switcher.setAttribute("role", "group");
  switcher.setAttribute("aria-label", language === "en" ? "Language" : "语言");
  [["zh", "中"], ["en", "EN"]].forEach(([locale, label]) => {
    const link = document.createElement("a");
    const url = new URL(window.location.href);
    url.searchParams.set("lang", locale);
    if (normalizePath() === "/inbox/" && new URLSearchParams(url.hash.slice(1)).has("key")) {
      url.hash = "";
    }
    link.href = `${url.pathname}${url.search}${url.hash}`;
    link.textContent = label;
    link.lang = locale === "zh" ? "zh-CN" : "en";
    link.setAttribute("aria-label", locale === "zh" ? "切换到中文" : "Switch to English");
    if (locale === language) link.setAttribute("aria-current", "true");
    link.addEventListener("click", () => {
      try { window.localStorage.setItem(STORAGE_KEY, locale); } catch (_) { /* storage may be unavailable */ }
    });
    switcher.append(link);
  });
  document.querySelector(".topbar")?.append(switcher);

  document.querySelectorAll('a[href^="/"]').forEach((link) => {
    if (link.closest(".locale-switch") || language !== "en") return;
    const url = new URL(link.href, window.location.origin);
    if (url.origin !== window.location.origin || url.pathname.startsWith("/admin")) return;
    url.searchParams.set("lang", "en");
    link.href = `${url.pathname}${url.search}${url.hash}`;
  });
})();
