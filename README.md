# VibeSMS

把 Android 手机变成 Agent 可调用的短信与来电终端。用户使用一个 Key 接入自己的 SIM，设备将事件可靠上传到 `sms.shareapi.ai`，Agent 再基于同一 Key 隔离读取。

当前版本已提供无账户 Key 接入、按号码与 SIM 隔离的 Agent Inbox/OTP API、VibeSMS Skill，以及带离线队列和主动心跳的专用 Android Terminal。产品定义见 [docs/VIBESMS_PRODUCT.md](docs/VIBESMS_PRODUCT.md)。

## 当前范围

- Android 端：VibeSMS Terminal 采集入站短信和来电事件，支持双卡、持久化离线队列、自动补发和主动心跳。
- 服务端：Python 标准库 + SQLite，无第三方运行依赖。
- 能力：用户 Key 签发/轮换/禁用、Android 首次绑定、设备独立上传密钥、Agent 隔离查询、OTP 长轮询、事件去重、主动心跳和响应式管理页面。
- 暂不包含：主动发短信、远程接听、MDM、集群调度和高可用。

## Android APK

VibeSMS Android Terminal v0.1.0 使用正式发布密钥签名，并通过 GitHub Releases 分发：

- [下载 VibeSMS-0.1.0.apk](https://github.com/guanxiong/VibeSMS/releases/latest/download/VibeSMS-0.1.0.apk)
- [版本说明与 SHA-256 校验值](https://github.com/guanxiong/VibeSMS/releases/latest)

安装后输入管理员签发的 Key、选择 SIM 并连接即可。Android 端不会保存用户 Key，只保存首次绑定后换取的设备上传凭据。

- 源码：[github.com/guanxiong/VibeSMS](https://github.com/guanxiong/VibeSMS)
- 云端入口：[sms.shareapi.ai](https://sms.shareapi.ai)

## 本地启动

```bash
mkdir -p config data
cp .env.example config/local.env
# 修改 config/local.env 中的 GATEWAY_TOKEN，并把 DB 路径改成 data/gateway.db
./bin/run-server
```

打开 <http://127.0.0.1:8787> 查看公开项目主页；管理控制台位于 <http://127.0.0.1:8787/admin/>，使用 `config/local.env` 中的管理员账号登录。服务健康检查：

```bash
curl http://127.0.0.1:8787/api/health
```

已通过 USB 连接手机时，再执行：

```bash
./bin/connect-usb-device
```

手机端详细配置见 [docs/SMSFORWARDER_SETUP.md](docs/SMSFORWARDER_SETUP.md)。
当前真机验收状态见 [docs/REAL_DEVICE_ACCEPTANCE.md](docs/REAL_DEVICE_ACCEPTANCE.md)。
生产 HTTPS 部署与新增设备见 [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)。

## Docker 部署

```bash
cp .env.example .env
# 设置强随机 GATEWAY_TOKEN
docker compose up -d --build
```

Compose 会使用 Caddy 自动提供 HTTPS，并且不直接暴露应用的 `8787` 端口。管理页面会弹出 Basic Auth 登录框。

## 仓库结构

```text
server/              HTTP API、SQLite 存储与 Web 资源
  static/site/       公开项目主页
  static/admin/      需认证的管理控制台
deploy/              HTTPS、反向代理、备份与 DNS 运维配置
android/             VibeSMS Terminal 原生 Android 工程
bin/                 本地启动、设备接入和凭据签发脚本
docs/                产品、部署、Android 配置与验收文档
tests/               服务端与访问边界自动化测试
skills/vibesms/      可安装的 VibeSMS Agent Skill 与零依赖客户端
```

运行时的 `config/local.env`、`data/` 与测试 APK 均被 Git 忽略，不进入公开仓库。

## API

- `POST /api/v1/events`：Android 事件入口，需要 `X-Gateway-Token`。
- `POST /api/v1/devices/heartbeat`：设备心跳入口，需要 `X-Gateway-Token`。
- `GET /api/v1/events`：事件列表，可使用 `type`、`device_id`、`limit` 过滤，需要管理员认证。
- `GET /api/v1/devices`：设备在线状态，需要管理员认证。
- `GET/POST /api/v1/admin/devices`：查看设备凭据元数据或生成独立 Token，需要管理员认证。
- `GET/POST /api/v1/admin/keys`：列出或签发用户 Key，需要管理员认证。
- `POST /api/v1/admin/keys/{key_id}/{rotate|disable|unbind}`：管理用户 Key，需要管理员认证。
- `POST /api/v1/bindings`：用户 Key 首次绑定设备与 SIM，返回仅显示一次的设备 Token。
- `GET /api/v1/status`：查询当前 Key 的终端状态与事件游标。
- `GET /api/v1/inbox`：按当前 Key 隔离读取短信与来电。
- `GET /api/v1/otp/wait`：等待当前 Key 对应号码的新验证码，最长 60 秒。
- `GET /api/health`：健康检查和统计。

## Agent Skill

使用开放 Agent Skills CLI 一键安装到 Codex、Claude Code、Cursor、GitHub Copilot、OpenCode 等客户端：

```bash
npx skills add guanxiong/VibeSMS --skill vibesms -g -y
```

也可以通过 GitHub CLI 的原生 Agent Skill 支持安装：

```bash
gh skill install guanxiong/VibeSMS
```

Skill 源码位于 [skills/vibesms](skills/vibesms)。安装后把用户 Key 保存为 `VIBESMS_KEY` Secret，再让 Agent 检查终端、读取短信/来电或等待验证码：

```bash
export VIBESMS_KEY='vbs_live_...'
python3 skills/vibesms/scripts/vibesms.py status
python3 skills/vibesms/scripts/vibesms.py wait-otp --after-id 0 --timeout 60
```

生产使用时先通过 `status` 捕获游标，再触发外部短信，最后用该游标等待验证码，避免误读旧消息。不要把 Key 写入提示词、代码或 Git。

- [GitHub Skill v1.0.0](https://github.com/guanxiong/VibeSMS/releases/tag/vibesms-skill-v1.0.0)
- [Skills.sh 仓库页](https://skills.sh/guanxiong/vibesms)
- [Agent Skills 开放规范](https://agentskills.io)

## 测试

```bash
python3 -m unittest -v
```

## License

本仓库目前公开可见，但尚未选择开源许可证。在许可证确定前，源码版权仍由作者保留，项目页因此使用 “Public Repository” 而非 “Open Source”。
