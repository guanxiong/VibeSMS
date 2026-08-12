const state = { type: "", stats: { sms: 0, call: 0 } };
const deviceInput = document.querySelector("#key-device");
const simSelect = document.querySelector("#key-sim");

function syncSimSlotState() {
  const hasPreboundDevice = Boolean(deviceInput.value.trim());
  simSelect.disabled = !hasPreboundDevice;
  if (!hasPreboundDevice) simSelect.value = "";
}

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

function showActivationSecret(value, label) {
  const secret = document.querySelector("#activation-secret");
  document.querySelector("#activation-secret-label").textContent = label;
  document.querySelector("#activation-secret-value").textContent = value;
  document.querySelector("#copy-activation").textContent = "复制激活码";
  secret.hidden = false;
  secret.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderRequests(requests) {
  const container = document.querySelector("#key-requests");
  if (!requests.length) {
    container.innerHTML = '<p class="empty">尚无 Key 申请</p>';
    return;
  }
  container.innerHTML = `<p class="subsection-label">KEY REQUESTS · ${requests.length}</p>` + requests.map(request => `
    <article class="request-card ${request.status !== "pending" ? "is-handled" : ""}">
      <div class="key-card-head"><div><strong>${escapeHtml(request.email)}</strong><span>${escapeHtml(request.request_id)}</span></div><span class="key-state">${escapeHtml(request.status.toUpperCase())}</span></div>
      <dl><div><dt>手机号</dt><dd>${escapeHtml(request.phone_number || "—")}</dd></div><div><dt>终端</dt><dd>${escapeHtml(request.device_count)} 台</dd></div><div><dt>用途</dt><dd>${escapeHtml(request.use_case)}</dd></div><div><dt>来源</dt><dd class="mono">${escapeHtml(request.attribution_source || "direct")} / ${escapeHtml(request.attribution_campaign || "none")}</dd></div><div><dt>${request.key_id ? "Key ID" : "提交时间"}</dt><dd>${request.key_id ? escapeHtml(request.key_id) : formatTime(request.created_at)}</dd></div>${request.contact ? `<div><dt>补充联系</dt><dd>${escapeHtml(request.contact)}</dd></div>` : ""}</dl>
      ${request.status === "pending" ? `<div class="key-actions"><button type="button" data-request-id="${escapeHtml(request.request_id)}">填入并生成激活码</button></div>` : ""}
    </article>`).join("");
}

function renderAcquisitionFunnel(funnel) {
  const container = document.querySelector("#acquisition-funnel");
  const totals = funnel.totals || {};
  const channels = funnel.channels || [];
  const cards = [
    ["申请", totals.requested], ["获得 Key", totals.issued], ["完成绑定", totals.bound],
    ["24h 首次心跳", totals.heartbeat_24h], ["24h 首个事件", totals.first_event_24h]
  ];
  const rows = channels.length ? channels.map(channel => `<tr>
    <td class="mono">${escapeHtml(channel.source)} / ${escapeHtml(channel.campaign)}</td>
    <td>${channel.requested}</td><td>${channel.issued}</td><td>${channel.bound}</td>
    <td>${channel.heartbeat_24h}</td><td>${channel.first_event_24h}</td>
  </tr>`).join("") : '<tr><td colspan="6" class="empty">尚无推广申请</td></tr>';
  container.innerHTML = `<div class="funnel-summary">${cards.map(([label, value]) => `<article><span>${label}</span><strong>${Number(value || 0)}</strong></article>`).join("")}</div>
    <div class="table-wrap"><table><thead><tr><th>渠道 / 活动</th><th>申请</th><th>获得 Key</th><th>完成绑定</th><th>24h 首次心跳</th><th>24h 首个事件</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function campaignLink(campaign) {
  const base = campaign.landing === "home" ? "/" : "/apply/";
  return `${window.location.origin}${base}?campaign=${encodeURIComponent(campaign.code)}`;
}

function renderCampaigns(campaigns) {
  const container = document.querySelector("#campaigns");
  if (!campaigns.length) {
    container.innerHTML = '<p class="empty">尚无推广活动</p>';
    return;
  }
  container.innerHTML = campaigns.map(campaign => {
    const link = campaignLink(campaign);
    return `<article class="campaign-card ${campaign.enabled ? "" : "is-disabled"}">
      <div class="key-card-head"><div><strong>${escapeHtml(campaign.name)}</strong><span class="mono">${escapeHtml(campaign.code)}</span></div><span class="key-state">${campaign.enabled ? "ACTIVE" : "DISABLED"}</span></div>
      <dl><div><dt>渠道</dt><dd>${escapeHtml(campaign.source)}</dd></div><div><dt>落地页</dt><dd>${campaign.landing === "home" ? "首页" : "申请页"}</dd></div></dl>
      <div class="campaign-link"><code>${escapeHtml(link)}</code><button type="button" data-campaign-link="${escapeHtml(link)}">复制链接</button></div>
      <div class="key-actions"><button type="button" data-campaign-action="${campaign.enabled ? "disable" : "enable"}" data-campaign-id="${escapeHtml(campaign.campaign_id)}">${campaign.enabled ? "停用" : "启用"}</button></div>
    </article>`;
  }).join("");
}

function renderOnboarding(settings) {
  const form = document.querySelector("#onboarding-form");
  if (!form.contains(document.activeElement)) {
    document.querySelector("#auto-issue-enabled").checked = settings.auto_issue_enabled;
    document.querySelector("#auto-issue-quota").value = settings.auto_issue_quota;
  }
  const stateLabel = document.querySelector("#onboarding-state");
  stateLabel.textContent = settings.auto_issue_available
    ? `已开启 · 剩余 ${settings.auto_issue_quota}`
    : settings.auto_issue_enabled ? "额度为 0 · 人工审核" : "已关闭 · 人工审核";
  stateLabel.className = settings.auto_issue_available ? "is-enabled" : "";
}

function renderActivationCodes(codes) {
  const container = document.querySelector("#activation-codes");
  if (!codes.length) {
    container.innerHTML = '<p class="empty">尚无激活码</p>';
    return;
  }
  container.innerHTML = `<p class="subsection-label">ACTIVATION CODES · ${codes.length}</p>` + codes.map(code => `
    <article class="activation-card ${code.status !== "available" ? "is-handled" : ""}">
      <div class="key-card-head"><div><strong>${escapeHtml(code.label || code.activation_id)}</strong><span>${escapeHtml(code.activation_id)}</span></div><span class="key-state">${escapeHtml(code.status.toUpperCase())}</span></div>
      <dl><div><dt>关联申请</dt><dd class="mono">${escapeHtml(code.request_id || "—")}</dd></div><div><dt>到期</dt><dd>${formatTime(code.expires_at)}</dd></div>${code.redeemed_phone ? `<div><dt>兑换号码</dt><dd>${escapeHtml(code.redeemed_phone)}</dd></div><div><dt>Key ID</dt><dd class="mono">${escapeHtml(code.key_id)}</dd></div>` : ""}</dl>
      ${code.status === "available" ? `<div class="key-actions"><button class="danger" type="button" data-activation-id="${escapeHtml(code.activation_id)}">作废</button></div>` : ""}
    </article>`).join("");
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
    const [devices, events, keys, requests, activationCodes, onboarding, funnel, campaigns] = await Promise.all([
      getJson("/api/v1/devices"),
      getJson(`/api/v1/events${suffix}`),
      getJson("/api/v1/admin/keys"),
      getJson("/api/v1/admin/key-requests"),
      getJson("/api/v1/admin/activation-codes"),
      getJson("/api/v1/admin/onboarding-settings"),
      getJson("/api/v1/admin/acquisition-funnel"),
      getJson("/api/v1/admin/campaigns")
    ]);
    renderDevices(devices.devices);
    renderEvents(events.events);
    renderKeys(keys.keys);
    renderRequests(requests.requests);
    renderActivationCodes(activationCodes.activation_codes);
    renderOnboarding(onboarding);
    renderAcquisitionFunnel(funnel);
    renderCampaigns(campaigns.campaigns);
    statusDot.className = "online";
    statusText.textContent = "服务正常";
  } catch (error) {
    statusDot.className = "offline";
    statusText.textContent = `连接失败：${error.message}`;
  }
}

document.querySelector("#refresh").addEventListener("click", refresh);
deviceInput.addEventListener("input", syncSimSlotState);
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
    syncSimSlotState();
    await refresh();
  } catch (error) {
    window.alert(`签发失败：${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#activation-form").addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  const payload = {
    request_id: document.querySelector("#activation-request").value.trim(),
    label: document.querySelector("#activation-label").value.trim(),
    expires_in_days: Number(document.querySelector("#activation-days").value)
  };
  submit.disabled = true;
  try {
    const result = await postJson("/api/v1/admin/activation-codes", payload);
    showActivationSecret(result.activation_code, `${result.activation_id} · 至 ${formatTime(result.expires_at)}`);
    event.currentTarget.reset();
    document.querySelector("#activation-days").value = "14";
    await refresh();
  } catch (error) {
    window.alert(`生成失败：${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#onboarding-form").addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const result = await postJson("/api/v1/admin/onboarding-settings", {
      auto_issue_enabled: document.querySelector("#auto-issue-enabled").checked,
      auto_issue_quota: Number(document.querySelector("#auto-issue-quota").value)
    });
    renderOnboarding(result);
    await refresh();
  } catch (error) {
    window.alert(`保存失败：${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#campaign-form").addEventListener("submit", async event => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  const payload = {
    name: document.querySelector("#campaign-name").value.trim(),
    code: document.querySelector("#campaign-code").value.trim().toLowerCase(),
    source: document.querySelector("#campaign-source").value,
    landing: document.querySelector("#campaign-landing").value
  };
  submit.disabled = true;
  try {
    await postJson("/api/v1/admin/campaigns", payload);
    event.currentTarget.reset();
    await refresh();
  } catch (error) {
    window.alert(`创建失败：${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#key-requests").addEventListener("click", event => {
  const button = event.target.closest("button[data-request-id]");
  if (!button) return;
  document.querySelector("#activation-request").value = button.dataset.requestId;
  document.querySelector("#activation-label").focus();
  document.querySelector("#activation-form").scrollIntoView({ behavior: "smooth", block: "center" });
});

document.querySelector("#activation-codes").addEventListener("click", async event => {
  const button = event.target.closest("button[data-activation-id]");
  if (!button || !window.confirm("作废后该激活码不能再兑换，继续吗？")) return;
  button.disabled = true;
  try {
    await postJson(`/api/v1/admin/activation-codes/${encodeURIComponent(button.dataset.activationId)}/disable`);
    await refresh();
  } catch (error) {
    window.alert(`作废失败：${error.message}`);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#campaigns").addEventListener("click", async event => {
  const copyButton = event.target.closest("button[data-campaign-link]");
  if (copyButton) {
    try {
      await navigator.clipboard.writeText(copyButton.dataset.campaignLink);
      copyButton.textContent = "已复制";
    } catch (_error) {
      window.alert("复制失败，请手动复制链接。");
    }
    return;
  }
  const button = event.target.closest("button[data-campaign-action]");
  if (!button) return;
  const action = button.dataset.campaignAction;
  if (!window.confirm(action === "disable" ? "停用后新的申请不会再归因到该活动，继续吗？" : "启用该推广活动吗？")) return;
  button.disabled = true;
  try {
    await postJson(`/api/v1/admin/campaigns/${encodeURIComponent(button.dataset.campaignId)}/${action}`);
    await refresh();
  } catch (error) {
    window.alert(`操作失败：${error.message}`);
  } finally {
    button.disabled = false;
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

document.querySelector("#copy-activation").addEventListener("click", async event => {
  try {
    await navigator.clipboard.writeText(document.querySelector("#activation-secret-value").textContent);
    event.currentTarget.textContent = "已复制";
  } catch (_error) {
    window.alert("复制失败，请手工复制激活码后安全发送。");
  }
});

refresh();
syncSimSlotState();
setInterval(refresh, 5000);
