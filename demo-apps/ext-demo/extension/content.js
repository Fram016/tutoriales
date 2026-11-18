// Content script on http://127.0.0.1:8767/*: answers the popup's buttons with a toast on the page and the
// number of documents in the results table (no real download).
const LABELS = {
  descargarRecibidos: "XML recibidos",
  descargarRecibidosPDF: "PDF recibidos",
  descargarEmitidos: "PDF emitidos",
  descargarEmitidosXML: "XML emitidos",
};

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  const label = LABELS[message && message.action];
  if (!label) return false;
  const count = document.querySelectorAll("#resultados tbody tr").length;
  let toast = document.getElementById("demo-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "demo-toast";
    toast.setAttribute("role", "status");
    document.body.appendChild(toast);
  }
  toast.textContent = `Descargando ${count} comprobantes (${label})`;
  toast.className = "visible";
  setTimeout(() => { toast.className = ""; }, 4000);
  reply({ count });
  return false;
});
