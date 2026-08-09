# SEA-AL10 真机验收记录

日期：2026-08-04  
设备：Huawei SEA-AL10，Android 10，双卡双待  
Android 端：SmsForwarder 3.5.0  
设备标记：`SEA-AL10-01`

## VibeSMS Terminal v0.2.0 切换状态

v0.2.0 增加了经 ADB 授权的自动安装、权限授予、SIM 绑定和云端在线验证。当前手机尚未重新连接；签名 APK 发布后，使用 `skills/vibesms/scripts/setup_android.py` 执行下列真机验收。本页后续记录的是 SmsForwarder 3.5.0 的既有验收结果。

下次连接手机后改装 VibeSMS Terminal，并补做：ADB 自动配置、APK 签名安装、运行时权限、双卡枚举、Key 首次绑定、脱离 USB 的短信/来电上传、断网恢复补发、15 分钟心跳和重启自启动。通过后再将 MVP-003 与 MVP-004 标记为最终 APPROVED。

## 已完成

- APK 校验、安装并授予短信、电话、通话记录、联系人和后台运行权限。
- 开启短信转发，以及来电提醒、来电接通、来电挂机和未接来电转发。
- 自动识别两张 SIM 的订阅 ID；仓库和文档不记录手机号。
- 建立 ADB reverse：手机 `127.0.0.1:8787` 到开发机 `127.0.0.1:8787`。
- 配置带 `X-Gateway-Token` 的 Webhook，并通过发送通道连通测试。
- 创建 `All SMS` 和 `All Calls` 两条不限卡槽的全量规则。
- 使用规则测试覆盖 SMS SIM1、SMS SIM2、Call SIM1、Call SIM2，服务端均成功入库，槽位与订阅 ID 对应正确。
- 请求重试设置为最多 3 次、递增间隔从 1 秒开始、单次超时 10 秒。
- 管理端已启用独立 Basic Auth；设备 Token 仅绑定 `SEA-AL10-01`。
- `SMS MVP` 已切换为局域网 Webhook；移除 `adb reverse` 后通道测试仍成功。
- `SMS Heartbeat` 通道已成功更新服务端心跳，未产生伪短信事件。
- `Gateway Reliability` 自动任务已启用：每 15 分钟重发最近 24 小时失败记录并发送心跳。
- 无人操作手机时，定时任务在 2026-08-04 15:59:59（Asia/Shanghai）自动更新心跳，证明后台调度已生效。

## 运营商真实信号验收

- [x] 真实短信：服务端识别为 `sms`，发送方、正文、接收时间、设备标记、SIM1 和订阅 ID 完整。
- [x] 真实来电：服务端收到来电过程与结束事件，发送方和设备标记完整；结束事件正确关联 SIM1。
- [x] 管理页面可查看上述事件，上传链路在 30 秒验收窗口内完成。

结论：单机双卡 MVP 于 2026-08-04 验收通过。

来电刚开始时 Android 可能暂时无法提供 SIM 槽位，后续结束事件会补充槽位信息；服务端允许该阶段字段为空。

## 公网 HTTPS 切换待办

`sms.shareapi.ai` 已于 2026-08-08 部署完成，DNS、Let’s Encrypt 证书、OpenResty、管理员认证、设备 Token 和公网访问均已验收。按用户安排，手机端切换延后到设备再次连接并解锁时执行。

下次连接手机后：

1. 把 `SMS MVP` 的 Webhook 改为 `https://sms.shareapi.ai/api/v1/events`。
2. 把 `SMS Heartbeat` 的 Webhook 改为 `https://sms.shareapi.ai/api/v1/devices/heartbeat`。
3. 保持原有 `X-Gateway-Token`、请求体和响应关键字不变。
4. 分别执行两个通道测试，确认返回 `SMS_MVP_OK`。
5. 关闭 ADB 后再次测试事件上传，并等待一轮 15 分钟自动心跳。
6. 用一条真实短信或来电完成公网端到端验收后，将 MVP-003 提交审核。

## 已知边界

- 规则测试页的短信模拟会错误携带默认通话类型，真实短信广播不受影响。
- 当前手机仍使用原局域网 HTTP 地址；在切换到正式 HTTPS 域名前，只能在原局域网环境上传。
- 公网服务已上线，但手机端尚未切换，因此暂不能把公网服务器在线状态当作真机公网链路已验收。
- SmsForwarder 的定时任务受 Android 后台调度影响，网络恢复补发目标是 15 分钟级而非实时消息队列 SLA。
