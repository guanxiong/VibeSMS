const statusNode = document.querySelector("#cloud-status");
const tr = (zh, en) => window.VibeSMSI18n?.text(zh, en) ?? zh;

function attributionFor(landing) {
  const parameters = new URLSearchParams(window.location.search);
  return {
    attribution_campaign: parameters.get("campaign") || parameters.get("cmp") || "",
    attribution_landing: landing
  };
}

function setCloudStatus(label, state) {
  const indicator = document.createElement("i");
  statusNode.className = `cloud-status ${state}`;
  statusNode.replaceChildren(indicator, document.createTextNode(` ${label}`));
}

async function updateCloudStatus() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const payload = await response.json();
    setCloudStatus(`Cloud online · v${String(payload.version || "—")}`, "is-online");
  } catch (_error) {
    setCloudStatus(tr("服务状态不可用", "Status unavailable"), "is-offline");
  }
}

updateCloudStatus();

const codeTabs = [...document.querySelectorAll("[data-code-tab]")];
const codePanels = [...document.querySelectorAll("[data-code-panel]")];
const copyCodeButton = document.querySelector("[data-copy-code]");

function selectCodeTab(tab) {
  const target = tab.dataset.codeTab;
  codeTabs.forEach((candidate) => {
    const selected = candidate === tab;
    candidate.classList.toggle("active", selected);
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  codePanels.forEach((panel) => {
    panel.hidden = panel.dataset.codePanel !== target;
  });
  if (copyCodeButton) copyCodeButton.textContent = tr("复制", "Copy");
}

codeTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectCodeTab(tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + codeTabs.length) % codeTabs.length;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % codeTabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = codeTabs.length - 1;
    selectCodeTab(codeTabs[nextIndex]);
    codeTabs[nextIndex].focus();
  });
});

async function copyText(button, text, successLabel) {
  try {
    await navigator.clipboard.writeText(text.trim());
    button.textContent = successLabel;
  } catch (_error) {
    button.textContent = tr("请手动复制", "Copy manually");
  }
}

copyCodeButton?.addEventListener("click", () => {
  const activePanel = codePanels.find((panel) => !panel.hidden);
  if (activePanel) copyText(copyCodeButton, activePanel.innerText, tr("已复制", "Copied"));
});

const copyInstallButton = document.querySelector("[data-copy-install]");
copyInstallButton?.addEventListener("click", () => {
  const command = copyInstallButton.parentElement?.querySelector("code")?.innerText || "";
  copyText(copyInstallButton, command, tr("已复制", "Copied"));
});

const keyDialog = document.querySelector("#key-dialog");
const keyDialogOpeners = [...document.querySelectorAll("[data-open-key-dialog]")];
const keyDialogForm = document.querySelector("#dialog-request-form");
const keyDialogSubmit = document.querySelector("#dialog-submit-request");
const keyDialogError = document.querySelector("#dialog-form-error");
const keyRequestView = document.querySelector("#key-request-view");
const keyIssuedView = document.querySelector("#key-issued-view");
const keyPendingView = document.querySelector("#key-pending-view");
const publicAvailability = document.querySelector("#public-key-availability");
let availabilityRefreshTimer = null;

function availabilityLabel(result, compact = false) {
  const remaining = Math.max(0, Number(result.auto_issue_remaining) || 0);
  if (result.auto_issue_available && remaining > 0) {
    return compact
      ? tr(`可自动签发 · 剩余 ${remaining} 个`, `${remaining} instant ${remaining === 1 ? "Key" : "Keys"} available`)
      : tr(`自动签发剩余 ${remaining} 个 · 提交后立即获得 Key`, `${remaining} instant ${remaining === 1 ? "Key" : "Keys"} available · issued after submission`);
  }
  return compact
    ? tr("自动名额已用完 · 可提交人工审核", "Instant capacity full · manual review available")
    : tr("自动签发名额已用完 · 提交后进入人工审核", "Instant capacity is full · submit for manual review");
}

