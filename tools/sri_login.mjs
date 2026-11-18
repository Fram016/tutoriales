// Logs in to SRI en línea in an ego-browser task space using credentials from a project's
// acceso.local.yaml (keys <PREFIX>_SRI_USER / <PREFIX>_SRI_PASSWORD). Values are never printed.
// Usage: ego-browser nodejs -e "await import('file:///.../tools/sri_login.mjs')"  with env-free config below,
// or import { sriLogin } and call it from another ego script.
const fs = await import("node:fs/promises");

export async function readAccess(file, prefix) {
  const text = await fs.readFile(file, "utf-8");
  const get = (k) => (text.match(new RegExp(`^${prefix}_${k}:\\s*"(.*)"\\s*$`, "m")) || [])[1];
  const user = get("SRI_USER");
  const password = get("SRI_PASSWORD");
  if (!user || !password) throw new Error(`Faltan ${prefix}_SRI_USER / ${prefix}_SRI_PASSWORD en acceso.local.yaml`);
  return { user, password };
}

export const isLoginPage = async (page) => /login/i.test(await page.title()) || /\/auth\/realms\//.test(await page.url());

// Returns {loggedIn, wasLogin}. Never logs the credential values.
export async function sriLogin(page, creds, { returnUrl } = {}) {
  if (!(await isLoginPage(page))) return { loggedIn: true, wasLogin: false };
  await page.waitForSelector("input[type=password]", { state: "visible", timeout: 20000 });
  const userSel = await page.evaluate(() => {
    const inputs = [...document.querySelectorAll("input:not([type=hidden]):not([type=password])")]
      .filter((i) => i.offsetParent !== null);
    const u = inputs.find((i) => /usuario|user|ruc|username/i.test(i.id + i.name)) || inputs[0];
    return u ? (u.id ? `#${CSS.escape(u.id)}` : `input[name="${u.name}"]`) : null;
  });
  if (!userSel) throw new Error("No encontré el campo de usuario del login del SRI");
  await page.fill(userSel, creds.user, { clearFirst: true });
  await page.fill("input[type=password]", creds.password, { clearFirst: true });
  const submit = await page.evaluate(() => {
    const b = document.querySelector("#kc-login, input[type=submit], button[type=submit]");
    return b ? (b.id ? `#${CSS.escape(b.id)}` : (b.tagName === "BUTTON" ? "button[type=submit]" : "input[type=submit]")) : null;
  });
  if (submit) await page.click(submit, { label: "ingresar al SRI" });
  else await page.press("input[type=password]", "Enter");
  await page.waitForFunction(() => !/\/auth\/realms\//.test(location.href), undefined, { timeout: 30000 }).catch(() => {});
  if (returnUrl) await page.goto(returnUrl, { timeout: 45000 }).catch(() => {});
  return { loggedIn: !(await isLoginPage(page)), wasLogin: true };
}
