const form = document.querySelector("#request-form");
const submit = document.querySelector("#submit-request");
const error = document.querySelector("#form-error");
const tr = (zh, en) => window.VibeSMSI18n?.text(zh, en) ?? zh;

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
    const remaining = Math.max(0, Number(result.auto_issue_remaining) || 0);
    status.textContent = result.auto_issue_available && remaining > 0
      ? tr(`自动签发剩余 ${remaining} 个 · 提交后立即获得 Key`, `${remaining} instant ${remaining === 1 ? "Key" : "Keys"} available · issued after submission`)
      : tr("自动签发名额已用完 · 提交后进入人工审核", "Instant capacity is full · submit for manual review");
    status.dataset.available = result.auto_issue_available ? "true" : "false";
  } catch (_error) {
    status.textContent = tr("暂时无法读取名额状态 · 仍可提交申请", "Capacity status unavailable · you can still apply");
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
    if (!response.ok) throw new Error(window.VibeSMSI18n?.isEnglish ? "Submission failed. Please try again." : (result.error || "提交失败，请稍后重试。"));
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
    event.currentTarget.textContent = tr("已复制", "Copied");
  } catch (_error) {
    window.alert(tr("复制失败，请手工复制并立即保存到 Secret 管理器。", "Copy failed. Copy it manually and save it to your secret manager now."));
  }
});

async function copyHandoff(button, selector, successLabel) {
  const value = document.querySelector(selector)?.textContent || "";
  try {
    await navigator.clipboard.writeText(value.trim());
    button.textContent = successLabel;
  } catch (_error) {
    window.alert(tr("复制失败，请手工选择并复制。", "Copy failed. Select and copy it manually."));
  }
}

document.querySelector("#copy-skill-command").addEventListener("click", event => {
  copyHandoff(event.currentTarget, "#setup-skill-command", tr("命令已复制", "Command copied"));
});

document.querySelector("#copy-agent-prompt").addEventListener("click", event => {
  copyHandoff(event.currentTarget, "#setup-agent-prompt", tr("Prompt 已复制", "Prompt copied"));
});

refreshIssuanceStatus();