function renderAvailability(result) {
  const available = Boolean(result.auto_issue_available && Number(result.auto_issue_remaining) > 0);
  const dialogStatus = document.querySelector("#dialog-issuance-status");
  if (dialogStatus) {
    dialogStatus.textContent = availabilityLabel(result);
    dialogStatus.dataset.available = String(available);
  }
  if (publicAvailability) {
    const label = publicAvailability.querySelector("span");
    if (label) label.textContent = availabilityLabel(result, true);
    publicAvailability.dataset.available = String(available);
  }
}

async function refreshIssuanceAvailability() {
  try {
    const response = await fetch("/api/v1/onboarding/status", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const result = await response.json();
    renderAvailability(result);
  } catch (_error) {
    const unavailable = tr("暂时无法同步名额 · 仍可提交申请", "Capacity unavailable · you can still apply");
    const dialogStatus = document.querySelector("#dialog-issuance-status");
    if (dialogStatus) {
      dialogStatus.textContent = unavailable;
      delete dialogStatus.dataset.available;
    }
    if (publicAvailability) {
      const label = publicAvailability.querySelector("span");
      if (label) label.textContent = unavailable;
      delete publicAvailability.dataset.available;
    }
  }
}

function openKeyDialog(event) {
  if (!keyDialog || typeof keyDialog.showModal !== "function") return;
  event.preventDefault();
  if (!keyDialog.open) keyDialog.showModal();
  refreshIssuanceAvailability();
}

keyDialogOpeners.forEach((opener) => opener.addEventListener("click", openKeyDialog));
document.querySelectorAll("[data-close-key-dialog]").forEach((button) => {
  button.addEventListener("click", () => keyDialog?.close());
});
keyDialog?.addEventListener("click", (event) => {
  if (event.target === keyDialog) keyDialog.close();
});

keyDialogForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  keyDialogError.textContent = "";
  keyDialogSubmit.disabled = true;
  keyDialogSubmit.textContent = tr("正在提交…", "Submitting…");
  try {
    const fields = new FormData(keyDialogForm);
    const payload = { ...Object.fromEntries(fields), ...attributionFor("home") };
    const response = await fetch("/api/v1/key-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(window.VibeSMSI18n?.isEnglish ? "Submission failed. Please try again." : (result.error || "提交失败，请稍后重试。"));
    keyRequestView.hidden = true;
    if (result.key) {
      sessionStorage.setItem("vibesms.inbox.key", result.key);
      document.querySelector("#dialog-issued-key").textContent = result.key;
      keyIssuedView.hidden = false;
      keyIssuedView.querySelector("h2")?.focus?.();
    } else {
      document.querySelector("#dialog-request-id").textContent = result.request_id || "—";
      keyPendingView.hidden = false;
      keyPendingView.querySelector("h2")?.focus();
    }
    refreshIssuanceAvailability();
    keyDialog.scrollTo({ top: 0, behavior: "smooth" });
  } catch (requestError) {
    keyDialogError.textContent = requestError.message;
  } finally {
    keyDialogSubmit.disabled = false;
    const arrow = document.createElement("span");
    arrow.textContent = "→";
    arrow.setAttribute("aria-hidden", "true");
    keyDialogSubmit.replaceChildren(document.createTextNode(`${tr("提交并获取 Key", "Submit and get a Key")} `), arrow);
  }
});

document.querySelector("[data-copy-issued-key]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-issued-key")?.textContent || "";
  copyText(event.currentTarget, value, tr("Key 已复制", "Key copied"));
});

document.querySelector("[data-copy-dialog-install]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-install-command")?.textContent || "";
  copyText(event.currentTarget, value, tr("命令已复制", "Command copied"));
});

document.querySelector("[data-copy-dialog-prompt]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-setup-prompt")?.textContent || "";
  copyText(event.currentTarget, value, tr("Prompt 已复制", "Prompt copied"));
});

refreshIssuanceAvailability();
availabilityRefreshTimer = window.setInterval(refreshIssuanceAvailability, 30000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshIssuanceAvailability();
});
window.addEventListener("pagehide", () => {
  if (availabilityRefreshTimer) window.clearInterval(availabilityRefreshTimer);
}, { once: true });
