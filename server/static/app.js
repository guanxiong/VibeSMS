const state = { type: "", stats: { sms: 0, call: 0, heartbeat: 0 } };

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

function renderDevices(devices) {
  const container = document.querySelector("#devices");
  document.querySelector("#device-count").textContent = devices.length;
  if (!devices.length) {
    container.innerHTML = '<p class="empty">等待终端上报…</p>';
    return;
  }
  container.innerHTML = devices.map(device => `
    <article class="device-card">
      <div class="device-head"><strong>${escapeHtml(device.device_id)}</strong><span>${escapeHtml(device.last_event_type)}</span></div>
      <dl>
        <div><dt>最后在线</dt><dd>${formatTime(device.last_seen)}</dd></div>
        <div><dt>SIM</dt><dd>${device.sim_slot ? `SIM${device.sim_slot}` : "—"} ${escapeHtml(device.sim_label)}</dd></div>
        <div><dt>电量</dt><dd>${escapeHtml(device.battery || "—")}</dd></div>
        <div><dt>网络</dt><dd>${escapeHtml(device.network_type || "—")}</dd></div>
        <div><dt>App</dt><dd>${escapeHtml(device.app_version || "—")}</dd></div>
      </dl>
    </article>`).join("");
}

function renderEvents(events) {
  const body = document.querySelector("#events");
  state.stats = { sms: 0, call: 0, heartbeat: 0 };
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
    const [devices, events] = await Promise.all([
      getJson("/api/v1/devices"),
      getJson(`/api/v1/events${suffix}`)
    ]);
    renderDevices(devices.devices);
    renderEvents(events.events);
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

refresh();
setInterval(refresh, 5000);

