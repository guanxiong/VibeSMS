const statusNode = document.querySelector("#cloud-status");

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
    setCloudStatus("Status unavailable", "is-offline");
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
  if (copyCodeButton) copyCodeButton.textContent = "复制";
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
    button.textContent = "请手动复制";
  }
}

copyCodeButton?.addEventListener("click", () => {
  const activePanel = codePanels.find((panel) => !panel.hidden);
  if (activePanel) copyText(copyCodeButton, activePanel.innerText, "已复制");
});

const copyInstallButton = document.querySelector("[data-copy-install]");
copyInstallButton?.addEventListener("click", () => {
  const command = copyInstallButton.parentElement?.querySelector("code")?.innerText || "";
  copyText(copyInstallButton, command, "已复制");
});

const keyDialog = document.querySelector("#key-dialog");
const keyDialogOpeners = [...document.querySelectorAll("[data-open-key-dialog]")];
const keyDialogForm = document.querySelector("#dialog-request-form");
const keyDialogSubmit = document.querySelector("#dialog-submit-request");
const keyDialogError = document.querySelector("#dialog-form-error");
const keyRequestView = document.querySelector("#key-request-view");
const keyIssuedView = document.querySelector("#key-issued-view");
const keyPendingView = document.querySelector("#key-pending-view");

async function refreshDialogIssuanceStatus() {
  const status = document.querySelector("#dialog-issuance-status");
  if (!status) return;
  try {
    const response = await fetch("/api/v1/onboarding/status", { cache: "no-store" });
    const result = await response.json();
    status.textContent = result.auto_issue_available
      ? "自动签发名额可用 · 提交后立即获得 Key"
      : "自动名额暂不可用 · 提交后进入人工审核";
    status.dataset.available = result.auto_issue_available ? "true" : "false";
  } catch (_error) {
    status.textContent = "暂时无法读取名额状态 · 仍可提交申请";
    delete status.dataset.available;
  }
}

function openKeyDialog(event) {
  if (!keyDialog || typeof keyDialog.showModal !== "function") return;
  event.preventDefault();
  if (!keyDialog.open) keyDialog.showModal();
  refreshDialogIssuanceStatus();
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
  keyDialogSubmit.textContent = "正在提交…";
  try {
    const fields = new FormData(keyDialogForm);
    const response = await fetch("/api/v1/key-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(fields))
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "提交失败，请稍后重试。");
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
    keyDialog.scrollTo({ top: 0, behavior: "smooth" });
  } catch (requestError) {
    keyDialogError.textContent = requestError.message;
  } finally {
    keyDialogSubmit.disabled = false;
    const arrow = document.createElement("span");
    arrow.textContent = "→";
    arrow.setAttribute("aria-hidden", "true");
    keyDialogSubmit.replaceChildren(document.createTextNode("提交并获取 Key "), arrow);
  }
});

document.querySelector("[data-copy-issued-key]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-issued-key")?.textContent || "";
  copyText(event.currentTarget, value, "Key 已复制");
});

document.querySelector("[data-copy-dialog-install]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-install-command")?.textContent || "";
  copyText(event.currentTarget, value, "命令已复制");
});

document.querySelector("[data-copy-dialog-prompt]")?.addEventListener("click", (event) => {
  const value = document.querySelector("#dialog-setup-prompt")?.textContent || "";
  copyText(event.currentTarget, value, "Prompt 已复制");
});
