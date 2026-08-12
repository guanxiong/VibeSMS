const STORAGE_KEY = "vibesms.inbox.key";
const state = { key: "", type: "", refreshTimer: null };

const loginView = document.querySelector("#login-view");
const inboxView = document.querySelector("#inbox-view");
const loginForm = document.querySelector("#login-form");
const keyInput = document.querySelector("#key-input");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");
const tr = (zh, en) => window.VibeSMSI18n?.text(zh, en) ?? zh;

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);

function consumeLinkedKey() {
  if (!window.location.hash) return "";
  const parameters = new URLSearchParams(window.location.hash.slice(1));
  const key = (parameters.get("key") || "").trim();
  if (parameters.has("key")) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  return key.startsWith("vbs_live_") ? key : "";
}

function formatTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? escapeHtml(value)
    : parsed.toLocaleString(window.VibeSMSI18n?.isEnglish ? "en-US" : "zh-CN", { hour12: false, timeZoneName: "short" });
}

function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 10) return tr("刚刚", "just now");
  if (seconds < 60) return tr(`${Math.floor(seconds)} 秒前`, `${Math.floor(seconds)}s ago`);
  if (seconds < 3600) return tr(`${Math.floor(seconds / 60)} 分钟前`, `${Math.floor(seconds / 60)}m ago`);
  if (seconds < 86400) return tr(`${Math.floor(seconds / 3600)} 小时前`, `${Math.floor(seconds / 3600)}h ago`);
  return tr(`${Math.floor(seconds / 86400)} 天前`, `${Math.floor(seconds / 86400)}d ago`);
}

function highlightOtp(value) {
  return escapeHtml(value).replace(/\b(\d{4,8})\b/g, "<mark>$1</mark>");
}

async function keyFetch(path, options = {}) {
  const headers = { Authorization: `Bearer ${state.key}`, ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
    headers
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(window.VibeSMSI18n?.isEnglish ? `Request failed (${response.status})` : (payload.error || `请求失败（${response.status}）`));
    error.status = response.status;
    throw error;
  }
  return payload;
}

function webhookFeedback(message = "", isError = false) {
  const feedback = document.querySelector("#webhook-feedback");
  feedback.textContent = message;
  feedback.classList.toggle("is-error", isError);
}

function renderWebhookDeliveries(deliveries = []) {
  const list = document.querySelector("#webhook-deliveries");
  if (!deliveries.length) {
    list.innerHTML = `<li class="delivery-empty">${tr("尚无命中关键词的投递记录。", "No keyword-matched deliveries yet.")}</li>`;
    return;
  }
  list.innerHTML = deliveries.map(delivery => {
    const failed = delivery.status === "failed";
    const statusLabel = delivery.status === "sent"
      ? tr("已发送", "SENT")
      : failed ? tr("待重试", "RETRY") : tr("等待中", "PENDING");
    const detail = failed
      ? `${tr("第", "Attempt ")}${delivery.attempts}${tr("次失败", " failed")} · ${escapeHtml(delivery.last_error || "")}`
      : `${escapeHtml(delivery.sender || tr("未知发送方", "Unknown sender"))} · ${tr("尝试", "attempts")} ${delivery.attempts}`;
    return `<li class="delivery-item">
      <span class="delivery-status ${failed ? "failed" : ""}">${statusLabel}</span>
      <span><strong>${detail}</strong></span>
      <time>${formatTime(delivery.sent_at || delivery.updated_at || delivery.created_at)}</time>
    </li>`;
  }).join("");
}

function renderWebhook(config) {
  const configured = Boolean(config.configured);
  const stateNode = document.querySelector("#webhook-state");
  stateNode.textContent = configured
    ? config.enabled ? tr("转发已启用", "Forwarding enabled") : tr("转发已暂停", "Forwarding paused")
    : tr("尚未配置", "Not configured");
  stateNode.classList.toggle("is-enabled", configured && config.enabled);
  document.querySelector("#webhook-keywords").value = configured ? (config.keywords || []).join("\n") : "验证码";
  document.querySelector("#webhook-enabled").checked = configured ? Boolean(config.enabled) : true;
  document.querySelector("#webhook-url").value = "";
  document.querySelector("#webhook-url").placeholder = configured
    ? tr(`已配置 ${config.webhook_hint || ""}；留空保持不变`, `Configured ${config.webhook_hint || ""}; leave blank to keep it`)
    : "https://open.feishu.cn/open-apis/bot/v2/hook/…";
  document.querySelector("#webhook-url-note").textContent = configured
    ? tr("已配置，留空保持原地址", "Configured; leave blank to keep it")
    : tr("首次配置必填", "Required for first setup");
  document.querySelector("#webhook-test").disabled = !configured;
  document.querySelector("#webhook-delete").disabled = !configured;
  renderWebhookDeliveries(config.deliveries || []);
}

