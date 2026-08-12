const form = document.querySelector("#request-form");
const submit = document.querySelector("#submit-request");
const error = document.querySelector("#form-error");
const tr = (zh, en) => window.VibeSMSI18n?.text(zh, en) ?? zh;
const CLAIM_DEVICE_STORAGE_KEY = "vibesms.claim-device";

function claimDeviceId() {
  try {
    const existing = localStorage.getItem(CLAIM_DEVICE_STORAGE_KEY) || "";
    if (/^[A-Za-z0-9_-]{16,128}$/.test(existing)) return existing;
    let generated = globalThis.crypto?.randomUUID?.().replaceAll("-", "") || "";
    if (!generated && globalThis.crypto?.getRandomValues) {
      const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
      generated = [...bytes].map(value => value.toString(16).padStart(2, "0")).join("");
    }
    if (!generated) return "";
    localStorage.setItem(CLAIM_DEVICE_STORAGE_KEY, generated);
    return generated;
  } catch (_error) {
    return "";
  }
}

const currentClaimDeviceId = claimDeviceId();

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
    const headers = currentClaimDeviceId ? { "X-VibeSMS-Claim-Device": currentClaimDeviceId } : {};
    const response = await fetch("/api/v1/onboarding/status", { cache: "no-store", headers });
    const result = await response.json();
    const remaining = Math.max(0, Number(result.auto_issue_remaining) || 0);
    status.textContent = result.device_already_claimed
      ? tr("本设备已领取过自动 Key · 再次提交将进入人工审核", "This device already claimed an instant Key · another request enters manual review")
      : result.device_auto_issue_eligible === false
        ? tr("浏览器无法保存匿名设备标识 · 提交后进入人工审核", "The browser cannot save an anonymous device ID · submit for manual review")
        : result.auto_issue_available && remaining > 0
          ? tr(`自动签发剩余 ${remaining} 个 · 提交后立即获得 Key`, `${remaining} instant ${remaining === 1 ? "Key" : "Keys"} available · issued after submission`)
          : tr("自动签发名额已用完 · 提交后进入人工审核", "Instant capacity is full · submit for manual review");
    status.dataset.available = result.auto_issue_available
      && result.device_auto_issue_eligible
      && !result.device_already_claimed ? "true" : "false";
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
    const payload = {
      ...Object.fromEntries(fields),
      ...attributionFor("apply"),
      claim_device_id: currentClaimDeviceId
    };
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
      const explanation = document.querySelector("#request-pending-explanation");
      if (explanation && result.auto_issue_blocked_reason === "device_limit") {
        explanation.textContent = tr("本设备已领取过自动签发额度，本次申请已转入人工审核。", "This device has already used its instant-issue allowance, so this request was sent to manual review.");
      }
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
