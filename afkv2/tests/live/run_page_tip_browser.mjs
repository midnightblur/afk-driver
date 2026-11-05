/** Run the page-tip fixture in installed Chrome through the local CDP endpoint. */

import { spawn } from "node:child_process";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WAIT_MS = 20_000;
const OPERATION_MS = 5_000;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const MAX_DIAGNOSTIC_BYTES = 1024 * 1024;

export function withDeadline(promise, timeout, label, cancel = () => {}) {
  let timer;
  const expired = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      cancel();
      reject(new Error(`Timed out waiting for ${label}`));
    }, timeout);
  });
  return Promise.race([promise, expired]).finally(() => clearTimeout(timer));
}

function chromeCandidates() {
  const values = [process.env.CHROME_PATH];
  if (process.platform === "win32") {
    for (const root of [process.env.PROGRAMFILES, process.env["PROGRAMFILES(X86)"], process.env.LOCALAPPDATA]) {
      if (root) values.push(path.join(root, "Google", "Chrome", "Application", "chrome.exe"));
    }
  } else if (process.platform === "darwin") {
    values.push("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
  } else {
    values.push("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/opt/google/chrome/chrome");
  }
  return [...new Set(values.filter(Boolean))];
}

async function findChrome() {
  for (const candidate of chromeCandidates()) {
    try {
      await access(candidate);
      return candidate;
    } catch {}
  }
  throw new Error(`Installed Chrome not found. Checked: ${chromeCandidates().join(", ")}`);
}

function boundedDiagnostic(text) {
  return text.length <= MAX_DIAGNOSTIC_BYTES ? text : `[truncated]\n${text.slice(-MAX_DIAGNOSTIC_BYTES)}`;
}

export function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const { timeout = WAIT_MS, ...spawnOptions } = options;
    const child = spawn(command, args, { windowsHide: true, ...spawnOptions });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      reject(new Error(`Timed out waiting for subprocess: ${command} ${args.join(" ")}\n${stdout}${stderr}`));
    }, timeout);
    child.stdout?.on("data", chunk => { stdout = boundedDiagnostic(stdout + chunk); });
    child.stderr?.on("data", chunk => { stderr = boundedDiagnostic(stderr + chunk); });
    child.on("error", error => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    });
    child.on("exit", code => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${command} ${args.join(" ")} exited ${code}\n${stdout}${stderr}`));
    });
  });
}

export function parseCdpMessage(data) {
  const text = String(data);
  if (text.length > MAX_RESPONSE_BYTES) throw new Error(`CDP message exceeded ${MAX_RESPONSE_BYTES} bytes`);
  return JSON.parse(text);
}

function getJson(port, route) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host: "127.0.0.1", port, path: route }, response => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", chunk => {
        body += chunk;
        if (body.length > MAX_RESPONSE_BYTES) response.destroy(new Error(`CDP ${route} exceeded ${MAX_RESPONSE_BYTES} bytes`));
      });
      response.on("error", reject);
      response.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(new Error(`CDP ${route} returned ${response.statusCode}: ${body}\n${error.message}`));
        }
      });
    });
    request.on("error", reject);
    request.setTimeout(OPERATION_MS, () => request.destroy(new Error(`Timed out waiting for CDP ${route}`)));
  });
}

async function until(label, action, accept, timeout = WAIT_MS) {
  const stop = Date.now() + timeout;
  let last;
  while (Date.now() < stop) {
    try {
      const remaining = stop - Date.now();
      last = await withDeadline(Promise.resolve().then(action), Math.min(OPERATION_MS, remaining), label);
      if (accept(last)) return last;
    } catch (error) {
      last = error;
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out waiting for ${label}: ${last instanceof Error ? last.message : JSON.stringify(last)}`);
}

class Cdp {
  constructor(url, diagnostics) {
    this.url = url;
    this.diagnostics = diagnostics;
    this.nextId = 0;
    this.pending = new Map();
  }