async function loadWebhook() {
  try {
    const config = await keyFetch("/api/v1/webhooks/feishu");
    renderWebhook(config);
  } catch (error) {
    webhookFeedback(tr(`读取转发设置失败：${error.message}`, `Failed to load forwarding settings: ${error.message}`), true);
  }
}

function renderStatus(status) {
  document.querySelector("#phone-number").textContent = status.phone_number || "—";
  document.querySelector("#sim-slot").textContent = status.sim_slot ? `SIM ${status.sim_slot}` : tr("尚未绑定", "Not bound");
  document.querySelector("#cursor-value").textContent = String(status.cursor || 0);

  const lastSeen = status.device?.last_seen || status.device?.last_heartbeat || "";
  const lastOnline = document.querySelector("#last-online");
  if (lastSeen) {
    const elapsed = formatElapsed(Number(status.seconds_since_seen));
    lastOnline.textContent = elapsed ? `${formatTime(lastSeen)} · ${elapsed}` : formatTime(lastSeen);
    lastOnline.title = tr(`服务器最后收到该终端请求的时间：${formatTime(lastSeen)}`, `Last terminal request received by the server: ${formatTime(lastSeen)}`);
  } else {
    lastOnline.textContent = tr("暂无记录", "No record");
    lastOnline.removeAttribute("title");
  }

  const deviceState = document.querySelector("#device-state");
  const indicator = document.createElement("i");
  let label = tr("尚未绑定", "Not bound");
  let className = "is-offline";
  if (status.bound) {
    label = status.online ? tr("终端在线", "Terminal online") : tr("终端离线", "Terminal offline");
    className = status.online ? "is-online" : "is-offline";
  }
  deviceState.className = className;
  deviceState.replaceChildren(indicator, document.createTextNode(` ${label}`));

  const notice = document.querySelector("#inbox-notice");
  notice.hidden = status.bound;
  notice.textContent = status.bound
    ? ""
    : tr("这个 Key 还没有绑定 Android 终端。请在手机上安装 VibeSMS APK，输入同一个 Key 并选择实际 SIM 卡槽。", "This Key is not bound to an Android terminal yet. Install the VibeSMS APK, enter the same Key, and choose the physical SIM slot.");
}

function renderEvents(events) {
  const list = document.querySelector("#event-list");
  if (!events.length) {
    list.innerHTML = `<li class="event-empty">${tr("当前筛选下还没有消息。", "No events match this filter yet.")}</li>`;
    return;
  }
  list.innerHTML = events.map(event => {
    const isCall = event.event_type === "call";
    const isTest = event.event_type === "test";
    const content = isCall ? (event.call_type || event.content || tr("来电", "Incoming call")) : (event.content || "");
    const kindLabel = isCall ? tr("来电", "CALL") : (isTest ? tr("测试", "TEST") : tr("短信", "SMS"));
    return `
      <li class="event-item">
        <span class="event-kind ${isCall ? "call" : (isTest ? "test" : "sms")}">${kindLabel}</span>
        <div class="event-sender"><span>${tr("来源", "SOURCE")}</span><strong>${escapeHtml(event.sender || tr("未知", "Unknown"))}</strong></div>
        <div class="event-message"><span>${isCall ? tr("状态", "STATUS") : tr("内容", "CONTENT")}</span><p>${highlightOtp(content)}</p></div>
        <time class="event-time" datetime="${escapeHtml(event.received_at || "")}">${formatTime(event.received_at)}</time>
      </li>`;
  }).join("");
}

function showLogin(message = "") {
  if (state.refreshTimer) window.clearInterval(state.refreshTimer);
  state.refreshTimer = null;
  state.key = "";
  sessionStorage.removeItem(STORAGE_KEY);
  inboxView.hidden = true;
  loginView.hidden = false;
  loginError.textContent = message;
  keyInput.value = "";
  keyInput.focus();
}

function showInbox() {
  loginView.hidden = true;
  inboxView.hidden = false;
  state.refreshTimer = window.setInterval(refreshInbox, 15000);
}

