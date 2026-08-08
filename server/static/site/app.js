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
