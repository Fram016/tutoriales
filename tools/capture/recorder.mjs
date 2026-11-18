// Frame recorder + step runner for ego-lite (imported by the generated take.mjs).
//
// ego-lite blocks Page.screencastFrameAck, so CDP screencast stalls after one frame.
// Instead we keep N Page.captureScreenshot requests in flight (~10 fps at 1080p) and
// stamp each frame. Every action is logged with its time, element box and pointer
// position, so the editor can cut, zoom and draw a synthetic cursor exactly.

const fs = await import("node:fs/promises");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function startRecorder(page, outDir, { inflight = 3, quality = 88 } = {}) {
  const framesDir = `${outDir}/frames`;
  await fs.rm(framesDir, { recursive: true, force: true });
  await fs.mkdir(framesDir, { recursive: true });
  const t0 = Date.now();
  const frames = [];
  let seq = 0;
  let running = true;
  let errors = 0;
  const worker = async () => {
    while (running) {
      const tReq = Date.now();
      try {
        const r = await page.cdp("Page.captureScreenshot", { format: "jpeg", quality, optimizeForSpeed: true });
        const t = ((tReq + Date.now()) / 2 - t0) / 1000;
        const name = `f${String(seq++).padStart(6, "0")}.jpg`;
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
    now: () => (Date.now() - t0) / 1000,
    async stop() {
      running = false;
      await Promise.all(workers);
      frames.sort((a, b) => a.t - b.t);
      await fs.writeFile(`${outDir}/frames.json`, JSON.stringify({ frames, errors }, null, 1));
      return frames.length;
    },
  };
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

// Typing is captured fast on purpose: edit.py retimes it to 13.5 chars/s (C6).
export async function runSteps(page, rec, steps, { typeDelay = 10 } = {}) {
  const log = [];
  for (const step of steps) {
    const entry = { id: step.id, t0: rec.now(), events: [] };
    const ev = entry.events;
    for (const action of step.actions || []) {
      const [kind, arg] = Object.entries(action)[0];
      switch (kind) {
        case "goto":
          await page.goto(arg, { timeout: 30000 });
          await page.waitForLoadState("load").catch(() => {});
          // No URL in the log: it may come from env:NAME and carry a token.
          ev.push({ type: "goto", t: rec.now() });
          break;
        case "click": {
          const p = await pointAt(page, rec, ev, "click", arg, `click ${arg}`.slice(0, 40));
          await page.mouse.click(p.x, p.y, { label: "click" });
          ev.at(-1).t = rec.now();
          await sleep(350);
          break;
        }
        case "hover":
          await pointAt(page, rec, ev, "hover", arg, `hover ${arg}`.slice(0, 40));
          await sleep(400);
          break;
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
        case "focus":
          await markAt(page, rec, ev, "focus", arg);
          await sleep(400);
          break;
        case "result":
        case "highlight":
          await markAt(page, rec, ev, kind, arg);
          await sleep(300);
          break;
        case "press":
          await page.keyboard.press(arg);
          ev.push({ type: "press", t: rec.now(), key: arg });
          await sleep(300);
          break;
        case "scroll": {
          await page.mouse.move(960, 540, { label: "scroll" });
          await page.mouse.wheel(0, Number(arg), { label: "scroll page" });
          ev.push({ type: "scroll", t: rec.now(), dy: Number(arg) });
          await sleep(600);
          break;
        }
        case "wait":
          await page.waitForSelector(arg, { state: "visible", timeout: 20000 });
          break;
        case "pause":
          await sleep(Number(arg));
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

// Full take: fixed viewport, record, run, write actions.json.
export async function take(task, { outDir, steps, viewport = [1920, 1080], startUrl }) {
  const page = (await task.pages())[0] ?? (await task.newPage());
  await page.cdp("Emulation.setDeviceMetricsOverride", {
    width: viewport[0], height: viewport[1], deviceScaleFactor: 1, mobile: false,
  });
  if (startUrl) {
    await page.goto(startUrl, { timeout: 30000 });
    await page.waitForLoadState("load").catch(() => {});
  }
  await fs.mkdir(outDir, { recursive: true });
  const rec = await startRecorder(page, outDir);
  let log = [];
  let failure = null;
  try {
    await sleep(800);
    log = await runSteps(page, rec, steps);
    await sleep(800);
  } catch (err) {
    failure = String(err?.message || err);
  }
  const frames = await rec.stop();
  await page.cdp("Emulation.clearDeviceMetricsOverride").catch(() => {});
  await fs.writeFile(`${outDir}/actions.json`, JSON.stringify({ viewport, steps: log, failure }, null, 1));
  console.log(JSON.stringify({ frames, steps: log.length, failure }));
  return { frames, failure };
}
