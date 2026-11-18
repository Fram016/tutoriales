// Frame recorder + step runner for ego-lite (imported by the generated take.mjs).
//
// ego-lite blocks Page.screencastFrameAck, so CDP screencast stalls after one frame.
// Instead we keep N Page.captureScreenshot requests in flight (~10 fps at 1080p) and
// stamp each frame. Every action is logged with its time, element box and pointer
// position, so the editor can cut, zoom and draw a synthetic cursor exactly.
//
// Also (perseo-xml S3/S5): `censor` blurs selectors and text matches in the page itself before any
// screenshot; `surfaces` are extra pages (an extension popup) recorded on the same clock while open;
// `follow: tab` moves the main recording to a tab a click opened, `back: main` returns.
//
// Round 4 (odd/tasks/reglas-ronda4.md T1): every marked target is verified (N13: visible, in the viewport,
// hit at its point; `target_ok` / `target_text`, the take fails otherwise); surfaces may `hide` promotions
// (N23); the censor walks open shadow roots, and on a followed tab where no script runs (chrome://) the
// matching text is logged as `censor_regions` for compose to blur (N25).

const fs = await import("node:fs/promises");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// `t0` shares the clock between recorders (main tab and surfaces); `prefix` names the frames of one take
// of a surface (w0_f000000.jpg ...); `write: false` leaves frames.json to the caller (`frames` holds them).
export async function startRecorder(page, outDir,
  { inflight = 3, quality = 88, t0 = Date.now(), prefix = "f", clear = true, write = true } = {}) {
  const framesDir = `${outDir}/frames`;
  if (clear) await fs.rm(framesDir, { recursive: true, force: true });
  await fs.mkdir(framesDir, { recursive: true });
  const frames = [];
  let seq = 0;
  let running = true;
  let errors = 0;
  let current = page;
  let gen = 0;   // bumped by setPage: a screenshot of the previous tab landing late is dropped
  const worker = async () => {
    while (running) {
      const tReq = Date.now();
      const mine = gen;
      try {
        const r = await current.cdp("Page.captureScreenshot", { format: "jpeg", quality, optimizeForSpeed: true });
        if (mine !== gen) continue;
        const t = ((tReq + Date.now()) / 2 - t0) / 1000;
        const name = `${prefix}${String(seq++).padStart(6, "0")}.jpg`;
        await fs.writeFile(`${framesDir}/${name}`, Buffer.from(r.data, "base64"));
        frames.push({ file: name, t });
      } catch {
        if (++errors > 50) running = false;
        await sleep(50);
      }
    }
  };
  const workers = Array.from({ length: inflight }, worker);
  return {
    t0,
    frames,
    now: () => (Date.now() - t0) / 1000,
    setPage(next) {
      current = next;
      gen++;
    },
    async stop() {
      running = false;
      await Promise.all(workers);
      frames.sort((a, b) => a.t - b.t);
      if (write) await fs.writeFile(`${outDir}/frames.json`, JSON.stringify({ frames, errors }, null, 1));
      return frames.length;
    },
  };
}

// --- censor (S3) ------------------------------------------------------------------------------
// censorRanges, censorSegments, wrapTextNode and installCensor also run inside the page: censorSource
// embeds their source, so they only use their arguments and each other. None of them logs anything:
// the matched text (a RUC, a person's name) must never reach a log.

// Merged [start, end) ranges of `text` matched by any pattern (regex sources; `flags` = censor.regex_flags,
// case-insensitive by default).
export function censorRanges(text, patterns, flags = "i") {
  const found = [];
  for (const pattern of patterns || []) {
    const re = new RegExp(pattern, `g${flags}`);
    for (let m = re.exec(text); m; m = re.exec(text)) {
      if (m[0].length === 0) {
        re.lastIndex++;
        continue;
      }
      found.push([m.index, m.index + m[0].length]);
    }
  }
  found.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged = [];
  for (const r of found) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

// `text` cut at the ranges: [{text, censored}].
export function censorSegments(text, ranges) {
  const out = [];
  let at = 0;
  for (const [a, b] of ranges) {
    if (a > at) out.push({ text: text.slice(at, a), censored: false });
    out.push({ text: text.slice(a, b), censored: true });
    at = b;
  }
  if (at < text.length) out.push({ text: text.slice(at), censored: false });
  return out;
}

// Replaces a text node by plain text plus blurred spans over its matches. Returns the number of matches.
export function wrapTextNode(doc, node, patterns, flags = "i") {
  const parent = node.parentElement;
  if (!parent || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TEXTAREA|TITLE)$/.test(parent.tagName)
      || parent.getAttribute("data-tutorial-censor") === "text") return 0;
  const text = node.nodeValue || "";
  if (!text.trim()) return 0;
  const ranges = censorRanges(text, patterns, flags);
  if (!ranges.length) return 0;
  const frag = doc.createDocumentFragment();
  for (const seg of censorSegments(text, ranges)) {
    if (!seg.censored) {
      frag.appendChild(doc.createTextNode(seg.text));
      continue;
    }
    const span = doc.createElement("span");
    span.setAttribute("data-tutorial-censor", "text");
    span.style.setProperty("display", "inline-block", "important");
    span.style.setProperty("filter", "blur(8px)", "important");
    span.style.setProperty("user-select", "none", "important");
    span.textContent = seg.text;
    frag.appendChild(span);
  }
  node.parentNode.replaceChild(frag, node);
  return ranges.length;
}

