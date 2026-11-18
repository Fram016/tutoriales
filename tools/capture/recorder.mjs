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

// Merged [start, end) ranges of `text` matched by any pattern (case-insensitive regex sources).
export function censorRanges(text, patterns) {
  const found = [];
  for (const pattern of patterns || []) {
    const re = new RegExp(pattern, "gi");
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
export function wrapTextNode(doc, node, patterns) {
  const parent = node.parentElement;
  if (!parent || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TEXTAREA|TITLE)$/.test(parent.tagName)
      || parent.getAttribute("data-tutorial-censor") === "text") return 0;
  const text = node.nodeValue || "";
  if (!text.trim()) return 0;
  const ranges = censorRanges(text, patterns);
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
  const patterns = cfg.text || [];
  const selectors = (cfg.selectors || []).join(", ");
  const blur = (el, why) => {
    if (!el.hasAttribute(MARK)) el.setAttribute(MARK, why);
    el.style.setProperty("filter", "blur(8px)", "important");
    el.style.setProperty("user-select", "none", "important");
  };
  const shown = (el) => (el.tagName === "SELECT" ? (el.options[el.selectedIndex] || {}).text || "" : String(el.value ?? ""));
  const value = (el) => {
    if (!patterns.length) return;
    if (censorRanges(shown(el), patterns).length) blur(el, "value");
    else if (el.getAttribute(MARK) === "value") {
      el.removeAttribute(MARK);
      el.style.removeProperty("filter");
      el.style.removeProperty("user-select");
    }
  };
  const scan = (root) => {
    if (root.nodeType === 3) {
      wrapTextNode(doc, root, patterns);
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
    if (!patterns.length) return;
    const walker = doc.createTreeWalker(root, 4);
    const nodes = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
    for (const n of nodes) wrapTextNode(doc, n, patterns);
    if (root.matches && root.matches(FIELDS)) value(root);
    if (root.querySelectorAll) root.querySelectorAll(FIELDS).forEach(value);
  };
  let observer = null;
  const watch = () => observer.observe(doc, { childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["class", "id", "value"] });
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
  const timer = patterns.length ? g.setInterval(() => apply(() => doc.querySelectorAll(FIELDS).forEach(value)), 150) : null;
  g.__tutorialCensor = {
    key,
    apply: all,
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
  text.forEach((pattern, i) => {
    try {
      new RegExp(pattern, "gi");
    } catch {
      throw new Error(`censor.text[${i}] no es una expresión regular válida`);
    }
  });
  const config = JSON.stringify({ selectors: cfg.selectors || [], text });
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

// Resolve a selector to a viewport box (+ the boxes of its visible labels and its ancestors for formBox). Supports raw CSS,
// text=..., xpath=... Scrolls the element into view smoothly first so the video shows the motion.
async function locate(page, selector) {
  return await page.evaluate(async (sel) => {
    let el = null;
    if (sel.startsWith("text=")) {
      let q = sel.slice(5).trim();
      const exact = /^".*"$/.test(q);
      q = q.replace(/^"|"$/g, "");
      const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
      const all = [...document.querySelectorAll("body *")].filter((e) => {
        const r = e.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        const text = norm(e.innerText || e.value || e.getAttribute("aria-label") || e.placeholder);
        return exact ? text === q : text.toLowerCase().includes(q.toLowerCase());
      });
      const interactive = (e) => e.matches("a,button,input,select,textarea,label,[role=button],[role=link],[role=tab],[role=menuitem],[onclick]");
      all.sort((a, b) => (interactive(b) - interactive(a)) ||
        (a.getBoundingClientRect().width * a.getBoundingClientRect().height) -
        (b.getBoundingClientRect().width * b.getBoundingClientRect().height));
      el = all[0] || null;
    } else if (sel.startsWith("xpath=")) {
      el = document.evaluate(sel.slice(6), document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    } else {
      el = document.querySelector(sel);
    }
    if (!el) return null;
    const r0 = el.getBoundingClientRect();
    if (r0.top < 0 || r0.bottom > innerHeight || r0.left < 0 || r0.right > innerWidth) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      await new Promise((res) => setTimeout(res, 700));
    }
    const rect = (e) => {
      const q = e.getBoundingClientRect();
      const st = getComputedStyle(e);
      if (q.width === 0 || q.height === 0 || st.visibility === "hidden" || st.display === "none") return null;
      return { x: q.x, y: q.y, w: q.width, h: q.height };
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
    const r = el.getBoundingClientRect();
    return { box: { x: r.x, y: r.y, w: r.width, h: r.height }, labels, ancestors };
  }, selector);
}

const center = (b) => ({ x: Math.round(b.x + b.w / 2), y: Math.round(b.y + b.h / 2) });

// Camera-only target (focus/result/highlight): wait until visible, log its box, no pointer.
async function markAt(page, rec, events, type, selector) {
  await page.waitForSelector(selector, { state: "visible", timeout: 20000 });
  const found = await locate(page, selector);
  if (!found) throw new Error(`No encontré el elemento: ${selector}`);
  const ev = { type, t: rec.now(), selector, box: found.box, point: center(found.box) };
  if (type === "focus") {
    const fb = formBox(found.ancestors, await page.evaluate(() => [innerWidth, innerHeight]));
    if (fb) ev.form_box = fb;
  }
  events.push(ev);
}

// type/select/click also log frame_box = control + its visible label (C9) and form_box = its form (N10).
async function pointAt(page, rec, events, type, selector, label) {
  const found = await locate(page, selector);
  if (!found) throw new Error(`No encontré el elemento: ${selector}`);
  const { box } = found;
  const p = center(box);
  await page.mouse.move(p.x, p.y, { label });
  const ev = { type, t: rec.now(), selector, box, point: p };
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
  await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: patch });
  if (ctx.censor) await page.cdp("Page.addScriptToEvaluateOnNewDocument", { source: ctx.censor });
  await page.goto(spec.url, { timeout: 20000 });
  await page.waitForLoadState("load").catch(() => {});
  // Already applied by the new-document script; repeated (idempotent) in case the page reloaded early.
  await inPage(page, patch).catch(() => {});
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
  if (ctx.censor) await everyDocument(page, ctx.censor).catch(() => {});
  ctx.followed = page;
  ctx.page = page;
  await front(ctx);
  ctx.rec.setPage(page);
}

async function backToMain(ctx) {
  const left = ctx.followed;
  ctx.followed = null;
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
  const log = [];
  for (const step of steps) {
    const entry = { id: step.id, t0: rec.now(), events: [] };
    const ev = entry.events;
    // Pointer events inside a surface log its name: their boxes are in surface CSS px.
    const tag = (at) => {
      if (at.surface) ev.at(-1).surface = at.surface;
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
          const p = await pointAt(at.page, rec, ev, "click", at.sel, `click ${at.sel}`.slice(0, 40));
          tag(at);
          await at.page.mouse.click(p.x, p.y, { label: "click" });
          ev.at(-1).t = rec.now();
          if (at.surface) await front(ctx);
          await sleep(350);
          break;
        }
        case "hover": {
          const at = where(ctx, arg);
          await pointAt(at.page, rec, ev, "hover", at.sel, `hover ${at.sel}`.slice(0, 40));
          tag(at);
          if (at.surface) await front(ctx);
          await sleep(400);
          break;
        }
        case "type": {
          const p = await pointAt(page, rec, ev, "type", arg.into, `type into field`);
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
          await pointAt(page, rec, ev, "select", arg.in, "choose option");
          await page.selectOption(arg.in, arg.option);
          ev.at(-1).t = rec.now();
          await sleep(350);
          break;
        case "focus": {
          const at = where(ctx, arg);
          await markAt(at.page, rec, ev, "focus", at.sel);
          tag(at);
          await sleep(400);
          break;
        }
        case "result":
        case "highlight": {
          const at = where(ctx, arg);
          await markAt(at.page, rec, ev, kind, at.sel);
          tag(at);
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
          const at = where(ctx, arg);
          await at.page.waitForSelector(at.sel, { state: "visible", timeout: 20000 });
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
        case "follow":
          await followTab(ctx);
          ev.push({ type: "goto", t: rec.now(), tab: "follow" });
          await sleep(600);
          break;
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
  const ctx = { task, main: page, page, rec, outDir, viewport, censor: censorJs, surfaces: surfaces || {}, state: {},
    known, followed: null };
  let log = [];
  let failure = null;
  try {
    await sleep(800);
    log = await runSteps(ctx, rec, steps);
    await sleep(800);
  } catch (err) {
    failure = String(err?.message || err);
  }
  const surfaceLog = await finishSurfaces(ctx);
  const frames = await rec.stop();
  await page.cdp("Emulation.clearDeviceMetricsOverride").catch(() => {});
  const actions = { viewport, steps: log, failure };
  if (Object.keys(ctx.surfaces).length) actions.surfaces = surfaceLog;
  await fs.writeFile(`${outDir}/actions.json`, JSON.stringify(actions, null, 1));
  console.log(JSON.stringify({ frames, steps: log.length, failure }));
  return { frames, failure };
}
