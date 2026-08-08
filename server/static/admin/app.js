const state = { type: "", stats: { sms: 0, call: 0 } };

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[char]);

const formatTime = value => {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? escapeHtml(value) : parsed.toLocaleString("zh-CN", { hour12: false });
};

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `${response.status} ${response.statusText}`);
  return result;
}

function showKeySecret(value, label) {
  const secret = document.querySelector("#key-secret");
  document.querySelector("#key-secret-label").textContent = label;
  document.querySelector("#key-secret-value").textContent = value;
  document.querySelector("#copy-key").textContent = "复制 Key";
  secret.hidden = false;
  secret.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderKeys(keys) {
  const container = document.querySelector("#keys");
  document.querySelector("#key-count").textContent = keys.filter(key => key.enabled).length;
  if (!keys.length) {
    container.innerHTML = '<p class="empty">尚未签发用户 Key</p>';
    return;
  }
  container.innerHTML = keys.map(key => `
    <article class="key-card ${key.enabled ? "" : "is-disabled"}">
      <div class="key-card-head">
        <div><strong>${escapeHtml(key.phone_number)}</strong><span>${escapeHtml(key.label || key.key_id)}</span></div>
        <span class="key-state">${key.enabled ? "ACTIVE" : "DISABLED"}</span>
      </div>
      <dl>
        <div><dt>Key ID</dt><dd class="mono">${escapeHtml(key.key_id)}</dd></div>
        <div><dt>Owner</dt><dd>${escapeHtml(key.owner_ref || "—")}</dd></div>
        <div><dt>绑定</dt><dd>${key.device_id ? `${escapeHtml(key.device_id)} · SIM${key.sim_slot}` : "等待 APK 绑定"}</dd></div>
        <div><dt>最后使用</dt><dd>${formatTime(key.last_accessed)}</dd></div>
      </dl>
      <div class="key-actions">
        <button type="button" data-key-action="rotate" data-key-id="${escapeHtml(key.key_id)}">轮换</button>
        ${key.device_id ? `<button type="button" data-key-action="unbind" data-key-id="${escapeHtml(key.key_id)}">解绑</button>` : ""}
        ${key.enabled ? `<button class="danger" type="button" data-key-action="disable" data-key-id="${escapeHtml(key.key_id)}">禁用</button>` : ""}
      </div>
    </article>`).join("");
}

function renderDevices(devices) {
  const container = document.querySelector("#devices");
  document.querySelector("#device-count").textContent = devices.length;
  document.querySelector("#online-count").textContent = devices.filter(device => device.online).length;
  if (!devices.length) {
    container.innerHTML = '<p class="empty">等待终端上报…</p>';
    return;
  }
  container.innerHTML = devices.map(device => `
    <article class="device-card">
      <div class="device-head"><strong>${escapeHtml(device.device_id)}</strong><span class="device-state ${device.online ? "is-online" : "is-offline"}">${device.online ? "在线" : "离线"}</span></div>
      <dl>
        <div><dt>最后在线</dt><dd>${formatTime(device.last_seen)}</dd></div>
        <div><dt>最后心跳</dt><dd>${formatTime(device.last_heartbeat)}</dd></div>
        <div><dt>SIM</dt><dd>${device.sim_slot ? `SIM${device.sim_slot}` : "—"} ${escapeHtml(device.sim_label)}</dd></div>
        <div><dt>电量</dt><dd>${escapeHtml(device.battery || "—")}</dd></div>
        <div><dt>网络</dt><dd>${escapeHtml(device.network_type || "—")}</dd></div>
        <div><dt>App</dt><dd>${escapeHtml(device.app_version || "—")}</dd></div>
      </dl>
    </article>`).join("");
}

function renderEvents(events) {
  const body = document.querySelector("#events");
  state.stats = { sms: 0, call: 0 };
  events.forEach(item => { if (item.event_type in state.stats) state.stats[item.event_type] += 1; });
  Object.entries(state.stats).forEach(([key, count]) => {
    document.querySelector(`#${key}-count`).textContent = count;
  });
  if (!events.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">尚无事件</td></tr>';
    return;
  }
  body.innerHTML = events.map(item => `
    <tr>
      <td>${formatTime(item.received_at)}</td>
      <td><span class="tag ${escapeHtml(item.event_type)}">${escapeHtml(item.event_type)}</span></td>
      <td>${item.sim_slot ? `SIM${item.sim_slot}` : "—"}</td>
      <td class="mono">${escapeHtml(item.sender || "—")}</td>
      <td class="content">${escapeHtml(item.event_type === "call" ? (item.call_type || item.content) : item.content)}</td>
      <td>${escapeHtml(item.device_id)}</td>
    </tr>`).join("");
}

async function refresh() {
  const statusDot = document.querySelector("#status-dot");
  const statusText = document.querySelector("#status-text");
  try {
    const suffix = state.type ? `?limit=200&type=${encodeURIComponent(state.type)}` : "?limit=200";
    const [devices, events, keys] = await Promise.all([
      getJson("/api/v1/devices"),
      getJson(`/api/v1/events${suffix}`),
      getJson("/api/v1/admin/keys")
    ]);
    renderDevices(devices.devices);
    renderEvents(events.events);
    renderKeys(keys.keys);
    statusDot.className = "online";
    statusText.textContent = "服务正常";
  } catch (error) {
    statusDot.className = "offline";
    statusText.textContent = `连接失败：${error.message}`;
  }
}

document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelectorAll(".filter").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".filter").forEach(item => item.classList.remove("active"));
  button.classList.add("active");
  state.type = button.dataset.type;
  refresh();
}));

document.querySelector("#key-form").addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  const deviceId = document.querySelector("#key-device").value.trim();
  const payload = {
    phone_number: document.querySelector("#key-phone").value.trim(),
    label: document.querySelector("#key-label").value.trim(),
    owner_ref: document.querySelector("#key-owner").value.trim()
  };
  if (deviceId) {
    payload.device_id = deviceId;
    payload.sim_slot = Number(document.querySelector("#key-sim").value);
  }
  submit.disabled = true;
  try {
    const result = await postJson("/api/v1/admin/keys", payload);
    showKeySecret(result.key, `${payload.phone_number} · 新 Key`);
    event.currentTarget.reset();
    await refresh();
  } catch (error) {
    window.alert(`签发失败：${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#keys").addEventListener("click", async event => {
  const button = event.target.closest("button[data-key-action]");
  if (!button) return;
  const action = button.dataset.keyAction;
  const keyId = button.dataset.keyId;
  const prompts = {
    rotate: "轮换后旧 Key 会立即失效，继续吗？",
    disable: "禁用后 Agent 将无法读取此号码，继续吗？",
    unbind: "解绑后需要 Android 重新绑定，继续吗？"
  };
  if (!window.confirm(prompts[action])) return;
  button.disabled = true;
  try {
    const result = await postJson(`/api/v1/admin/keys/${encodeURIComponent(keyId)}/${action}`);
    if (action === "rotate") showKeySecret(result.key, `${keyId} · 已轮换`);
    await refresh();
  } catch (error) {
    window.alert(`操作失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#copy-key").addEventListener("click", async event => {
  try {
    await navigator.clipboard.writeText(document.querySelector("#key-secret-value").textContent);
    event.currentTarget.textContent = "已复制";
  } catch (_error) {
    window.alert("复制失败，请手工复制并立即保存到 Secret 管理器。");
  }
});

refresh();
setInterval(refresh, 5000);
