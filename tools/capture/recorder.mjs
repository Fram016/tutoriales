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

// Resolve a selector to a viewport box. Supports raw CSS, text=..., xpath=...
// Scrolls the element into view smoothly first so the video shows the motion.
async function locate(page, selector) {
  const box = await page.evaluate(async (sel) => {
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
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, selector);
  return box;
}

const center = (b) => ({ x: Math.round(b.x + b.w / 2), y: Math.round(b.y + b.h / 2) });

// Camera-only target (focus/result/highlight): wait until visible, log its box, no pointer.
async function markAt(page, rec, events, type, selector) {
  await page.waitForSelector(selector, { state: "visible", timeout: 20000 });
  const box = await locate(page, selector);
  if (!box) throw new Error(`No encontré el elemento: ${selector}`);
  events.push({ type, t: rec.now(), selector, box, point: center(box) });
}

async function pointAt(page, rec, events, type, selector, label) {
  const box = await locate(page, selector);
  if (!box) throw new Error(`No encontré el elemento: ${selector}`);
  const p = center(box);
  await page.mouse.move(p.x, p.y, { label });
  events.push({ type, t: rec.now(), selector, box, point: p });
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
