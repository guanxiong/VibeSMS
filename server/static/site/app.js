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