// Blurs every element matching cfg.selectors and every text/field value matching cfg.text, now and after
// any DOM change (JSF partial updates, navigations re-run it from addScriptToEvaluateOnNewDocument).
// MutationObserver callbacks run before the next paint, so no screenshot shows the clear text.
// N25: open shadow roots (chrome://settings is built of them) are walked recursively and observed too;
// roots attached later are caught by a hook on attachShadow (installed before the page's scripts when
// this runs as a new-document script).
export function installCensor(g, cfg) {
  const doc = g.document;
  if (!doc) return;
  const key = JSON.stringify(cfg);
  if (g.__tutorialCensor && g.__tutorialCensor.key === key) {
    g.__tutorialCensor.apply();
    return;
  }
  // A different config replaces the previous install instead of being silently ignored.
  if (g.__tutorialCensor) g.__tutorialCensor.stop();
  const MARK = "data-tutorial-censor";
  const FIELDS = "input, textarea, select";
  const OPTIONS = { childList: true, subtree: true, characterData: true, attributes: true,
    attributeFilter: ["class", "id", "value"] };
  const patterns = cfg.text || [];
  const flags = cfg.flags ?? "i";
  const selectors = (cfg.selectors || []).join(", ");
  const roots = new Set();   // shadow roots found so far
  const blur = (el, why) => {
    if (!el.hasAttribute(MARK)) el.setAttribute(MARK, why);
    el.style.setProperty("filter", "blur(8px)", "important");
    el.style.setProperty("user-select", "none", "important");
  };
  const shown = (el) => (el.tagName === "SELECT" ? (el.options[el.selectedIndex] || {}).text || "" : String(el.value ?? ""));
  const value = (el) => {
    if (!patterns.length) return;
    if (censorRanges(shown(el), patterns, flags).length) blur(el, "value");
    else if (el.getAttribute(MARK) === "value") {
      el.removeAttribute(MARK);
      el.style.removeProperty("filter");
      el.style.removeProperty("user-select");
    }
  };
  const scan = (root) => {
    if (root.nodeType === 3) {
      wrapTextNode(doc, root, patterns, flags);
      return;
    }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (selectors) {
      try {
        if (root.matches && root.matches(selectors)) blur(root, "selector");
        root.querySelectorAll(selectors).forEach((el) => blur(el, "selector"));
      } catch (e) {
        // an invalid selector blurs nothing; the text patterns still apply
      }
    }
    if (patterns.length) {
      const walker = doc.createTreeWalker(root, 4);
      const nodes = [];
      for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
      for (const n of nodes) wrapTextNode(doc, n, patterns, flags);
      if (root.matches && root.matches(FIELDS)) value(root);
      if (root.querySelectorAll) root.querySelectorAll(FIELDS).forEach(value);
    }
    // The tree walker and querySelectorAll stop at shadow roots: each one is scanned (and observed) by itself.
    if (root.shadowRoot) adopt(root.shadowRoot);
    if (root.querySelectorAll) root.querySelectorAll("*").forEach((el) => el.shadowRoot && adopt(el.shadowRoot));
  };
  const adopt = (sr) => {
    roots.add(sr);
    scan(sr);
  };
  let observer = null;
  const watch = () => {
    observer.observe(doc, OPTIONS);
    roots.forEach((sr) => observer.observe(sr, OPTIONS));
  };
  const apply = (fn) => {
    observer.disconnect();
    try {
      fn();
    } finally {
      watch();
    }
  };
  observer = new g.MutationObserver((records) => apply(() => {
    for (const r of records) {
      if (r.type === "childList") r.addedNodes.forEach((n) => n.isConnected && scan(n));
      else if (r.target.isConnected) scan(r.target);
    }
  }));
  const all = () => apply(() => doc.documentElement && scan(doc.documentElement));
  all();
  // Field values change without DOM mutations (typing, JSF scripts setting .value).
  const onField = (e) => apply(() => value(e.target));
  doc.addEventListener("input", onField, true);
  doc.addEventListener("change", onField, true);
  const timer = patterns.length ? g.setInterval(() => apply(() => {
    doc.querySelectorAll(FIELDS).forEach(value);
    roots.forEach((sr) => sr.querySelectorAll(FIELDS).forEach(value));
  }), 150) : null;
  const proto = g.Element && g.Element.prototype;
  if (proto && typeof proto.attachShadow === "function" && !proto.attachShadow.__tutorialCensor) {
    const original = proto.attachShadow;
    const later = g.queueMicrotask ? (f) => g.queueMicrotask(f) : (f) => Promise.resolve().then(f);
    const hooked = function (...args) {
      const sr = original.apply(this, args);
      later(() => g.__tutorialCensor && g.__tutorialCensor.adopt(sr));
      return sr;
    };
    hooked.__tutorialCensor = true;
    proto.attachShadow = hooked;
  }
  g.__tutorialCensor = {
    key,
    apply: all,
    adopt: (sr) => apply(() => adopt(sr)),
    stop() {
      observer.disconnect();
      doc.removeEventListener("input", onField, true);
      doc.removeEventListener("change", onField, true);
      if (timer) g.clearInterval(timer);
    },
  };
}

// Self-contained script for Page.addScriptToEvaluateOnNewDocument / Runtime.evaluate. A bad pattern fails
// here, before the take, with its index only (the pattern may be the person's name).
export function censorSource(cfg = {}) {
  const text = (cfg.text || []).map(String);
  const flags = cfg.flags ?? "i";
  if (!/^[imsu]*$/.test(flags) || new Set(flags).size !== flags.length) throw new Error("censor.regex_flags no es válido");
  text.forEach((pattern, i) => {
    try {
      new RegExp(pattern, `g${flags}`);
    } catch {
      throw new Error(`censor.text[${i}] no es una expresión regular válida`);
    }
  });
  const config = JSON.stringify({ selectors: cfg.selectors || [], text, flags });
  return `(() => {\n${censorRanges}\n${censorSegments}\n${wrapTextNode}\n${installCensor}\n` +
    `installCensor(globalThis, ${config});\n})();`;
}

// --- surfaces (S5) ----------------------------------------------------------------------------

