const form = document.querySelector("#request-form");
const submit = document.querySelector("#submit-request");
const error = document.querySelector("#form-error");

form.addEventListener("submit", async event => {
  event.preventDefault();
  error.textContent = "";
  submit.disabled = true;
  try {
    const fields = new FormData(form);
    const response = await fetch("/api/v1/key-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(fields))
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "提交失败，请稍后重试。");
    document.querySelector("#request-id").textContent = result.request_id;
    form.hidden = true;
    document.querySelector("#request-success").hidden = false;
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    submit.disabled = false;
  }
});