async function refreshInbox() {
  const refreshLabel = document.querySelector("#refresh-label");
  const refreshButton = document.querySelector("#refresh-button");
  refreshButton.disabled = true;
  refreshLabel.textContent = tr("正在读取…", "Loading…");
  const type = state.type ? `&type=${encodeURIComponent(state.type)}` : "";
  try {
    const [status, inbox] = await Promise.all([
      keyFetch("/api/v1/status"),
      keyFetch(`/api/v1/inbox?limit=100&order=desc${type}`)
    ]);
    renderStatus(status);
    renderEvents(inbox.events || []);
    refreshLabel.textContent = tr(`刚刚更新 · ${formatTime(new Date().toISOString())}`, `Updated just now · ${formatTime(new Date().toISOString())}`);
  } catch (error) {
    if (error.status === 401) {
      showLogin(tr("Key 无效、已轮换或已被禁用，请检查后重试。", "The Key is invalid, rotated, or disabled. Check it and try again."));
      return;
    }
    refreshLabel.textContent = tr(`读取失败：${error.message}`, `Failed to load: ${error.message}`);
  } finally {
    refreshButton.disabled = false;
  }
}

async function authenticate(key) {
  state.key = key;
  loginButton.disabled = true;
  loginButton.textContent = tr("正在验证…", "Verifying…");
  loginError.textContent = "";
  try {
    const status = await keyFetch("/api/v1/status");
    sessionStorage.setItem(STORAGE_KEY, key);
    renderStatus(status);
    showInbox();
    await Promise.all([refreshInbox(), loadWebhook()]);
  } catch (error) {
    state.key = "";
    sessionStorage.removeItem(STORAGE_KEY);
    loginError.textContent = error.status === 401
      ? tr("Key 无效、已轮换或已被禁用，请检查后重试。", "The Key is invalid, rotated, or disabled. Check it and try again.")
      : tr(`暂时无法登录：${error.message}`, `Unable to sign in: ${error.message}`);
  } finally {
    loginButton.disabled = false;
    loginButton.innerHTML = `${tr("打开我的收件箱", "Open my inbox")} <span aria-hidden="true">→</span>`;
  }
}

loginForm.addEventListener("submit", event => {
  event.preventDefault();
  const key = keyInput.value.trim();
  if (key) authenticate(key);
});

document.querySelector("#logout-button").addEventListener("click", () => showLogin());
document.querySelector("#refresh-button").addEventListener("click", refreshInbox);
document.querySelector("#webhook-refresh").addEventListener("click", loadWebhook);
document.querySelector("#webhook-form").addEventListener("submit", async event => {
  event.preventDefault();
  const saveButton = document.querySelector("#webhook-save");
  saveButton.disabled = true;
  webhookFeedback(tr("正在保存…", "Saving…"));
  try {
    const config = await keyFetch("/api/v1/webhooks/feishu", {
      method: "POST",
      body: JSON.stringify({
        webhook_url: document.querySelector("#webhook-url").value.trim(),
        keywords: document.querySelector("#webhook-keywords").value,
        enabled: document.querySelector("#webhook-enabled").checked
      })
    });
    renderWebhook(config);
    webhookFeedback(tr("转发设置已保存。", "Forwarding settings saved."));
  } catch (error) {
    webhookFeedback(tr(`保存失败：${error.message}`, `Save failed: ${error.message}`), true);
  } finally {
    saveButton.disabled = false;
  }
});

document.querySelector("#webhook-test").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  webhookFeedback(tr("正在向飞书发送测试消息…", "Sending a test message to Feishu…"));
  try {
    await keyFetch("/api/v1/webhooks/feishu/test", { method: "POST", body: "{}" });
    webhookFeedback(tr("飞书已接收测试消息。", "Feishu received the test message."));
    await loadWebhook();
  } catch (error) {
    webhookFeedback(tr(`测试失败：${error.message}`, `Test failed: ${error.message}`), true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#webhook-delete").addEventListener("click", async event => {
  if (!window.confirm(tr("删除飞书 Webhook 配置和投递记录？", "Delete the Feishu webhook and delivery history?"))) return;
  const button = event.currentTarget;
  button.disabled = true;
  try {
    await keyFetch("/api/v1/webhooks/feishu/delete", { method: "POST", body: "{}" });
    renderWebhook({ configured: false, deliveries: [] });
    webhookFeedback(tr("飞书转发配置已删除。", "Feishu forwarding configuration deleted."));
  } catch (error) {
    webhookFeedback(tr(`删除失败：${error.message}`, `Delete failed: ${error.message}`), true);
    button.disabled = false;
  }
});
document.querySelectorAll(".filter").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".filter").forEach(candidate => {
    const active = candidate === button;
    candidate.classList.toggle("is-active", active);
    candidate.setAttribute("aria-pressed", String(active));
  });
  state.type = button.dataset.type || "";
  refreshInbox();
}));

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.key) refreshInbox();
});

const linkedKey = consumeLinkedKey();
const savedKey = sessionStorage.getItem(STORAGE_KEY);
if (linkedKey) authenticate(linkedKey);
else if (savedKey) authenticate(savedKey);