// Inside an extension page opened as a tab, {active: true, currentWindow: true} would be that tab itself:
// answer it with the most recent tab matching `target` (the page the popup acts on). Idempotent.
export function patchTabs(g, target) {
  const tabs = g && g.chrome && g.chrome.tabs;
  if (!tabs || typeof tabs.query !== "function" || tabs.query.__tutorialPatched) return false;
  const original = tabs.query.bind(tabs);
  const call = (q) => new Promise((resolve) => original(q, resolve));
  const active = (q) => !!q && q.active === true && (q.currentWindow === true || q.lastFocusedWindow === true) && !q.url;
  const query = function (q, cb) {
    const p = target && active(q)
      ? call({ url: target }).then((found) => (found && found.length
        ? [found.slice().sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0]]
        : call(q)))
      : call(q);
    if (typeof cb === "function") {
      p.then(cb);
      return undefined;
    }
    return p;
  };
  query.__tutorialPatched = true;
  try {
    tabs.query = query;
  } catch (e) {
    // read-only binding: defined below
  }
  if (tabs.query !== query) Object.defineProperty(tabs, "query", { value: query, configurable: true, writable: true });
  return true;
}

export function tabsPatchSource(target) {
  return `(${patchTabs})(globalThis, ${JSON.stringify(target ?? null)});`;
}

// N23: surfaces.<name>.hide. One rule per selector, so an invalid selector only drops its own rule.
export function hideCss(selectors) {
  return (selectors || []).map((s) => `${s} { display: none !important; }`).join("\n");
}

// Adds the hide style as soon as the document has a root (new-document scripts run before it exists). Null
// without selectors.
export function hideSource(selectors) {
  if (!(selectors || []).length) return null;
  return `(() => {
  const css = ${JSON.stringify(hideCss(selectors))};
  const add = () => {
    if (document.querySelector("style[data-tutorial-hide]")) return true;
    const root = document.head || document.documentElement;
    if (!root) return false;
    const style = document.createElement("style");
    style.setAttribute("data-tutorial-hide", "");
    style.textContent = css;
    root.appendChild(style);
    return true;
  };
  if (!add()) {
    const observer = new MutationObserver(() => add() && observer.disconnect());
    observer.observe(document, { childList: true, subtree: true });
  }
})();`;
}

// --- censor regions (N25 fallback) -------------------------------------------------------------
// A page where no script runs (chrome://) is censored by compose: the boxes of the matching text, found in
// DOM.getDocument({depth: -1, pierce: true}) (open and closed shadow roots, frames) + DOM.getBoxModel.

// [{nodeId, parentId}] of the text nodes matching the patterns (not inside script/style nor already blurred).
export function censorTextNodes(root, patterns, flags = "i") {
  const out = [];
  if (!root || !(patterns || []).length) return out;
  const marked = (n) => {
    const a = n.attributes || [];
    for (let i = 0; i < a.length; i += 2) if (a[i] === "data-tutorial-censor") return true;
    return false;
  };
  const walk = (n, parent, skip) => {
    if (n.nodeType === 3) {
      if (parent && !skip && censorRanges(n.nodeValue || "", patterns, flags).length) {
        out.push({ nodeId: n.nodeId, parentId: parent.nodeId });
      }
      return;
    }
    const inner = skip || (n.nodeType === 1 && (/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TITLE)$/.test(n.nodeName) || marked(n)));
    for (const sr of n.shadowRoots || []) walk(sr, n, inner);
    for (const c of n.children || []) walk(c, n, inner);
    if (n.contentDocument) walk(n.contentDocument, n, inner);
  };
  walk(root, null, false);
  return out;
}

// Viewport box of a CDP quad [x1, y1, ..., x4, y4] in whole pixels; null when it is off screen.
export function quadBox(quad, [vw, vh] = [1920, 1080]) {
  const xs = [quad[0], quad[2], quad[4], quad[6]], ys = [quad[1], quad[3], quad[5], quad[7]];
  const r = Math.round;
  const x0 = r(Math.max(0, Math.min(...xs))), y0 = r(Math.max(0, Math.min(...ys)));
  const x1 = r(Math.min(vw, Math.max(...xs))), y1 = r(Math.min(vh, Math.max(...ys)));
  return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
}

async function censorRegions(page, cfg, viewport) {
  const { root } = await page.cdp("DOM.getDocument", { depth: -1, pierce: true });
  const boxes = [];
  for (const { nodeId, parentId } of censorTextNodes(root, cfg.text, cfg.flags)) {
    let model = null;
    for (const id of [nodeId, parentId]) {
      model = await page.cdp("DOM.getBoxModel", { nodeId: id }).then((r) => r.model, () => null);
      if (model) break;
    }
    const box = model && quadBox(model.border, viewport);
    if (box) boxes.push(box);
  }
  return boxes;
}

// While a followed tab is recorded, its regions are refreshed every 400 ms: a changed set closes the previous
// one (t1) and opens the new one (t0) on the take clock.
function trackRegions(ctx, page) {
  const track = { current: null, busy: false, timer: null };
  const update = async () => {
    if (track.busy) return;
    track.busy = true;
    try {
      const boxes = await censorRegions(page, ctx.censorCfg, ctx.viewport).catch(() => null);
      if (!boxes) return;
      const key = JSON.stringify(boxes);
      if (track.current?.key === key) return;
      const now = ctx.rec.now();
      for (const item of track.current?.items || []) item.t1 = now;
      track.current = { key, items: boxes.map((box) => ({ t0: now, t1: null, box })) };
      ctx.regions.push(...track.current.items);
    } finally {
      track.busy = false;
    }
  };
  track.stop = () => {
    clearInterval(track.timer);
    const now = ctx.rec.now();
    for (const item of track.current?.items || []) item.t1 ??= now;
  };
  track.first = update().then(() => track.current?.items.length || 0);
  track.timer = setInterval(update, 400);
  return track;
}

