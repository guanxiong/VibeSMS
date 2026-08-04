# 生产部署与多设备接入

## HTTPS 部署

准备一台具有公网 IP 的 Linux 主机，并将域名的 A/AAAA 记录指向该主机。开放 TCP 80、TCP 443 和 UDP 443，然后执行：

```bash
cp .env.example .env
# 填写域名、ACME 邮箱、管理员密码、首台设备 ID 和设备 Token
docker compose up -d --build
```

Caddy 会自动申请和续期 HTTPS 证书，应用容器的 `8787` 端口不会直接发布到公网。管理页和查询 API 使用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 的 HTTP Basic Auth；Android 上传仍使用设备独立 Token。

公网部署前必须确认：

- `SMS_GATEWAY_DOMAIN` 是真实域名，不是 IP 地址。
- DNS 已生效，80/443 未被其他服务占用。
- `ADMIN_PASSWORD` 与设备 Token 均为独立强随机值。
- 仅通过 `https://域名` 访问，不额外暴露 `8787`。
- 定期备份 Docker volume `sms-gateway-data`。

## 设备独立密钥

首台设备由 `SMS_GATEWAY_BOOTSTRAP_DEVICE_ID` 和 `GATEWAY_TOKEN` 自动迁移。新增或轮换设备密钥：

```bash
SMS_GATEWAY_ADMIN_URL=https://sms.example.com ./bin/provision-device PIXEL-02 "备用终端"
```

返回的 `token` 只显示一次。把它配置到对应 Android 设备的 `X-Gateway-Token` Header，不要复用到其他手机；再次执行同一设备 ID 会轮换旧密钥。

## 无 USB 运行

开发环境可先把 Android Webhook 从 `http://127.0.0.1:8787` 改为同一局域网内服务器地址，例如：

```text
http://192.168.1.20:8787/api/v1/events
```

正式环境改为：

```text
https://sms.example.com/api/v1/events
```

配置成功后移除 `adb reverse`，再次执行发送通道测试。收到 `SMS_MVP_OK` 即证明链路不再依赖 USB。

## Android 心跳与自动补发

SmsForwarder 3.5.0 可用“自动任务”组合实现可靠性补强：

1. 新增 `SMS Heartbeat` Webhook 通道，URL 为 `/api/v1/devices/heartbeat`，使用同一台设备自己的 Token。
2. 请求体至少包含 `device_id`，建议同时上报版本、电量和网络。
3. 新增每 15 分钟执行的定时任务。
4. 第一个动作选择“重发”，扫描最近 24 小时的失败日志。
5. 第二个动作选择“转发通知”，通过 `SMS Heartbeat` 通道发送心跳。

长时间断网期间，原始短信和来电保留在 SmsForwarder 本地数据库；网络恢复后，下一个 15 分钟任务会重试失败日志。服务端使用事件幂等 ID 去重，因此重复补发不会生成重复记录。