  async open() {
    this.socket = new WebSocket(this.url);
    this.socket.addEventListener("message", event => {
      let message;
      try {
        message = parseCdpMessage(event.data);
      } catch (error) {
        this.diagnostics.push(`CDP message: ${error.message}`);
        this.socket.close();
        return;
      }
      if (!message.id) return;
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
      else pending.resolve(message.result);
    });
    this.socket.addEventListener("close", () => {
      for (const pending of this.pending.values()) pending.reject(new Error("CDP socket closed"));
      this.pending.clear();
    });
    await withDeadline(new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", () => reject(new Error(`Cannot connect to ${this.url}`)), { once: true });
    }), OPERATION_MS, `CDP WebSocket ${this.url}`, () => this.socket.close());
  }

  call(method, params = {}) {
    const id = ++this.nextId;
    this.diagnostics.push(`${id} ${method}`);
    const answer = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
    return withDeadline(answer, OPERATION_MS, `CDP ${method}`, () => this.pending.delete(id));
  }

  close() {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.close();
  }
}

async function buildFixture(folder) {
  const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
  const builder = path.join(HERE, "page_tip_browser.py");
  const result = await run(python, [builder, "--output", folder]);
  const url = result.stdout.trim().split(/\r?\n/).at(-1);
  if (!url?.startsWith("file:")) throw new Error(`Fixture builder returned no file URL:\n${result.stdout}${result.stderr}`);
  return url;
}

async function stopChrome(browser, chrome, diagnostics) {
  try {
    await Promise.race([browser?.call("Browser.close"), new Promise(resolve => setTimeout(resolve, 1000))]);
  } catch (error) {
    diagnostics.push(`Browser.close: ${error.message}`);
  }
  browser?.close();
  if (chrome && chrome.exitCode === null) chrome.kill();
  if (chrome && chrome.exitCode === null) {
    await Promise.race([
      new Promise(resolve => chrome.once("exit", resolve)),
      new Promise(resolve => setTimeout(resolve, 3000)),
    ]);
  }
}

export async function runBrowserProof() {
  const scratch = await mkdtemp(path.join(os.tmpdir(), "afkv2-page-tip-"));
  const profile = path.join(scratch, "chrome-profile");
  const diagnostics = [];
  let chrome;
  let browser;
  let page;
  try {
    const fixture = await buildFixture(path.join(scratch, "fixture"));
    const executable = await findChrome();
    const args = [
      "--headless=new",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-sync",
      fixture,
    ];
    diagnostics.push(`launch: ${executable} ${args.join(" ")}`);
    chrome = spawn(executable, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    chrome.stdout.on("data", chunk => diagnostics.push(`chrome stdout: ${chunk}`.trim()));
    chrome.stderr.on("data", chunk => diagnostics.push(`chrome stderr: ${chunk}`.trim()));
    chrome.on("error", error => diagnostics.push(`chrome error: ${error.message}`));

    const active = path.join(profile, "DevToolsActivePort");
    const endpoint = await until("Chrome DevToolsActivePort", async () => (await readFile(active, "utf8")).trim().split(/\r?\n/), value => value.length >= 2);
    const port = Number(endpoint[0]);
    browser = new Cdp(`ws://127.0.0.1:${port}${endpoint[1]}`, diagnostics);
    await browser.open();

    const targets = await until("fixture page target", () => getJson(port, "/json/list"), list => list.some(item => item.type === "page" && item.url === fixture));
    const target = targets.find(item => item.type === "page" && item.url === fixture);
    page = new Cdp(target.webSocketDebuggerUrl, diagnostics);
    await page.open();
    await page.call("Runtime.enable");
    await page.call("Runtime.evaluate", { expression: "document.getElementById('run').click()" });
    const proof = await until("browser proof result", async () => {
      const result = await page.call("Runtime.evaluate", {
        expression: "document.getElementById('result').textContent",
        returnByValue: true,
      });
      return result.result.value;
    }, value => value.startsWith("PASS ALL") || value.startsWith("FAIL:"), 30_000);
    if (!proof.startsWith("PASS ALL")) throw new Error(proof);
    console.log(proof);
  } catch (error) {
    throw new Error(`${error.stack || error.message}\n\nDiagnostics:\n${diagnostics.join("\n")}`);
  } finally {
    page?.close();
    await stopChrome(browser, chrome, diagnostics);
    await rm(scratch, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runBrowserProof().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
