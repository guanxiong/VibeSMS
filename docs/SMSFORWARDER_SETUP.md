# SmsForwarder MVP 配置

首轮使用 SmsForwarder 3.5.0 作为 Android 边缘采集端。它负责读取短信和来电广播，MVP 服务负责鉴权、去重、持久化与管理页面。

## 1. 手机侧基础设置

1. 安装项目 `artifacts/` 中的 arm64 APK。
2. 授予短信、电话、通话记录、联系人、通知和后台运行权限。
3. 在系统设置中允许自启动，并将电池策略改为“不允许休眠/手动管理”。
4. 在 SmsForwarder 设置中填写设备标记 `SEA-AL10-01`、SIM1 `中国联通`、SIM2 `中国移动`。

## 2. Webhook 发送通道

新建 Webhook 发送通道：

- 名称：`SMS MVP`
- 启用：是
- 方法：`POST`
- Web Server：`http://127.0.0.1:8787/api/v1/events`
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

关闭短信指令、远程控制服务端和不需要的 APP 通知转发，保持最小权限面。

## 4. USB 联调

手机连接 ADB 时执行：

```bash
./bin/connect-usb-device
```

USB 断开后 `adb reverse` 会失效。正式部署时将 Web Server 改为服务器的 HTTPS 公网地址。