// --- verified targets (N13) --------------------------------------------------------------------
// viewportPart ... findTarget also run inside the page (locateSource embeds them): they only use their
// arguments, each other and censorRanges. A target is ok when it is visible (box > 4x4 px, not display:none,
// visibility:hidden or opacity 0), in the viewport, and the element at its point is itself, a descendant or
// a tight (or interactive) ancestor. The text of a target never reaches an error message.

// The part of a box inside the viewport (> 4x4 px), or null.
export function viewportPart(box, [vw, vh]) {
  const x0 = Math.max(0, box.x), y0 = Math.max(0, box.y);
  const x1 = Math.min(vw, box.x + box.w), y1 = Math.min(vh, box.y + box.h);
  return x1 - x0 > 4 && y1 - y0 > 4 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
}

// {display, visibility, opacity (effective, ancestors included)}.
export function shownStyle(style) {
  return style.display !== "none" && style.visibility !== "hidden" && style.visibility !== "collapse"
    && Number(style.opacity) > 0;
}

// Where elementFromPoint is asked: the center of the visible part (a long table's center may be off screen).
export function hitPoint(box, viewport) {
  const part = viewportPart(box, viewport);
  return part ? { x: Math.round(part.x + part.w / 2), y: Math.round(part.y + part.h / 2) } : null;
}

// hit: {rel: self|descendant|ancestor|other|none, box, interactive} of the element found at hitPoint.
export function hitOk(hit, box) {
  if (!hit) return false;
  if (hit.rel === "self" || hit.rel === "descendant") return true;
  if (hit.rel !== "ancestor" || !hit.box) return false;
  return !!hit.interactive || hit.box.w * hit.box.h <= 4 * box.w * box.h;
}

export function targetOk({ box, style, viewport, hit }) {
  return !!box && box.w > 4 && box.h > 4 && shownStyle(style) && !!viewportPart(box, viewport) && hitOk(hit, box);
}

// Order in which matches are tried, hidden ones left out: in the viewport first, then interactive ones, then
// the smallest (text=, where ancestors match too) or document order (CSS, xpath).
export function rankTargets(cands, byArea = false) {
  const area = (c) => c.box.w * c.box.h;
  return cands.map((c, i) => i).filter((i) => cands[i].shown).sort((i, j) => {
    const a = cands[i], b = cands[j];
    return (b.inView - a.inView) || (b.interactive - a.interactive) || (byArea ? area(a) - area(b) : 0) || i - j;
  });
}

// target_text: the visible text, collapsed, <= 60 chars; null when empty, inside a blurred element or matching
// a censor pattern.
export function targetText(text, patterns, flags = "i", censored = false) {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  if (!t || censored || censorRanges(t, patterns || [], flags).length) return null;
  return t.length > 60 ? t.slice(0, 60) : t;
}

// The error that stops the take for a marked action whose target is not ok, else null.
export function targetFailure(stepId, ev) {
  const marked = ["click", "type", "select", "highlight", "result", "focus"];
  if (!marked.includes(ev.type) || ev.target_ok !== false) return null;
  return `Paso ${stepId}: el objetivo '${ev.selector}' no se ve donde se marca (oculto, vacío, fuera de la ` +
    "pantalla o tapado por otro elemento; N13). Usa un selector del elemento visible.";
}

function isInteractive(e) {
  return e.matches("a,button,input,select,textarea,label,summary,[role=button],[role=link],[role=tab],[role=menuitem],[onclick]");
}

