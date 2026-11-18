// Same contract as Perseo XML (odd/tasks/perseo-xml.md L6): the buttons message the tab found by
// chrome.tabs.query({active: true, currentWindow: true}); "Carpeta de descargas" opens a new tab.
// Opened as a plain page (no chrome.tabs, e.g. served over http), the buttons only update the status line.
const estado = document.getElementById("estado");
const hasTabs = typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query;

function show(text) {
  estado.textContent = text;
}

for (const button of document.querySelectorAll("button[data-action]")) {
  button.addEventListener("click", async () => {
    show("En proceso…");
    button.disabled = true;
    try {
      if (!hasTabs) {
        await new Promise((r) => setTimeout(r, 900));
        show("Vista previa: 3 comprobantes descargados");
        return;
      }
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        show("Abre la consulta de comprobantes primero");
        return;
      }
      const reply = await chrome.tabs.sendMessage(tab.id, { action: button.dataset.action });
      show(`${reply.count} comprobantes descargados`);
    } catch (err) {
      show("Abre la consulta de comprobantes primero");
    } finally {
      button.disabled = false;
    }
  });
}

// In preview mode the local stand-in of chrome://settings/downloads (nested shadow roots) opens instead.
document.getElementById("configure-folder").addEventListener("click", () => {
  if (hasTabs && chrome.tabs.create) chrome.tabs.create({ url: "chrome://settings/downloads" });
  else window.open("../site/ajustes.html", "_blank");
});
