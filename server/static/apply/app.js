const form = document.querySelector("#request-form");
const submit = document.querySelector("#submit-request");
const error = document.querySelector("#form-error");

function attributionFor(landing) {
  const parameters = new URLSearchParams(window.location.search);
  return {
    attribution_campaign: parameters.get("campaign") || parameters.get("cmp") || "",
    attribution_landing: landing
  };
}

async function refreshIssuanceStatus() {
  const status = document.querySelector("#issuance-status");
  try {
    const response = await fetch("/api/v1/onboarding/status", { cache: "no-store" });
    const result = await response.json();
    status.textContent = result.auto_issue_available
      ? "自动签发名额可用 · 提交后立即获得 Key"
      : "自动名额暂不可用 · 提交后进入人工审核";
    status.dataset.available = result.auto_issue_available ? "true" : "false";
  } catch (_error) {
    status.textContent = "暂时无法读取名额状态 · 仍可提交申请";
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  error.textContent = "";
  submit.disabled = true;
  try {
    const fields = new FormData(form);
    const payload = { ...Object.fromEntries(fields), ...attributionFor("apply") };
    const response = await fetch("/api/v1/key-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "提交失败，请稍后重试。");
    form.hidden = true;
    if (result.key) {
      sessionStorage.setItem("vibesms.inbox.key", result.key);
      document.querySelector("#issued-key").textContent = result.key;
      document.querySelector("#auto-issue-success").hidden = false;
    } else {
      document.querySelector("#request-id").textContent = result.request_id;
      document.querySelector("#request-success").hidden = false;
    }
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#copy-key").addEventListener("click", async event => {
  try {
    await navigator.clipboard.writeText(document.querySelector("#issued-key").textContent);
    event.currentTarget.textContent = "已复制";
  } catch (_error) {
    window.alert("复制失败，请手工复制并立即保存到 Secret 管理器。");
  }
});

async function copyHandoff(button, selector, successLabel) {
  const value = document.querySelector(selector)?.textContent || "";
  try {
    await navigator.clipboard.writeText(value.trim());
    button.textContent = successLabel;
  } catch (_error) {
    window.alert("复制失败，请手工选择并复制。");
  }
}

document.querySelector("#copy-skill-command").addEventListener("click", event => {
  copyHandoff(event.currentTarget, "#setup-skill-command", "命令已复制");
});

document.querySelector("#copy-agent-prompt").addEventListener("click", event => {
  copyHandoff(event.currentTarget, "#setup-agent-prompt", "Prompt 已复制");
});

refreshIssuanceStatus();
