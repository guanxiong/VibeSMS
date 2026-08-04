# SMS Gateway MVP Board

## Active

| Task ID | Priority | Task | Assignee | Session ID | Status |
| --- | --- | --- | --- | --- | --- |
| MVP-001 | Critical | 实现单台双卡 Android 的短信与来电事件采集、上传、持久化和管理页面 | Codex | root-20260804-mvp1 | APPROVED |
| MVP-002 | High | 使用运营商真实短信和来电完成最终端到端验收 | User + Codex | root-20260804-mvp1 | APPROVED |
| MVP-003 | Medium | 补充断网恢复后的自动补发、主动设备心跳、设备独立密钥、管理端认证与 HTTPS 公网部署 | Codex | root-20260804-mvp3 | IN PROGRESS |

## MVP-001 Acceptance Criteria

- Android 10 真机可安装并完成短信、电话、网络与通知权限配置。
- 收到短信后，将发送方、正文、接收时间、SIM 槽位和设备 ID 上传到自部署服务。
- 来电振铃、接通或结束事件可上传；无法可靠取得号码时允许标记为 unknown。
- 服务端持久化事件，重复上传不会生成重复记录。
- 浏览器可查看设备状态、短信和来电事件。
- 请求失败时 Android 端执行有限次数重试；断网恢复后的自动补发在 MVP-003 完成。

## Review Notes

- 2026-08-04：首轮目标锁定为单机双卡、入站短信和来电事件；集群调度、远程发短信、MDM 和 HA 延后。
- 2026-08-04：SEA-AL10 已安装 SmsForwarder 3.5.0，短信/来电开关、双卡标识、Webhook 和全量规则配置完成。
- 2026-08-04：规则级模拟验收已覆盖短信 SIM1/SIM2 与来电 SIM1/SIM2，4 条事件均成功入库；等待运营商真实短信与真实来电做最终验收。
- 2026-08-04：Android 请求重试设置为最多 3 次、递增间隔从 1 秒开始、单次超时 10 秒；应用会保留失败日志，但断网恢复自动补发仍需后续实现。
- 2026-08-04：运营商真实来电产生来电过程与结束事件，发送方和设备标记完整；结束事件正确关联 SIM1。
- 2026-08-04：运营商真实短信已识别为 `sms`，正文、发送方、接收时间、设备标记、SIM1 和订阅 ID 均完整。
- 2026-08-04：质量门禁复核通过：5 项服务端自动化测试、Python 编译检查、前端 JavaScript 语法检查和 Git diff 检查均通过。当前环境未安装 `quality-gate-auditor` skill，使用上述可重复检查作为人工审核依据。
