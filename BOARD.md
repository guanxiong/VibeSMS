# SMS Gateway MVP Board

## Active

| Task ID | Priority | Task | Assignee | Session ID | Status |
| --- | --- | --- | --- | --- | --- |
| MVP-001 | Critical | 实现单台双卡 Android 的短信与来电事件采集、上传、持久化和管理页面 | Codex | root-20260804-mvp1 | IN PROGRESS |
| MVP-002 | High | 在已连接的华为 SEA-AL10 上安装并完成端到端验收 | Unassigned | - | PENDING |
| MVP-003 | Medium | 补充断网重试、设备心跳、双卡标识与部署文档 | Unassigned | - | PENDING |

## MVP-001 Acceptance Criteria

- Android 10 真机可安装并完成短信、电话、网络与通知权限配置。
- 收到短信后，将发送方、正文、接收时间、SIM 槽位和设备 ID 上传到自部署服务。
- 来电振铃、接通或结束事件可上传；无法可靠取得号码时允许标记为 unknown。
- 服务端持久化事件，重复上传不会生成重复记录。
- 浏览器可查看设备状态、短信和来电事件。
- 手机离线时事件保存在本地，恢复联网后自动重试。

## Review Notes

- 2026-08-04：首轮目标锁定为单机双卡、入站短信和来电事件；集群调度、远程发短信、MDM 和 HA 延后。