// In the page: the elements a selector names (raw CSS, text=..., xpath=...). Throws on an invalid selector.
function matchTargets(sel) {
  if (sel.startsWith("text=")) {
    let q = sel.slice(5).trim();
    const exact = /^".*"$/.test(q);
    q = q.replace(/^"|"$/g, "");
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
    const els = [...document.querySelectorAll("body *")].filter((e) => {
      const text = norm(e.innerText || e.value || e.getAttribute("aria-label") || e.placeholder);
      return exact ? text === q : text.toLowerCase().includes(q.toLowerCase());
    });
    return { els, byArea: true };
  }
  if (sel.startsWith("xpath=")) {
    const snap = document.evaluate(sel.slice(6), document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    const els = [];
    for (let i = 0; i < snap.snapshotLength; i++) if (snap.snapshotItem(i).nodeType === 1) els.push(snap.snapshotItem(i));
    return { els, byArea: false };
  }
  return { els: [...document.querySelectorAll(sel)], byArea: false };
}

// In the page: {box, style, shown, inView, interactive} of an element.
function describeTarget(e) {
  const r = e.getBoundingClientRect();
  const box = { x: r.x, y: r.y, w: r.width, h: r.height };
  let opacity = 1;
  for (let p = e; p && p.nodeType === 1; p = p.parentElement || p.getRootNode().host || null) {
    opacity *= Number(getComputedStyle(p).opacity);
  }
  const st = getComputedStyle(e);
  const style = { display: st.display, visibility: st.visibility, opacity };
  return { box, style, shown: box.w > 4 && box.h > 4 && shownStyle(style),
    inView: !!viewportPart(box, [innerWidth, innerHeight]), interactive: isInteractive(e) };
}

// In the page: number of visible matches (-1: invalid selector). Used by wait and before every mark.
function shownTargets(sel) {
  try {
    return matchTargets(sel).els.filter((e) => describeTarget(e).shown).length;
  } catch (e) {
    return -1;
  }
}

// In the page: the verified target of a selector (null when nothing matches). Tries the ranked matches (scrolling
// each into view smoothly so the video shows the motion), retrying for a moment while an overlay fades; when
// none is ok, returns the best one with target_ok false. Also the boxes of its visible labels and ancestors
// (frameBox, formBox).
async function findTarget(sel, cfg) {
  const viewport = () => [innerWidth, innerHeight];
  const check = async (el) => {
    let info = describeTarget(el);
    const b0 = info.box;
    if (b0.y < 0 || b0.y + b0.h > innerHeight || b0.x < 0 || b0.x + b0.w > innerWidth) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      await new Promise((res) => setTimeout(res, 700));
      info = describeTarget(el);
    }
    const p = hitPoint(info.box, viewport());
    let hit = null;
    if (p) {
      const root = el.getRootNode();
      const h = (root.elementFromPoint ? root : document).elementFromPoint(p.x, p.y);
      const rel = !h ? "none" : h === el ? "self" : el.contains(h) ? "descendant" : h.contains(el) ? "ancestor" : "other";
      hit = { rel, box: h ? describeTarget(h).box : null, interactive: !!h && isInteractive(h) };
    }
    return { el, ok: targetOk({ box: info.box, style: info.style, viewport: viewport(), hit }) };
  };
  let best = null;
  for (let attempt = 0; attempt < 6; attempt++) {
    const { els, byArea } = matchTargets(sel);
    if (!els.length) break;
    const order = rankTargets(els.map(describeTarget), byArea).slice(0, 5);
    for (const i of order) {
      const c = await check(els[i]);
      if (c.ok) {
        best = c;
        break;
      }
      best ??= c;
    }
    if (best?.ok) break;
    best ??= { el: els[0], ok: false };
    await new Promise((res) => setTimeout(res, 300));
  }
  if (!best) return null;
  const el = best.el;
  const rect = (e) => {
    const d = describeTarget(e);
    return d.box.w > 0 && d.box.h > 0 && d.style.visibility !== "hidden" && d.style.display !== "none" ? d.box : null;
  };
  // label[for=id] / wrapping <label>; else the label or legend of the closest wrapper of this field only.
  let found = [...(el.labels || [])];
  if (!found.length && el.id) found = [...document.querySelectorAll(`label[for="${CSS.escape(el.id)}"]`)];
  const field = el.matches("input,select,textarea");
  for (let p = el.parentElement, depth = 0; field && !found.length && p && depth < 3; p = p.parentElement, depth++) {
    if (p.querySelectorAll("input,select,textarea").length > 1) break;
    found = [...p.querySelectorAll("label,legend")].filter((l) => !l.contains(el));
  }
  const labels = found.map(rect).filter(Boolean);
  const ancestors = [];
  for (let p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
    ancestors.push({ tag: p.tagName.toLowerCase(), role: p.getAttribute("role"), box: rect(p),
      fields: p.querySelectorAll("input:not([type=hidden]),select,textarea").length });
  }
  // A field's text is its label (its value may be a secret); a button input's is its value.
  const text = field && !/^(submit|button|reset)$/i.test(el.type || "")
    ? (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute("aria-label") || el.placeholder || ""
    : el.innerText || el.value || el.getAttribute("aria-label") || "";
  const censored = !!(el.closest("[data-tutorial-censor]") || el.querySelector("[data-tutorial-censor]"));
  const out = { box: describeTarget(el).box, labels, ancestors, target_ok: best.ok };
  const shownText = targetText(text, cfg.text || [], cfg.flags ?? "i", censored);
  if (shownText) out.target_text = shownText;
  return out;
}

const TARGET_FNS = [censorRanges, viewportPart, shownStyle, hitPoint, hitOk, targetOk, rankTargets, targetText,
  isInteractive, matchTargets, describeTarget, shownTargets, findTarget];

// Self-contained expression (Runtime.evaluate, awaitPromise) resolving to findTarget(sel, cfg). cfg: the censor
// patterns and flags (target_text is left out when it matches one).
export function locateSource(sel, cfg = {}) {
  const config = JSON.stringify({ text: cfg.text || [], flags: cfg.flags ?? "i" });
  return `(async () => {\n${TARGET_FNS.join("\n")}\nreturn await findTarget(${JSON.stringify(sel)}, ${config});\n})()`;
}

function shownSource(sel) {
  return `(() => {\n${TARGET_FNS.join("\n")}\nreturn shownTargets(${JSON.stringify(sel)});\n})()`;
}

// The tab a click opened: one not in `known` (target ids), the active one first.
export function pickNewTab(tabs, known) {
  const seen = new Set(known);
  const fresh = (tabs || []).filter((t) => t.targetId && !seen.has(t.targetId));
  return fresh.find((t) => t.active) || fresh[fresh.length - 1] || null;
}

// C9: framing a field includes its visible label. A label counts only while the union stays close
// to the control (a page heading or a legend spanning the form would zoom the camera out).
const LABEL_GROW_X = 480;
const LABEL_GROW_Y = 120;

// Union of the control box and its label boxes, clamped to the viewport, in whole pixels.
export function frameBox(control, labels, [vw, vh] = [1920, 1080]) {
  let x0 = control.x, y0 = control.y, x1 = control.x + control.w, y1 = control.y + control.h;
  for (const l of labels || []) {
    const nx0 = Math.min(x0, l.x), ny0 = Math.min(y0, l.y);
    const nx1 = Math.max(x1, l.x + l.w), ny1 = Math.max(y1, l.y + l.h);
    if (nx1 - nx0 > control.w + LABEL_GROW_X || ny1 - ny0 > control.h + LABEL_GROW_Y) continue;
    [x0, y0, x1, y1] = [nx0, ny0, nx1, ny1];
  }
  x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(vw, x1); y1 = Math.min(vh, y1);
  const r = Math.round;
  return { x: r(x0), y: r(y0), w: r(x1) - r(x0), h: r(y1) - r(y0) };
}

// N10: form framing. A form container is the closest form, fieldset, dialog or [role=dialog]; without one,
// the nearest ancestor holding >= 2 fields (a modal or card with several fields). `ancestors` goes from the
// element's parent up to (not including) body: [{tag, role, fields, box}], box null when not rendered.
const FORM_TAGS = new Set(["form", "fieldset", "dialog"]);

export function formBox(ancestors, [vw, vh] = [1920, 1080]) {
  const shown = (ancestors || []).filter((a) => a.box && a.box.w > 0 && a.box.h > 0 && a.tag !== "body" && a.tag !== "html");
  const hit = shown.find((a) => FORM_TAGS.has(a.tag) || a.role === "dialog") || shown.find((a) => a.fields >= 2);
  if (!hit) return null;
  const r = Math.round, b = hit.box;
  const x0 = r(Math.max(0, b.x)), y0 = r(Math.max(0, b.y));
  const x1 = r(Math.min(vw, b.x + b.w)), y1 = r(Math.min(vh, b.y + b.h));
  return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
}

// Runs a self-contained expression in the page's main world, awaiting it; throws on a script error.
async function evaluate(page, expression) {
  const r = await page.cdp("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r?.exceptionDetails) throw new Error("script error");
  return r?.result?.value;
}

// wait: until at least one match of the selector is visible (hidden duplicates do not count).
async function waitVisible(page, selector, timeout = 20000) {
  const source = shownSource(selector);
  const end = Date.now() + timeout;
  for (;;) {
    const n = await evaluate(page, source).catch(() => 0);   // 0 while the page navigates
    if (n === -1) throw new Error(`Selector no válido: ${selector}`);
    if (n > 0) return;
    if (Date.now() > end) throw new Error(`No apareció ningún elemento visible para ${selector}`);
    await sleep(250);
  }
}

// The verified target of a selector (findTarget) or null. Supports raw CSS, text=..., xpath=...
async function locate(page, selector, cfg = {}) {
  return await evaluate(page, locateSource(selector, cfg)).catch(() => null);
}

const center = (b) => ({ x: Math.round(b.x + b.w / 2), y: Math.round(b.y + b.h / 2) });

// Camera-only target (focus/result/highlight): wait until visible, log its box (N13: verified), no pointer.
async function markAt(page, rec, events, type, selector, cfg) {
  await waitVisible(page, selector).catch((err) => {
    throw /^Selector/.test(err.message) ? err
      : new Error(`ningún elemento visible para '${selector}' (oculto o vacío; N13). Usa un selector del elemento visible.`);
  });
  const found = await locate(page, selector, cfg);
  if (!found) throw new Error(`No encontré el elemento: ${selector}`);
  const ev = { type, t: rec.now(), selector, box: found.box, point: center(found.box), target_ok: found.target_ok };
  if (found.target_text) ev.target_text = found.target_text;
  if (type === "focus") {
    const fb = formBox(found.ancestors, await page.evaluate(() => [innerWidth, innerHeight]));
    if (fb) ev.form_box = fb;
  }
  events.push(ev);
}

// type/select/click also log frame_box = control + its visible label (C9) and form_box = its form (N10).
async function pointAt(page, rec, events, type, selector, label, cfg) {
  const found = await locate(page, selector, cfg);
  if (!found) throw new Error(`No encontré el elemento: ${selector}`);
  const { box } = found;
  const p = center(box);
  await page.mouse.move(p.x, p.y, { label });
  const ev = { type, t: rec.now(), selector, box, point: p, target_ok: found.target_ok };
  if (found.target_text) ev.target_text = found.target_text;
  if (type !== "hover") {
    const viewport = await page.evaluate(() => [innerWidth, innerHeight]);
    ev.frame_box = frameBox(box, found.labels, viewport);
    const fb = formBox(found.ancestors, viewport);
    if (fb) ev.form_box = fb;
  }
  events.push(ev);
  await sleep(250);
  return p;
}

// Runs a script in the page's main world (where the page's own scripts and chrome.* live).
async function inPage(page, source) {
  const r = await page.cdp("Runtime.evaluate", { expression: source, returnByValue: true });
  return r?.result?.value;
}

// Registered for every new document of `page` (reloads, navigations) and run once on the current one.
async function everyDocument(page, source) {
  await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source });
  await inPage(page, source).catch(() => {});
}

