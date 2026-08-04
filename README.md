# SMS Gateway MVP

把一台双卡 Android 手机作为短信与来电边缘终端，将事件可靠上传到自部署服务，并在本地管理页面集中查看。

## 当前范围

- Android 端：首轮复用开源 SmsForwarder，采集入站短信和来电事件。
- 服务端：Python 标准库 + SQLite，无第三方运行依赖。
- 能力：上传鉴权、事件去重、设备 Last Seen、短信/来电查询、响应式管理页面。
- 暂不包含：主动发短信、远程接听、断网恢复自动补发、MDM、集群调度和高可用。

## 本地启动

```bash
mkdir -p config data
cp .env.example config/local.env
# 修改 config/local.env 中的 GATEWAY_TOKEN，并把 DB 路径改成 data/gateway.db
./bin/run-server
```

打开 <http://127.0.0.1:8787>。服务健康检查：

```bash
curl http://127.0.0.1:8787/api/health
```

已通过 USB 连接手机时，再执行：

```bash
./bin/connect-usb-device
```

手机端详细配置见 [docs/SMSFORWARDER_SETUP.md](docs/SMSFORWARDER_SETUP.md)。
当前真机验收状态见 [docs/REAL_DEVICE_ACCEPTANCE.md](docs/REAL_DEVICE_ACCEPTANCE.md)。

## Docker 部署

```bash
cp .env.example .env
# 设置强随机 GATEWAY_TOKEN
docker compose up -d --build
```

公网部署必须在前面增加 HTTPS 反向代理，并限制管理页面访问来源。

当前管理查询接口没有单独的登录层；公网使用时必须由反向代理增加认证，不能直接暴露 `8787` 端口。

## API

- `POST /api/v1/events`：Android 事件入口，需要 `X-Gateway-Token`。
- `POST /api/v1/devices/heartbeat`：设备心跳入口，需要 `X-Gateway-Token`。
- `GET /api/v1/events`：事件列表，可使用 `type`、`device_id`、`limit` 过滤。
- `GET /api/v1/devices`：设备状态。
- `GET /api/health`：健康检查和统计。

## 测试

```bash
python3 -m unittest -v
```
