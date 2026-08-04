# SmsForwarder MVP 配置

首轮使用 SmsForwarder 3.5.0 作为 Android 边缘采集端。它负责读取短信和来电广播，MVP 服务负责鉴权、去重、持久化与管理页面。

## 1. 手机侧基础设置

1. 安装项目 `artifacts/` 中的 arm64 APK。
2. 授予短信、电话、通话记录、联系人、通知和后台运行权限。
3. 在系统设置中允许自启动，并将电池策略改为“不允许休眠/手动管理”。
4. 在 SmsForwarder 设置中填写唯一设备标记，例如 `SEA-AL10-01`，然后点击 SIM1/SIM2 的“刷新”自动获取订阅 ID 和运营商标识。
5. 将“请求重试机制”设置为最多 3 次、递增间隔 1 秒、单次超时 10 秒。

## 2. Webhook 发送通道

新建 Webhook 发送通道：

- 名称：`SMS MVP`
- 启用：是
- 方法：`POST`
- Web Server：USB 联调使用 `http://127.0.0.1:8787/api/v1/events`；长期运行使用局域网或 HTTPS 服务器地址
- 响应关键字：`SMS_MVP_OK`
- Header `Content-Type`：`application/json`
- Header `X-Gateway-Token`：读取 `config/local.env` 中的 `GATEWAY_TOKEN`
- 请求体：

```json
{
  "device_id": "{{DEVICE_NAME}}",
  "sender": "{{FROM}}",
  "content": "{{SMS}}",
  "received_at": "{{RECEIVE_TIME}}",
  "sim": "{{CARD_SLOT}}",
  "sub_id": "{{CARD_SUBID}}",
  "call_type": "{{CALL_TYPE}}",
  "app_version": "{{APP_VERSION}}",
  "battery": "{{BATTERY_INFO_SIMPLE}}",
  "network": "{{NET_TYPE}}",
  "client_timestamp": "[timestamp]"
}
```

保存后点击“测试”。管理页面应立即出现一条测试短信。

## 3. 转发规则

创建两条启用规则，并将发送通道设为 `SMS MVP`：

- 所有收到的短信。
- 来电提醒、来电接通、来电挂机和未接来电。

两条规则均选择“不限卡槽”和“全部”，即可同时覆盖 SIM1 与 SIM2。

SmsForwarder 3.5.0 的“短信规则测试”存在一个仅限测试界面的差异：它会把默认通话类型一并传给 Webhook，因此服务端可能把该模拟记录显示为来电。真实短信广播的通话类型为 `0/未知通话`，会正常归类为短信。最终验收应再使用运营商真实短信确认。

关闭短信指令、远程控制服务端和不需要的 APP 通知转发，保持最小权限面。

## 4. USB 联调

手机连接 ADB 时执行：

```bash
./bin/connect-usb-device
```

USB 断开后 `adb reverse` 会失效。正式部署时将 Web Server 改为服务器的 HTTPS 公网地址。

## 5. 心跳与断网补发

SmsForwarder 的 Webhook 支持请求内有限次数重试，并在本机保存转发日志。再创建一条每 15 分钟运行的自动任务：

1. “重发消息”动作：最近 24 小时、状态为失败。
2. “推送通知”动作：使用指向 `/api/v1/devices/heartbeat` 的 `SMS Heartbeat` 通道。

这样网络恢复后最迟约 15 分钟会扫描并补发失败记录。服务端事件 ID 具有幂等性，重复补发不会重复入库。

当前 SEA-AL10 的后台任务已在无人操作时按计划触发；手机可仅通过 Wi-Fi 上传，不再依赖 `adb reverse`。USB 数据连接可以关闭或直接拔线。