async function front(ctx) {
  await ctx.page.cdp("Page.bringToFront").catch(() => {});
}

// S5: the surface page opens hidden behind the main tab, gets its metrics, the tabs.query patch (before its
// own scripts run) and the censor, and starts recording on the shared clock. Returns the open time.
async function openSurface(ctx, name) {
  const spec = ctx.surfaces[name];
  if (!spec) throw new Error(`No existe la superficie '${name}' en surfaces`);
  const state = (ctx.state[name] ??= { windows: [], frames: [], takes: 0, current: null });
  if (state.current) throw new Error(`La superficie '${name}' ya está abierta`);
  const page = await ctx.task.newPage();
  ctx.known.add(page.targetId);
  const [w, h] = spec.size;
  await page.cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: spec.dpr ?? 1, mobile: false });
  const patch = tabsPatchSource(spec.target_tab ?? null);
  const hide = hideSource(spec.hide);   // N23: promotions hidden before the first frame and after every reload
  await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: patch });
  if (hide) await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: hide });
  if (ctx.censor) await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: ctx.censor });
  await page.goto(spec.url, { timeout: 20000 });
  await page.waitForLoadState("load").catch(() => {});
  // Already applied by the new-document script; repeated (idempotent) in case the page reloaded early.
  await inPage(page, patch).catch(() => {});
  if (hide) await inPage(page, hide).catch(() => {});
  if (ctx.censor) await inPage(page, ctx.censor).catch(() => {});
  await front(ctx);
  const rec = await startRecorder(page, `${ctx.outDir}/surfaces/${name}`,
    { t0: ctx.rec.t0, inflight: 2, prefix: `w${state.takes}_f`, clear: state.takes === 0, write: false });
  state.takes++;
  await sleep(300);   // the first surface frames exist before the panel is shown
  state.current = { page, rec, t0: ctx.rec.now() };
  return state.current.t0;
}

