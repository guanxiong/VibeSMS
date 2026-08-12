# 生产部署与多设备接入

## 当前生产实例

- 域名：`https://sms.shareapi.ai`
- 主机：Obsidian Infra 中的 `us`（DediOne LAX，`5.253.38.114`）
- 应用目录：`/opt/sms-gateway`
- 容器：`sms-gateway`，仅绑定 `127.0.0.1:8787`
- 反向代理：现有 1Panel OpenResty，配置 `/opt/1panel/www/conf.d/sms.shareapi.ai.conf`
- 证书：acme.sh + Namecheap DNS-01，自动续期并 reload OpenResty
- 数据：`/opt/sms-gateway/data/gateway.db`
- 备份：每天 UTC 03:17 生成 SQLite 在线备份，保留 30 天
- 当前版本：`0.9.2`，公开页面已支持中英文切换与语言持久化，并完成中英文标题断词、字号和移动端换行加固；“把你的号码”等语义短语保持整体换行。同时启用首页弹框自动签发、人工激活码兜底、用户 Key 收件箱、Agent USB 自动配置、Android 绑定和 Agent Inbox/OTP API；Android Terminal APK 为 v0.4.9

常用操作：

```bash
ssh us 'cd /opt/sms-gateway && docker compose -f deploy/compose.openresty.yaml ps'
ssh us 'cd /opt/sms-gateway && docker compose -f deploy/compose.openresty.yaml logs --tail 100'
ssh us '/opt/sms-gateway/deploy/backup.sh'
curl https://sms.shareapi.ai/api/health
```

Android Terminal 下载：

- APK：<https://github.com/guanxiong/VibeSMS/releases/download/v0.4.9/VibeSMS-0.4.9.apk>
- Release 与校验值：<https://github.com/guanxiong/VibeSMS/releases/tag/v0.4.9>
- SHA-256：`1bdf1bf4a81120729124d5228c1ca4d09b6149f9f233e6b1472695965da19f36`

发布私钥只保存在维护者机器。GitHub Actions 负责编译未签名 Release Candidate，本地使用官方 `apksigner` 完成签名后再上传 GitHub Release。

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

## 用户 Key 与 Agent 接入

打开 `https://sms.shareapi.ai/admin/`，在“号码与用户 Key”中填写手机号并签发。可选择预绑定已有设备与 SIM，也可留空等待 VibeSMS Terminal 首次绑定。Key 明文只显示一次，应立即保存到用户的 Agent Secret。

用户可打开 `https://sms.shareapi.ai/inbox/`，使用自己的 Key 查看该 Key 对应号码的终端状态、短信与来电。Android 端可使用 `https://sms.shareapi.ai/inbox/#key=...` 直接跳转；URL 片段不会随 HTTP 请求发送，页面读取后立即清除，并仅在当前浏览器标签页的 `sessionStorage` 中保存。Key 不会获得管理员权限，也不能读取其他 Key 的事件。

管理端支持轮换、禁用和解绑；服务端数据库只保存 Key 的 SHA-256 哈希。Agent 将 Key 配置为 `VIBESMS_KEY`，使用仓库中的 `skills/vibesms/` 查询终端状态、读取 Inbox 或等待验证码。

新终端可通过已授权 ADB 自动接入。手机解锁、连接 USB 并确认 SIM 卡槽后运行：

```bash
python3 skills/vibesms/scripts/setup_android.py --sim-slot 1
```

脚本会校验 GitHub Release 的 SHA-256、安装 APK、授予运行权限、换取设备凭据并等待 Key-scoped `status` 返回 `bound=true` 与 `online=true`。用户 Key 只从 `VIBESMS_KEY` Secret 读取，不写入 Prompt 或脚本日志；绑定后由 Android Keystore 加密保存，以支持本机显示和直接打开 Web 收件箱。

用户 Key 不能上传设备事件；首次绑定换取的设备 Token 不能读取 Inbox。一个启用中的手机号与一个设备 SIM 绑定最多各对应一个启用中的用户 Key。

## 无 USB 运行

开发环境可先把 Android Webhook 从 `http://127.0.0.1:8787` 改为同一局域网内服务器地址，例如：

```text
http://192.168.1.20:8787/api/v1/events
```

正式环境改为：

```text
https://sms.shareapi.ai/api/v1/events
```

心跳地址为 `https://sms.shareapi.ai/api/v1/devices/heartbeat`。

配置成功后移除 `adb reverse`，再次执行发送通道测试。收到 `SMS_MVP_OK` 即证明链路不再依赖 USB。

## Android 心跳与自动补发

VibeSMS Terminal 同时使用约 9 分钟一次的 `AlarmManager.setAndAllowWhileIdle` 锁屏心跳和 15 分钟 `JobScheduler` 兜底。锁屏心跳只在 HTTPS 请求期间持有最长 45 秒的 WakeLock；绑定页面会显示电池优化豁免状态，并提供“允许锁屏保活”入口。通过 ADB 自动配置时，脚本会尝试把应用加入设备 Doze allowlist。

华为等厂商系统还需要人工放行厂商级后台策略：进入“设置 → 应用 → 应用启动管理 → VibeSMS”，关闭“自动管理”，并打开“允许自启动、允许关联启动、允许后台活动”。同时将电池优化设为“不允许优化”；再进入“设置 → 电池 → 更多电池设置”，开启“休眠时始终保持网络连接”。菜单名称可能因 EMUI 版本略有不同；固定终端保持供电更稳定。

从 Android Terminal 0.4.9 起，华为设备会显示锁屏保活检查卡片：电池优化状态由 APK 自动检测；应用启动管理与休眠联网设置提供系统页跳转并由用户手动确认。如果连续超过 20 分钟没有成功心跳，卡片会提示重新检查这两项厂商设置。

SmsForwarder 3.5.0 可用“自动任务”组合实现可靠性补强：

1. 新增 `SMS Heartbeat` Webhook 通道，URL 为 `/api/v1/devices/heartbeat`，使用同一台设备自己的 Token。
2. 请求体至少包含 `device_id`，建议同时上报版本、电量和网络。
3. 新增每 15 分钟执行的定时任务。
4. 第一个动作选择“重发”，扫描最近 24 小时的失败日志。
5. 第二个动作选择“转发通知”，通过 `SMS Heartbeat` 通道发送心跳。

长时间断网期间，原始短信和来电保留在 SmsForwarder 本地数据库；网络恢复后，下一个 15 分钟任务会重试失败日志。服务端使用事件幂等 ID 去重，因此重复补发不会生成重复记录。
