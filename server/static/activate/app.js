const form = document.querySelector("#activation-form");
const redeem = document.querySelector("#redeem-button");
const error = document.querySelector("#form-error");
const tr = (zh, en) => window.VibeSMSI18n?.text(zh, en) ?? zh;

form.addEventListener("submit", async event => {
  event.preventDefault();
  error.textContent = "";
  redeem.disabled = true;
  try {
    const response = await fetch("/api/v1/activations/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form)))
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(window.VibeSMSI18n?.isEnglish ? "Redemption failed. Check the activation code and try again." : (result.error || "兑换失败，请检查激活码后重试。"));
    sessionStorage.setItem("vibesms.inbox.key", result.key);
    document.querySelector("#issued-key").textContent = result.key;
    form.hidden = true;
    document.querySelector("#activation-success").hidden = false;
  } catch (activationError) {
    error.textContent = activationError.message;
  } finally {
    redeem.disabled = false;
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