async function closeSurface(ctx, name) {
  const state = ctx.state[name];
  if (!state?.current) throw new Error(`La superficie '${name}' no está abierta`);
  const { page, rec, t0 } = state.current;
  const t1 = ctx.rec.now();
  await rec.stop();
  state.frames.push(...rec.frames);
  state.windows.push({ t0, t1 });
  state.current = null;
  await page.close().catch(() => {});
  await front(ctx);
  return t1;
}

// Closes what is still open and writes surfaces/<name>/frames.json. Returns actions.json `surfaces`.
async function finishSurfaces(ctx) {
  const out = {};
  for (const [name, spec] of Object.entries(ctx.surfaces)) {
    const state = ctx.state[name];
    if (state?.current) await closeSurface(ctx, name).catch(() => {});
    const frames = (state?.frames || []).sort((a, b) => a.t - b.t);
    if (state) {
      await fs.writeFile(`${ctx.outDir}/surfaces/${name}/frames.json`, JSON.stringify({ frames }, null, 1));
    }
    out[name] = { size: spec.size, dpr: spec.dpr ?? 1, anchor: spec.anchor ?? "top-right", dir: `surfaces/${name}`,
      windows: state?.windows || [], frames: frames.length };
  }
  return out;
}

// follow: tab. The tab the last click opened becomes the recorded one (same frames stream).
async function followTab(ctx) {
  let tab = null;
  for (let i = 0; i < 60 && !tab; i++) {
    tab = pickNewTab(await ctx.task.tabs(), ctx.known);
    if (!tab) await sleep(250);
  }
  if (!tab) throw new Error("No se abrió ninguna pestaña nueva para 'follow: tab'");
  const page = tab.label ? ctx.task.page(tab.label) : await ctx.task.adopt(tab.page);
  ctx.known.add(tab.targetId);
  const [w, h] = ctx.viewport;
  await page.cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false })
    .catch(() => {});
  await page.waitForLoadState("load").catch(() => {});
  // N25: the censor script (it walks open shadow roots); where no script runs (chrome://), the boxes of the
  // matching text are logged as censor_regions for compose. The regions are tracked in both cases: they also
  // catch what the script cannot reach (closed shadow roots). Returns the path that worked.
  let path = null;
  if (ctx.censor) {
    await everyDocument(page, ctx.censor).catch(() => {});
    const script = await inPage(page, "!!globalThis.__tutorialCensor").catch(() => false);
    path = script ? "script" : "regions";
    if (ctx.censorCfg.text.length) {
      ctx.track = trackRegions(ctx, page);
      const found = await ctx.track.first;
      if (found && script) path = "script+regions";
    } else if (!script) {
      throw new Error("No pude censurar la pestaña de 'follow: tab' (censor.selectors necesita el script; N25)");
    }
  }
  ctx.followed = page;
  ctx.page = page;
  await front(ctx);
  ctx.rec.setPage(page);
  return path;
}

async function backToMain(ctx) {
  const left = ctx.followed;
  ctx.followed = null;
  ctx.track?.stop();
  ctx.track = null;
  ctx.page = ctx.main;
  await front(ctx);
  ctx.rec.setPage(ctx.main);
  if (left) await left.close().catch(() => {});
}

// {in: SURFACE, sel} / {in, px} -> the surface page; a plain selector -> the recorded tab.
function where(ctx, arg, key = "sel") {
  if (arg && typeof arg === "object" && !Array.isArray(arg) && arg.in) {
    const current = ctx.state[arg.in]?.current;
    if (!current) throw new Error(`La superficie '${arg.in}' no está abierta`);
    return { page: current.page, sel: arg[key], surface: arg.in };
  }
  return { page: ctx.page, sel: arg, surface: null };
}

