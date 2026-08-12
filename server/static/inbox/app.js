const STORAGE_KEY = "vibesms.inbox.key";
const state = { key: "", type: "", refreshTimer: null };

const loginView = document.querySelector("#login-view");
const inboxView = document.querySelector("#inbox-view");
const loginForm = document.querySelector("#login-form");
const keyInput = document.querySelector("#key-input");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");

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
    : parsed.toLocaleString("zh-CN", { hour12: false, timeZoneName: "short" });
}

function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 10) return "刚刚";
  if (seconds < 60) return `${Math.floor(seconds)} 秒前`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  return `${Math.floor(seconds / 86400)} 天前`;
}

function highlightOtp(value) {
  return escapeHtml(value).replace(/\b(\d{4,8})\b/g, "<mark>$1</mark>");
}

async function keyFetch(path) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${state.key}` }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || `请求失败（${response.status}）`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function renderStatus(status) {
  document.querySelector("#phone-number").textContent = status.phone_number || "—";
  document.querySelector("#sim-slot").textContent = status.sim_slot ? `SIM ${status.sim_slot}` : "尚未绑定";
  document.querySelector("#cursor-value").textContent = String(status.cursor || 0);

  const lastSeen = status.device?.last_seen || status.device?.last_heartbeat || "";
  const lastOnline = document.querySelector("#last-online");
  if (lastSeen) {
    const elapsed = formatElapsed(Number(status.seconds_since_seen));
    lastOnline.textContent = elapsed ? `${formatTime(lastSeen)} · ${elapsed}` : formatTime(lastSeen);
    lastOnline.title = `服务器最后收到该终端请求的时间：${formatTime(lastSeen)}`;
  } else {
    lastOnline.textContent = "暂无记录";
    lastOnline.removeAttribute("title");
  }

  const deviceState = document.querySelector("#device-state");
  const indicator = document.createElement("i");
  let label = "尚未绑定";
  let className = "is-offline";
  if (status.bound) {
    label = status.online ? "终端在线" : "终端离线";
    className = status.online ? "is-online" : "is-offline";
  }
  deviceState.className = className;
  deviceState.replaceChildren(indicator, document.createTextNode(` ${label}`));

  const notice = document.querySelector("#inbox-notice");
  notice.hidden = status.bound;
  notice.textContent = status.bound
    ? ""
    : "这个 Key 还没有绑定 Android 终端。请在手机上安装 VibeSMS APK，输入同一个 Key 并选择实际 SIM 卡槽。";
}

function renderEvents(events) {
  const list = document.querySelector("#event-list");
  if (!events.length) {
    list.innerHTML = '<li class="event-empty">当前筛选下还没有消息。</li>';
    return;
  }
  list.innerHTML = events.map(event => {
    const isCall = event.event_type === "call";
    const isTest = event.event_type === "test";
    const content = isCall ? (event.call_type || event.content || "来电") : (event.content || "");
    const kindLabel = isCall ? "来电" : (isTest ? "测试" : "短信");
    return `
      <li class="event-item">
        <span class="event-kind ${isCall ? "call" : (isTest ? "test" : "sms")}">${kindLabel}</span>
        <div class="event-sender"><span>来源</span><strong>${escapeHtml(event.sender || "未知")}</strong></div>
        <div class="event-message"><span>${isCall ? "状态" : "内容"}</span><p>${highlightOtp(content)}</p></div>
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
  refreshLabel.textContent = "正在读取…";
  const type = state.type ? `&type=${encodeURIComponent(state.type)}` : "";
  try {
    const [status, inbox] = await Promise.all([
      keyFetch("/api/v1/status"),
      keyFetch(`/api/v1/inbox?limit=100&order=desc${type}`)
    ]);
    renderStatus(status);
    renderEvents(inbox.events || []);
    refreshLabel.textContent = `刚刚更新 · ${formatTime(new Date().toISOString())}`;
  } catch (error) {
    if (error.status === 401) {
      showLogin("Key 无效、已轮换或已被禁用，请检查后重试。");
      return;
    }
    refreshLabel.textContent = `读取失败：${error.message}`;
  } finally {
    refreshButton.disabled = false;
  }
}

async function authenticate(key) {
  state.key = key;
  loginButton.disabled = true;
  loginButton.textContent = "正在验证…";
  loginError.textContent = "";
  try {
    const status = await keyFetch("/api/v1/status");
    sessionStorage.setItem(STORAGE_KEY, key);
    renderStatus(status);
    showInbox();
    await refreshInbox();
  } catch (error) {
    state.key = "";
    sessionStorage.removeItem(STORAGE_KEY);
    loginError.textContent = error.status === 401
      ? "Key 无效、已轮换或已被禁用，请检查后重试。"
      : `暂时无法登录：${error.message}`;
  } finally {
    loginButton.disabled = false;
    loginButton.innerHTML = '打开我的收件箱 <span aria-hidden="true">→</span>';
  }
}

loginForm.addEventListener("submit", event => {
  event.preventDefault();
  const key = keyInput.value.trim();
  if (key) authenticate(key);
});

document.querySelector("#logout-button").addEventListener("click", () => showLogin());
document.querySelector("#refresh-button").addEventListener("click", refreshInbox);
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