// Typing is captured fast on purpose: edit.py retimes it to 13.5 chars/s (C6).
// `target` is the main page, or a take context {task, main, page, rec, surfaces, state, ...} (take()).
export async function runSteps(target, rec, steps, { typeDelay = 10 } = {}) {
  const ctx = target.main ? target : { main: target, page: target, rec, surfaces: {}, state: {}, known: new Set() };
  const cfg = ctx.censorCfg || {};
  const log = [];
  for (const step of steps) {
    const entry = { id: step.id, t0: rec.now(), events: [] };
    ctx.step = step.id;   // take() names the step of a failure
    const ev = entry.events;
    // Pointer events inside a surface log its name: their boxes are in surface CSS px.
    const tag = (at) => {
      if (at.surface) ev.at(-1).surface = at.surface;
    };
    // N13: a marked target that is not visible where it is marked stops the take (before any click on it).
    const verify = () => {
      const failure = targetFailure(step.id, ev.at(-1));
      if (failure) throw new Error(failure);
    };
    for (const action of step.actions || []) {
      const [kind, arg] = Object.entries(action)[0];
      const page = ctx.page;
      switch (kind) {
        case "goto":
          await page.goto(arg, { timeout: 30000 });
          await page.waitForLoadState("load").catch(() => {});
          // No URL in the log: it may come from env:NAME and carry a token.
          ev.push({ type: "goto", t: rec.now() });
          break;
        case "click": {
          const at = where(ctx, arg);
          const p = await pointAt(at.page, rec, ev, "click", at.sel, `click ${at.sel}`.slice(0, 40), cfg);
          tag(at);
          verify();
          await at.page.mouse.click(p.x, p.y, { label: "click" });
          ev.at(-1).t = rec.now();
          if (at.surface) await front(ctx);
          await sleep(350);
          break;
        }
        case "hover": {
          const at = where(ctx, arg);
          await pointAt(at.page, rec, ev, "hover", at.sel, `hover ${at.sel}`.slice(0, 40), cfg);
          tag(at);
          if (at.surface) await front(ctx);
          await sleep(400);
          break;
        }
        case "type": {
          const p = await pointAt(page, rec, ev, "type", arg.into, `type into field`, cfg);
          verify();
          await page.mouse.click(p.x, p.y, { label: "focus field" });
          if (arg.clear) {
            await page.keyboard.press("ControlOrMeta+a");
            await page.keyboard.press("Backspace");
          }
          const text = [...String(arg.text)];
          // Length only: the text itself (it may be a secret) never reaches the log.
          ev.at(-1).chars = text.length;
          ev.at(-1).ts = rec.now();
          for (const ch of text) {
            await page.keyboard.type(ch);
            await sleep(typeDelay);
          }
          ev.at(-1).t_end = rec.now();
          if (arg.secret) ev.at(-1).secret = true;
          await sleep(200);
          break;
        }
        case "select":
          await pointAt(page, rec, ev, "select", arg.in, "choose option", cfg);
          verify();
          await page.selectOption(arg.in, arg.option);
          ev.at(-1).t = rec.now();
          await sleep(350);
          break;
        case "focus": {
          const at = where(ctx, arg);
          await markAt(at.page, rec, ev, "focus", at.sel, cfg);
          tag(at);
          verify();
          await sleep(400);
          break;
        }
        case "result":
        case "highlight": {
          const at = where(ctx, arg);
          await markAt(at.page, rec, ev, kind, at.sel, cfg);
          tag(at);
          verify();
          await sleep(300);
          break;
        }
        case "press":
          await page.keyboard.press(arg);
          ev.push({ type: "press", t: rec.now(), key: arg });
          await sleep(300);
          break;
        case "scroll": {
          const at = where(ctx, arg, "px");
          const dy = Number(at.sel);
          const [x, y] = at.surface ? ctx.surfaces[at.surface].size.map((v) => Math.round(v / 2)) : [960, 540];
          await at.page.mouse.move(x, y, { label: "scroll" });
          await at.page.mouse.wheel(0, dy, { label: "scroll page" });
          ev.push({ type: "scroll", t: rec.now(), dy });
          tag(at);
          if (at.surface) await front(ctx);
          await sleep(600);
          break;
        }
        case "wait": {
          // Any visible match: text= and xpath= also match hidden duplicates (the SRI side menu).
          const at = where(ctx, arg);
          await waitVisible(at.page, at.sel);
          break;
        }
        case "pause":
          await sleep(Number(arg));
          break;
        case "open":
          ev.push({ type: "open", t: await openSurface(ctx, arg), surface: arg });
          await sleep(400);
          break;
        case "close":
          ev.push({ type: "close", t: await closeSurface(ctx, arg), surface: arg });
          await sleep(300);
          break;
        case "follow": {
          const censor = await followTab(ctx);
          ev.push({ type: "goto", t: rec.now(), tab: "follow" });
          if (censor) ev.at(-1).censor = censor;   // N25: script | regions | script+regions
          await sleep(600);
          break;
        }
        case "back":
          await backToMain(ctx);
          ev.push({ type: "goto", t: rec.now(), tab: "main" });
          await sleep(600);
          break;
        default:
          throw new Error(`Acción desconocida '${kind}' en el paso ${step.id}`);
      }
    }
    await sleep(step.hold_ms ?? 600);
    entry.t1 = rec.now();
    log.push(entry);
    console.log(`[take] paso ${step.id} ok (${(entry.t1 - entry.t0).toFixed(1)} s)`);
  }
  return log;
}

// Full take: fixed viewport, censor injected before the first frame, record, run, write actions.json.
export async function take(task, { outDir, steps, viewport = [1920, 1080], startUrl, censor = null, surfaces = {} }) {
  const page = (await task.pages())[0] ?? (await task.newPage());
  await page.cdp("Emulation.setDeviceMetricsOverride", {
    width: viewport[0], height: viewport[1], deviceScaleFactor: 1, mobile: false,
  });
  const censorJs = censor && ((censor.selectors || []).length || (censor.text || []).length) ? censorSource(censor) : null;
  const censorCfg = { text: (censor && censor.text) || [], flags: (censor && censor.flags) ?? "i" };
  if (censorJs) await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: censorJs });
  if (startUrl) {
    await page.goto(startUrl, { timeout: 30000 });
    await page.waitForLoadState("load").catch(() => {});
  }
  if (censorJs) {
    await inPage(page, censorJs);
    // S3: never record a frame without the censor.
    if (!(await inPage(page, "!!globalThis.__tutorialCensor"))) throw new Error("No pude activar la censura en la página");
  }
  await fs.mkdir(outDir, { recursive: true });
  if (Object.keys(surfaces || {}).length) await fs.rm(`${outDir}/surfaces`, { recursive: true, force: true });
  const rec = await startRecorder(page, outDir);
  const known = new Set((await task.tabs()).map((t) => t.targetId));
  const ctx = { task, main: page, page, rec, outDir, viewport, censor: censorJs, censorCfg, surfaces: surfaces || {},
    state: {}, known, followed: null, track: null, regions: [] };
  let log = [];
  let failure = null;
  try {
    await sleep(800);
    log = await runSteps(ctx, rec, steps);
    await sleep(800);
  } catch (err) {
    failure = String(err?.message || err);
    if (ctx.step && !failure.startsWith("Paso ")) failure = `Paso ${ctx.step}: ${failure}`;
  }
  const surfaceLog = await finishSurfaces(ctx);
  ctx.track?.stop();
  const frames = await rec.stop();
  await page.cdp("Emulation.clearDeviceMetricsOverride").catch(() => {});
  const actions = { viewport, steps: log, failure };
  if (Object.keys(ctx.surfaces).length) actions.surfaces = surfaceLog;
  if (ctx.regions.length) actions.censor_regions = ctx.regions;   // N25: [{t0, t1, box}] blurred by compose
  await fs.writeFile(`${outDir}/actions.json`, JSON.stringify(actions, null, 1));
  console.log(JSON.stringify({ frames, steps: log.length, failure }));
  return { frames, failure };
}
