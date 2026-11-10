# Page live test

An agent runs this test. It needs Edge, Node 22 or later and a folder that holds `lavish-axi@0.1.81`. It proves AC-042 and the seam row "lavish host": a page with many notes, long text, wide tables, many rounds and big diagrams hides nothing and cuts nothing off, and every control works in a real browser through the real host. The shell steps prove the page shell (AC-015, AC-020, AC-021, AC-026, AC-027, AC-035, AC-039, AC-040) and the seam row "Page host" (AC-036) on a page of their own.

## Rules

- Install `lavish-axi@0.1.81` with `npm install --ignore-scripts` in a scratch folder. Search that folder for `.exe` and `.dll`. If one appears, delete it, and stop.
- Do not install `playwright-core`. Its install brings an `.exe`. The driver below speaks the Chrome DevTools Protocol to the installed Edge through the `WebSocket` of Node.
- The host runs on its own port with its own state folder. Do not touch the shared host and do not set `LAVISH_AXI_HOST`.
- The driver closes Edge and ends its sessions. Remove the scratch folder after the host stops.

## Run

1. Make an empty scratch folder. Install the host in `<scratch>/lavish`.
2. Save the block under "Driver" as `<scratch>/live.mjs`.
3. Run it, with these variables:

| Variable | Value |
|---|---|
| `AFKV2_LIVE_ROOT` | the `afkv2` folder of the plugin |
| `AFKV2_LIVE_SCRATCH` | the scratch folder |
| `AFKV2_LIVE_PYTHON` | a Python interpreter, full path |
| `AFKV2_LIVE_PORT` | a free port, default 47395 |
| `AFKV2_LIVE_EDGE` | `msedge.exe`, full path |

4. Read `<scratch>/live-result.json`. Look at each screenshot in `<scratch>/shots`.

The test passes when the driver exits 0 and no screenshot shows content that is cut off or hidden.

## What the driver does

| Step | Pass rule |
|---|---|
| layout | At 1280 and at 390 wide, all cards expanded: the page does not scroll sideways; no text is clipped; nothing outside a scroll area is past the edge; no 2 map boxes overlap |
| title | The browser tab and the heading read `<ticket> · <short title> · <step>`, and the next round keeps it |
| navigation | At 1280 the navigation ends left of the page; at 390 it is one button whose list opens on a click and closes after a jump; a collapsed navigation stays collapsed on the next round |
| back | With the host's Annotate switch off, a card link and a map box each scroll to their card; one click on Back returns to the place before the jump |
| map box | The box's hover tip names the card's state and the round of its last change |
| what changed | After round 1 the banner lists the changed card with a link, and only that card has a round mark |
| tab reuse | A second show of an open page answers `tab: reused` with the same URL; the open tab shows the new round and the browser has no new tab |
| closed tab | After the tab closes, `poll` reports that the browser left, and the next show answers `tab: null`: the engine asks the host for a new tab. The host runs with `LAVISH_AXI_NO_OPEN`, so the driver opens that one tab itself |
| host audit | The severe findings of the host's layout audit, on the full page and on a page of only diagrams, are in the result. A finding fails the test |
| mark | A real click on a radio selects it, and the host queue holds its mark |
| note | In annotation mode, a real click opens the host's note card; typed text and Queue queue one note on a card, a map node, a settled item, a diagram and a freestyle fragment |
| cancel | A note card closed with Cancel queues nothing, and its text is not sent |
| collapse | A closed older round of notes and a settled card fold and unfold |
| re-render | A reply added and rendered while notes are unsent: the page reloads, the host queue is the same and the mark is still there |
| send | The host's Send to Agent takes the batch; the host queue is empty after |
| seam | The prompts the host queue held are the prompts `poll` reads; the raw response `poll` builds and what `ingest` stored are the same bytes |
| ingest | Each state and note in the document is what the mark table says |
| continue | A new round on the same tab works to `ingest` again |
| reopen | After `end`, `show` opens the saved session and its notes are there |

Every click finds its point with `elementFromPoint`, so a control that something covers fails.

## Driver

```js
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const ROOT = process.env.AFKV2_LIVE_ROOT;
const SCRATCH = process.env.AFKV2_LIVE_SCRATCH;
const PYTHON = process.env.AFKV2_LIVE_PYTHON;
const EDGE = process.env.AFKV2_LIVE_EDGE;
const PORT = process.env.AFKV2_LIVE_PORT || '47395';
const ENGINE = path.join(ROOT, 'engine', 'engine.py');
const SHOTS = path.join(SCRATCH, 'shots');
const PROFILE = path.join(SCRATCH, 'edge-profile');
const NO_CHOICE = '\u2014';
const TRICKY = 'C:\\Users\\x "quoted" a | b \u00e9 \u4e2d\u6587 $HOME `tick`\nsecond line\n\n  third\ttab \\\\double';
const pause = (ms) => new Promise((done) => setTimeout(done, ms));
const result = { steps: [], layout: {}, audit: {}, frame: {} };

const started = Date.now();
function step(name, ok, detail) {
  result.steps.push({ name, ok: !!ok, detail });
  console.log(`${String(Math.round((Date.now() - started) / 1000)).padStart(4)}s ${ok ? 'ok  ' : 'FAIL'} ${name}${detail === undefined ? '' : ' ' + JSON.stringify(detail).slice(0, 400)}`);
  if (!ok) throw new Error(`step failed: ${name}`);
}

const env = { ...process.env, LOCALAPPDATA: path.join(SCRATCH, 'local'), LAVISH_AXI_PORT: PORT,
  LAVISH_AXI_STATE_DIR: path.join(SCRATCH, 'state'), LAVISH_AXI_NO_OPEN: '1', LAVISH_AXI_IDLE_TIMEOUT_MS: '45000',
  PATH: `${path.join(SCRATCH, 'lavish', 'node_modules', '.bin')}${path.delimiter}${process.env.PATH}` };
delete env.LAVISH_AXI_HOST;
delete env.CODEX_THREAD_ID;

function run(args) {
  const done = spawnSync(PYTHON, args, { env, encoding: 'utf-8', timeout: 120000 });
  return done;
}

function engine(...args) {
  const done = run([ENGINE, ...args]);
  let answer;
  try { answer = JSON.parse(done.stdout); } catch (e) { throw new Error(`engine ${args[0]}: ${done.stdout}${done.stderr}`); }
  return answer;
}

function endSession(json) {
  const script = "import sys; sys.path[:0] = sys.argv[1:3]; import launcher; print(launcher.run(['end', sys.argv[3]]))";
  return run(['-c', script, path.join(ROOT, 'engine'), path.join(ROOT, 'scripts'), json.replace(/\.json$/, '.html')]).stdout;
}

class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.waiting = new Map(); this.contexts = new Map(); this.sessions = new Set();
    ws.addEventListener('message', (event) => this.receive(JSON.parse(event.data)));
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    return new Promise((resolve, reject) => this.waiting.set(id, { resolve, reject, method }));
  }
  receive(message) {
    if (message.id) {
      const entry = this.waiting.get(message.id);
      this.waiting.delete(message.id);
      if (message.error) entry.reject(new Error(`${entry.method}: ${message.error.message}`));
      else entry.resolve(message.result);
      return;
    }
    const { method, params, sessionId } = message;
    if (method === 'Target.attachedToTarget') this.attach(params.sessionId);
    if (method === 'Target.detachedFromTarget') {
      this.sessions.delete(params.sessionId);
      for (const [key, value] of this.contexts) if (value.sessionId === params.sessionId) this.contexts.delete(key);
    }
    if (method === 'Runtime.executionContextCreated' && params.context.auxData && params.context.auxData.isDefault) {
      this.contexts.set(`${sessionId}:${params.context.id}`, { sessionId, id: params.context.id, frameId: params.context.auxData.frameId });
    }
    if (method === 'Runtime.executionContextDestroyed') this.contexts.delete(`${sessionId}:${params.executionContextId}`);
    if (method === 'Runtime.executionContextsCleared') {
      for (const [key, value] of this.contexts) if (value.sessionId === sessionId) this.contexts.delete(key);
    }
  }
  attach(sessionId) {
    this.sessions.add(sessionId);
    /* A sandboxed frame may run in a process of its own and arrive as its own target. */
    this.send('Runtime.enable', {}, sessionId).catch(() => {});
    this.send('Page.enable', {}, sessionId).catch(() => {});
    this.send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }, sessionId).catch(() => {});
  }
  async value(context, expression) {
    /* A frame of a page the tab has left can stay frozen and never answer. */
    const answer = await Promise.race([
      this.send('Runtime.evaluate', { expression, contextId: context.id, returnByValue: true, awaitPromise: true }, context.sessionId),
      pause(5000).then(() => { throw new Error('context not answering'); }),
    ]);
    if (answer.exceptionDetails) throw new Error(`${expression.slice(0, 200)}: ${JSON.stringify(answer.exceptionDetails).slice(0, 400)}`);
    return answer.result.value;
  }
}

let cdp, top, topTarget, frameContext, edge, frameKey = '/artifact/';
process.on('exit', () => { if (edge) edge.kill(); });

async function findFrame() {
  for (const context of cdp.contexts.values()) {
    const href = await cdp.value(context, 'location.href').catch(() => '');
    if (href.includes(frameKey)) return context;
  }
  return null;
}

async function ev(expression) {
  for (let tries = 0; tries < 300; tries += 1) {
    if (!frameContext || ![...cdp.contexts.values()].includes(frameContext)) frameContext = await findFrame();
    if (frameContext) {
      try { return await cdp.value(frameContext, expression); } catch (e) {
        if (!/context|navigat|destroyed|not found|session/i.test(e.message)) throw e;
        frameContext = null;
      }
    }
    await pause(100);
  }
  throw new Error('the page frame did not load');
}

async function until(expression, what) {
  for (let tries = 0; tries < 300; tries += 1) {
    if (await ev(expression)) return;
    await pause(100);
  }
  throw new Error(`timed out: ${what}`);
}

async function topValue(expression) {
  for (const context of cdp.contexts.values()) {
    if (context.sessionId !== top) continue;
    const frameless = await cdp.value(context, 'window === window.top').catch(() => false);
    if (frameless) return cdp.value(context, expression);
  }
  throw new Error('no top frame');
}

async function frameOffset() {
  return topValue(`(() => { const f = [...document.querySelectorAll('iframe')].find((x) => (x.src || '').includes('/artifact/')) || document.querySelector('iframe'); const r = f.getBoundingClientRect(); return { x: r.left + f.clientLeft, y: r.top + f.clientTop }; })()`);
}

/* The host covers a frame with its own overlay while its audit runs. */
async function frameOnTop() {
  for (let tries = 0; tries < 600; tries += 1) {
    const clear = await topValue(`(() => { const f = [...document.querySelectorAll('iframe')].find((x) => (x.src || '').includes('/artifact/')) || document.querySelector('iframe'); if (!f || getComputedStyle(f).opacity !== '1') return false; const r = f.getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === f; })()`).catch(() => false);
    if (clear) return;
    await pause(100);
  }
  throw new Error('the host overlay stayed on the page');
}

async function press(at) {
  const point = { x: at.x, y: at.y, button: 'left', clickCount: 1 };
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y }, top);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point }, top);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point }, top);
  await pause(60);
}

/* lavish draws its annotation card in an open shadow root; `inCard` finds the selector there. */
const CARD_ROOT = `document.querySelector('.lavish-annotation-root')`;
const scope = (inCard) => (inCard ? `(${CARD_ROOT} ? ${CARD_ROOT}.shadowRoot : null)` : 'document');

async function click(selector, inCard = false) {
  await frameOnTop();
  const expression = `(() => {
    const root = ${scope(inCard)};
    const el = root && root.querySelector(${JSON.stringify(selector)});
    if (!el) return { missing: true };
    if (!${inCard}) el.scrollIntoView({ block: 'center', inline: 'center' });
    const r = el.getBoundingClientRect();
    const x = r.left + Math.min(r.width / 2, 40), y = r.top + r.height / 2;
    const hit = root.elementFromPoint(x, y);
    return { x, y, covered: !hit || !(hit === el || el.contains(hit) || hit.contains(el)), hit: hit && hit.tagName };
  })()`;
  const point = await ev(expression);
  if (point.missing) throw new Error(`no element: ${selector}`);
  if (point.covered) throw new Error(`covered: ${selector}, by ${point.hit}`);
  const offset = await frameOffset();
  await press({ x: point.x + offset.x, y: point.y + offset.y });
}

async function type(selector, text, inCard = false) {
  const field = `${scope(inCard)}.querySelector(${JSON.stringify(selector)})`;
  await click(selector, inCard);
  await ev(`(() => { const f = ${field}; f.setSelectionRange(f.value.length, f.value.length); return 1; })()`);
  await cdp.send('Input.insertText', { text }, top);
  await pause(60);
  const value = await ev(`${field}.value`);
  if (!value.endsWith(text)) throw new Error(`typed text did not arrive in ${selector}: ${JSON.stringify(value).slice(0, 200)}`);
}

/* A control of the host page around the frame, by its id. */
async function hostClick(id) {
  const point = await topValue(`(() => {
    const el = document.getElementById(${JSON.stringify(id)});
    if (!el) return { missing: true };
    const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const hit = r.width && r.height ? document.elementFromPoint(x, y) : null;
    return { x, y, covered: !hit || !(hit === el || el.contains(hit)), hit: hit && hit.tagName };
  })()`);
  if (point.missing) throw new Error(`no host control: #${id}`);
  if (point.covered) throw new Error(`covered: host #${id}, by ${point.hit}`);
  await press(point);
}

async function waitTop(expression, what) {
  for (let tries = 0; tries < 300; tries += 1) {
    if (await topValue(expression)) return;
    await pause(100);
  }
  throw new Error(`timed out: ${what}`);
}

/* The host keeps the queue of unsent prompts in the session storage of its own page. */
const QUEUE = `(() => { const key = Object.keys(sessionStorage).find((k) => k.startsWith('lavish-axi:queued:')); return key ? JSON.parse(sessionStorage.getItem(key)) : []; })()`;
const hostQueue = () => topValue(QUEUE);

/* The host's Annotate switch; lavish starts with it on. */
async function annotation(on) {
  if ((await topValue(`document.getElementById('annotation').getAttribute('aria-pressed')`)) !== String(on)) await hostClick('annotation');
  await waitTop(`document.getElementById('annotation').getAttribute('aria-pressed') === '${on}'`, `annotation ${on ? 'on' : 'off'}`);
  await pause(150);
}

/* A real click on `selector` in annotation mode opens lavish's card; typed text and Queue queue one note. */
async function annotate(selector, text) {
  const before = (await hostQueue()).length;
  await click(selector);
  await until(`!!(${scope(true)} && ${scope(true)}.querySelector('.lavish-annotation-card textarea'))`, `the annotation card on ${selector}`);
  await type('.lavish-annotation-card textarea', text, true);
  await click('.lavish-annotation-card .lavish-send', true);
  await waitTop(`${QUEUE}.length === ${before + 1}`, `the queued note on ${selector}`);
}

/* The host's Send to Agent; the queue is empty once the host took the batch. */
async function sendRound() {
  const queued = await hostQueue();
  const covered = await topValue(`(() => { const el = document.getElementById('send'); const r = el.getBoundingClientRect(); const hit = r.width ? document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) : null; return !hit || !el.contains(hit); })()`);
  if (covered) await hostClick('panelToggle');
  await hostClick('send');
  await waitTop(`${QUEUE}.length === 0`, 'the host took the batch');
  await pause(800);
  return queued.map((prompt) => prompt.prompt);
}

async function shot(name) {
  mkdirSync(SHOTS, { recursive: true });
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' }, top);
  writeFileSync(path.join(SHOTS, `${name}.png`), Buffer.from(data, 'base64'));
}

async function width(pixels) {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: pixels, height: 900, deviceScaleFactor: 1, mobile: false }, top);
  await pause(400);
}

/* Reachable by scrolling is fine: a wide table or a big diagram scrolls in its own box. */
const LAYOUT = `(() => {
  document.querySelectorAll('.afkv2-collapsed').forEach((el) => el.classList.remove('afkv2-collapsed'));
  document.querySelectorAll('details').forEach((el) => { el.open = true; });
  const w = window.innerWidth, found = { overflow: Math.max(0, document.documentElement.scrollWidth - w), cut: [], clipped: [], hidden: [], overlap: [] };
  const name = (el) => el.tagName + (el.id ? '#' + el.id : '') + (el.getAttribute('data-afkv2-element') ? '[' + el.getAttribute('data-afkv2-element') + ']' : '') + '.' + String(el.className.baseVal === undefined ? el.className : el.className.baseVal).split(' ')[0];
  const scrolls = (el) => { for (let a = el.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll') return true; } return false; };
  const page = document.querySelector('.afkv2-page');
  let total = 0, inBoxScroll = 0;
  for (const el of page.querySelectorAll('*')) {
    if (el.closest('svg') && el.tagName !== 'svg') continue;
    if (el.closest('[hidden]') || ['SCRIPT', 'STYLE', 'OPTION'].includes(el.tagName)) continue;
    total += 1;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    const holdsText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if ((s.display === 'none' || s.visibility === 'hidden') && (holdsText || el.children.length)) found.hidden.push(name(el));
    if (s.display === 'none') continue;
    if ((r.right > w + 1 || r.left < -1) && !scrolls(el) && s.position !== 'fixed') found.cut.push(name(el));
    const clipsX = s.overflowX === 'hidden' || s.overflowX === 'clip', clipsY = s.overflowY === 'hidden' || s.overflowY === 'clip';
    if ((clipsX && el.scrollWidth > el.clientWidth + 1) || (clipsY && el.scrollHeight > el.clientHeight + 1)) found.clipped.push(name(el));
    if (s.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) found.clipped.push('ellipsis ' + name(el));
    if (el.matches('.afkv2-box') && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)) inBoxScroll += 1;
  }
  for (const figure of page.querySelectorAll('figure')) {
    const boxes = [...figure.querySelectorAll('.afkv2-box')].map((el) => [el, el.getBoundingClientRect()]);
    boxes.forEach(([a, ra], i) => boxes.slice(i + 1).forEach(([b, rb]) => {
      if (Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left) > 2 && Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top) > 2) found.overlap.push(name(a) + ' ' + name(b));
    }));
  }
  return { width: w, elements: total, boxes_that_scroll: inBoxScroll, ...found };
})()`;

async function checkLayout(label, shots = []) {
  await frameOnTop();
  const found = await ev(LAYOUT);
  result.layout[label] = { ...found, cut: found.cut.slice(0, 20), cut_count: found.cut.length, clipped: found.clipped.slice(0, 20),
    clipped_count: found.clipped.length, hidden: found.hidden.slice(0, 20), hidden_count: found.hidden.length,
    overlap: found.overlap.slice(0, 20), overlap_count: found.overlap.length };
  for (const selector of shots) {
    await ev(`document.querySelector(${JSON.stringify(selector[1])}).scrollIntoView({ block: 'start' })`);
    await pause(150);
    await frameOnTop();
    await shot(`${label}-${selector[0]}`);
  }
  step(`layout ${label}`, !found.overflow && !found.cut.length && !found.clipped.length && !found.hidden.length && !found.overlap.length, result.layout[label]);
}

async function hostAudit(label) {
  await topValue(`(() => { window.__afkv2Layout = []; const f = document.querySelector('iframe'); f.contentWindow.postMessage({ type: 'lavish:requestLayoutDiagnostics' }, '*'); return 1; })()`);
  for (let tries = 0; tries < 100; tries += 1) {
    const seen = await topValue('(window.__afkv2Layout || []).filter((m) => m.complete).length');
    if (seen) break;
    await pause(100);
  }
  const messages = await topValue('window.__afkv2Layout || []');
  const last = messages.filter((m) => m.complete).pop() || messages.pop() || null;
  result.audit[label] = last ? { complete: last.complete, viewport_width: last.viewport_width, count: last.findings.length, findings: last.findings.slice(0, 40) } : { no_message: true };
  console.log(`audit ${label}`, JSON.stringify(result.audit[label]).slice(0, 1200));
}

function newHome(name, doc) {
  const repo = path.join(SCRATCH, name);
  mkdirSync(path.join(repo, '.afkv2'), { recursive: true });
  mkdirSync(path.join(repo, '.git'), { recursive: true });
  mkdirSync(path.join(repo, 'specs', 'f', 'pages'), { recursive: true });
  writeFileSync(path.join(repo, '.afkv2', 'config.json'), JSON.stringify({ spec_folder: 'specs' }));
  const json = path.join(repo, 'specs', 'f', 'pages', `grill-${doc.session.id}.json`);
  writeFileSync(json, JSON.stringify(doc));
  return json;
}

const readDoc = (json) => JSON.parse(readFileSync(json, 'utf-8'));
const itemOf = (doc, id) => doc.rounds.flatMap((r) => r.items).find((i) => i.id === id);

async function openPage(url) {
  frameContext = null;
  frameKey = `/artifact/${url.split('/').pop()}/`;
  await cdp.send('Page.navigate', { url }, top);
  const opened = Date.now();
  await until(`!!document.querySelector('.afkv2-page') && document.readyState === 'complete'`, 'the page');
  await frameOnTop();
  (result.frame.open_ms = result.frame.open_ms || []).push(Date.now() - opened);
  await pause(300);
}

async function interact(json) {
  await until(`!!window.lavish && typeof window.lavish.queuePrompt === 'function'`, 'the host bridge');
  await annotation(true);
  await click('input[name="choice:c-decided"][value="accept"]');
  step('mark', await ev(`document.querySelector('input[name="choice:c-decided"][value="accept"]').checked`)
    && (await hostQueue()).some((p) => p.prompt.startsWith('c-decided accept')));

  await annotate('#c-note-only .afkv2-text p', TRICKY);
  step('note on a card', true);
  await annotate('#n-3 .afkv2-box-label', 'Look at this node first.');
  step('note on a map node', true);
  await annotate('#i-8-0 > .afkv2-settled', 'This settled point is wrong now.');
  step('note on a settled item', true);
  await annotate('#d-graph figcaption', 'The graph misses a service.');
  await annotate('#d-free figcaption', 'The drawing is wrong.');
  step('note on a diagram and a freestyle fragment', true);

  const queued = (await hostQueue()).length;
  await click('#n-5 .afkv2-box-label');
  await until(`!!(${scope(true)} && ${scope(true)}.querySelector('.lavish-annotation-card textarea'))`, 'the annotation card on n-5');
  await type('.lavish-annotation-card textarea', 'First text.', true);
  await click('.lavish-annotation-card .lavish-cancel', true);
  await pause(150);
  step('cancel an unsent note', !(await ev(`!!${scope(true)}.querySelector('.lavish-annotation-card')`)) && (await hostQueue()).length === queued);

  /* The current round and the one before stand open in the session table; round 7 is a closed fold.
   * An earlier step can leave it open, so each click must flip the state it finds. */
  const roundFold = 'details[data-afkv2-nr-round="7"]';
  const foldOpen = () => ev(`document.querySelector('${roundFold}').open`);
  const start = await foldOpen();
  await click(`${roundFold} > summary`);
  const flipped = (await foldOpen()) === !start;
  await click(`${roundFold} > summary`);
  step('fold and unfold a closed older round of notes', flipped && (await foldOpen()) === start, { start });

  const card = '[data-afkv2-element="i-7-0"]';
  const before = await ev(`document.querySelector('${card}').matches('.afkv2-collapsed')`);
  await click(`${card} > .afkv2-h`);
  const after = await ev(`document.querySelector('${card}').matches('.afkv2-collapsed')`);
  step('collapse a settled card', before !== after, { before, after });
  await checkLayout('with-queue-1280', [['notes', '#afkv2-notes-replies']]);

  const typed = JSON.stringify((await hostQueue()).map((p) => p.prompt));
  const doc = readDoc(json);
  doc.rounds[8].replies.push({ text: 'A reply written while you type.' });
  writeFileSync(json, JSON.stringify(doc));
  const rendered = engine('render', json);
  step('render while typing', rendered.ok, rendered);
  await until(`document.body.textContent.includes('A reply written while you type.')`, 'the live reload');
  await until(`!!window.lavish && typeof window.lavish.queuePrompt === 'function'`, 'the host bridge');
  await pause(500);
  const typedAfter = JSON.stringify((await hostQueue()).map((p) => p.prompt));
  const marked = await ev(`document.querySelector('input[name="choice:c-decided"][value="accept"]').checked`);
  step('every unsent note and mark survives a re-render', typedAfter === typed && marked, { queued: JSON.parse(typedAfter).length });
  const sent = await sendRound();
  step('send empties the host queue', (await hostQueue()).length === 0, { sent: sent.length });
  return sent;
}

/* `sent` is the text of each prompt the host queue held at Send, in order. */
function checkIngest(json, sent) {
  const polled = engine('poll', json);
  step('poll', polled.ok && !polled.raw_warning, { status: polled.status, raw_warning: polled.raw_warning });
  const prompts = JSON.stringify((polled.prompts || []).map((p) => p.prompt));
  step('seam: poll reads the prompts the page queued', prompts === JSON.stringify(sent), { polled: prompts.slice(0, 300) });
  const rawFile = path.join(SCRATCH, 'raw.txt');
  writeFileSync(rawFile, polled.raw);
  const answer = engine('ingest', json, '--raw-file', rawFile);
  step('ingest', answer.ok, { round: answer.round, needs_reading: answer.needs_reading, reopened: answer.reopened, steers: answer.steers, settled_by_mark: answer.settled_by_mark });
  const doc = readDoc(json);
  const stored = doc.rounds.find((r) => r.state === 'current').responses.at(-1).raw;
  step('seam: ingest stored the bytes poll read', Buffer.compare(Buffer.from(stored), Buffer.from(polled.raw)) === 0);
  return doc;
}

async function newTab() {
  ({ targetId: topTarget } = await cdp.send('Target.createTarget', { url: 'about:blank' }));
  ({ sessionId: top } = await cdp.send('Target.attachToTarget', { targetId: topTarget, flatten: true }));
  cdp.attach(top);
  await cdp.send('Page.bringToFront', {}, top);
  await cdp.send('Emulation.setFocusEmulationEnabled', { enabled: true }, top);
  await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
    source: `addEventListener('message', (e) => { if (window === window.top && e.data && e.data.type === 'lavish:layoutDiagnostics') (window.__afkv2Layout = window.__afkv2Layout || []).push(e.data); });`,
  }, top);
  await width(1280);
}

const pageTabs = async () => (await cdp.send('Target.getTargets')).targetInfos.filter((t) => t.type === 'page').length;
const LONG = 'Words of a long card. '.repeat(300);
const BANNER = { settled: [], unlocks: [], parked: [] };

function shellDocument() {
  return {
    schema: 'afkv2.page/1',
    session: { id: 's3', skill: 'grill', feature: 'Shell feature', ticket: 'T-3', started: '2026-01-05T10:00:00Z',
      short_title: 'Page shell', step: 'Requirements grill' },
    maps: [{ type: 'map', id: 'm-shell', props: { nodes: [{ id: 'n-tab', label: 'The tab', state: 'open', round: 1 }] } }],
    notes: [],
    rounds: [{ n: 1, state: 'current', banner: BANNER, items: [
      { id: 'c-tab', kind: 'decided', node: 'n-tab', body: { type: 'text', props: { text: 'The first card. ' + LONG } } },
      { id: 'c-far', kind: 'confirm', body: { type: 'text', props: { text: LONG + ' This follows c-tab.' } } }] }],
  };
}

const scrolled = () => ev('Math.round(window.scrollY)');
const nearTop = (selector) => ev(`Math.abs(document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().top) < 80`);
const navClosed = () => ev(`getComputedStyle(document.getElementById('afkv2-nav-list')).display === 'none'`);
const navMin = () => ev(`document.getElementById('afkv2-nav').classList.contains('afkv2-min')`);

/* The page shell and the "Page host" seam, on a page of its own. */
async function shellSteps() {
  const json = newHome('repo-shell', shellDocument());
  const shown = engine('show', json);
  step('show without --no-open', shown.ok && shown.tab === null && !!shown.url, shown);
  await width(1280);
  await openPage(shown.url);
  const title = 'T-3 \u00b7 Page shell \u00b7 Requirements grill';
  const titles = async () => JSON.stringify(await ev(`[document.title, document.querySelector('.afkv2-title').textContent]`));
  step('title', (await titles()) === JSON.stringify([title, title]), await titles());
  const margin = await ev(`(() => { const n = document.getElementById('afkv2-nav').getBoundingClientRect(); return { nav: n.right, page: document.querySelector('.afkv2-page').getBoundingClientRect().left }; })()`);
  step('navigation in the left margin at 1280', margin.nav <= margin.page, margin);
  /* In annotation mode a click on a link or a map box opens lavish's note card; the jumps need it off. */
  await annotation(false);

  /* The click helper centres its target first, so each place before a jump is read after that centring. */
  const centre = (selector) => ev(`(document.querySelector(${JSON.stringify(selector)}).scrollIntoView({ block: 'center', inline: 'center' }), 1)`);
  const jumpAndBack = async (selector, what) => {
    await centre(selector);
    await pause(150);
    const before = await scrolled();
    await click(selector);
    await pause(300);
    step(`${what} scrolls to its card`, await nearTop('#c-tab'));
    await click('#afkv2-back');
    const after = await scrolled();
    step(`back after ${what}`, Math.abs(after - before) <= 4, { before, after });
  };
  await jumpAndBack('.afkv2-card-link[href="#c-tab"]', 'a card link');
  const tip = await ev(`document.getElementById('n-tab').getAttribute('data-afkv2-tip') || ''`);
  step('the map box tip', /open/.test(tip) && tip.includes('last changed in round 1'), tip);
  await jumpAndBack('#n-tab', 'a map box');

  await click('#afkv2-nav-head');
  step('collapse the navigation', await navMin());
  const tabs = await pageTabs();
  const doc = readDoc(json);
  doc.rounds[0].state = 'settled';
  doc.rounds.push({ n: 2, state: 'current', banner: BANNER, changed: ['c-two'], items: [
    { id: 'c-two', kind: 'decided', title: 'The second round', body: { type: 'text', props: { text: 'The second round.' } } },
    { id: 'c-same', kind: 'decided', body: { type: 'text', props: { text: 'An unchanged card.' } } }] });
  writeFileSync(json, JSON.stringify(doc));
  const again = engine('show', json);
  step('tab reuse: the second show reuses the tab', again.ok && again.tab === 'reused' && again.url === shown.url, again);
  await until(`document.body.textContent.includes('An unchanged card.')`, 'the new round in the open tab');
  step('tab reuse: no new tab', (await pageTabs()) === tabs, { before: tabs, after: await pageTabs() });
  step('the title stays the same', (await titles()) === JSON.stringify([title, title]));
  step('the collapsed navigation stays collapsed', await navMin());
  step('what changed', await ev(`!!document.querySelector('.afkv2-banner-changed a[href="#c-two"]') && document.getElementById('c-two').getAttribute('data-afkv2-fresh') === '2' && !document.getElementById('c-same').hasAttribute('data-afkv2-fresh')`));
  await checkLayout('shell-1280', [['top', '.afkv2-page']]);

  await width(390);
  await frameOnTop();
  step('a narrow window: the navigation is one button', await navClosed());
  await click('#afkv2-nav-head');
  step('the button opens the list', !(await navClosed()));
  await click('.afkv2-nav-row');
  step('a jump closes the list', await navClosed());
  await checkLayout('shell-390', [['top', '.afkv2-page']]);
  await width(1280);

  await cdp.send('Target.closeTarget', { targetId: topTarget });
  frameContext = null;
  const left = engine('poll', json);
  step('closed tab: poll reports that the browser left', !left.ok, left);
  const third = engine('show', json);
  step('closed tab: the next show asks for a new tab', third.ok && third.tab === null, third);
  await newTab();
  await openPage(third.url);
  step('closed tab: one new tab', (await pageTabs()) === tabs, { before: tabs, after: await pageTabs() });
  await cdp.send('Page.navigate', { url: 'about:blank' }, top);
  frameContext = null;
  endSession(json);
}

async function main() {
  mkdirSync(path.join(SCRATCH, 'local'), { recursive: true });
  mkdirSync(path.join(SCRATCH, 'state'), { recursive: true });
  const docs = JSON.parse(run([path.join(ROOT, 'tests', 'engine', 'test_ingest.py')]).stdout);
  const json = newHome('repo', docs.stress);
  const diagrams = newHome('repo-diagrams', docs.diagrams);
  const shown = engine('show', json, '--no-open');
  step('show', shown.ok && shown.url, shown);

  rmSync(PROFILE, { recursive: true, force: true, maxRetries: 20, retryDelay: 500 });
  edge = spawn(EDGE, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${PROFILE}`, '--no-first-run', '--disable-gpu', '--disable-features=BackForwardCache', 'about:blank'], { stdio: 'ignore' });
  try {
    const activePort = path.join(PROFILE, 'DevToolsActivePort');
    for (let tries = 0; tries < 200 && !existsSync(activePort); tries += 1) await pause(100);
    const [debugPort, wsPath] = readFileSync(activePort, 'utf-8').split('\n');
    const ws = new WebSocket(`ws://127.0.0.1:${debugPort}${wsPath.trim()}`);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
    cdp = new Cdp(ws);
    await newTab();

    await openPage(shown.url);
    result.frame.oopif = cdp.sessions.size > 1;
    result.frame.width_1280 = await ev('window.innerWidth');
    await checkLayout('stress-1280', [['top', '.afkv2-page'], ['map', '#afkv2-maps'], ['table', '[data-afkv2-element="d-table"]'], ['graph', '[data-afkv2-element="d-graph"]'], ['sequence', '[data-afkv2-element="d-seq"]'], ['free', '[data-afkv2-element="d-free"]']]);
    await hostAudit('stress-1280');
    await width(390);
    result.frame.width_390 = await ev('window.innerWidth');
    await checkLayout('stress-390', [['top', '.afkv2-page'], ['map', '#afkv2-maps'], ['table', '[data-afkv2-element="d-table"]'], ['long', '[data-afkv2-element="c-confirm"]'], ['copy', '#afkv2-copy']]);
    await hostAudit('stress-390');

    const shownDiagrams = engine('show', diagrams, '--no-open');
    await width(1280);
    await openPage(shownDiagrams.url);
    await checkLayout('diagrams-1280', [['all', '.afkv2-page']]);
    await hostAudit('diagrams-1280');
    await width(390);
    await checkLayout('diagrams-390', [['all', '.afkv2-page']]);
    await hostAudit('diagrams-390');
    endSession(diagrams);

    await shellSteps();

    await width(1280);
    await openPage(shown.url);
    const sent = await interact(json);
    step('the queue holds the typed text', sent.includes(TRICKY) && sent.some((p) => p.startsWith('c-decided accept')), sent.map((p) => p.slice(0, 60)));
    let doc = checkIngest(json, sent);

    const state = (id) => itemOf(doc, id).state || 'open';
    const notes = doc.notes || [];
    step('a lone accept settles by mark', state('c-decided') === 'settled_by_mark');
    step('a note goes to needs-reading, with its text', state('c-note-only') === 'needs_reading' && notes.some((n) => n.item === 'c-note-only' && n.text === TRICKY));
    step('a note on a settled item reopens it', state('i-8-0') === 'open' && !itemOf(doc, 'i-8-0').settled);
    step('a note on a map node is a steer', notes.some((n) => n.target === 'n-3' && !n.item && n.text === 'Look at this node first.') && state('c-spare') === 'open');
    step('notes on a diagram and a freestyle fragment', notes.some((n) => n.target === 'd-graph') && notes.some((n) => n.target === 'd-free'));
    step('the cancelled note is not sent', !notes.some((n) => n.text === 'First text.'));

    const rendered = engine('render', json);
    step('render after ingest', rendered.ok, rendered);
    await until(`document.body.textContent.includes('This settled point is wrong now.') && document.body.textContent.includes('Look at this node first.')`, 'the notes on the page');
    await checkLayout('after-ingest-1280', [['notes', '#afkv2-notes-replies']]);

    doc = readDoc(json);
    const read = itemOf(doc, 'c-note-only');
    read.state = 'settled_by_note';
    read.settled = { by: 'note', round: 9, signal: 'N-9-c-note-only', reading: 'The reading of the agent.' };
    doc.rounds[8].state = 'settled';
    doc.rounds.push({ n: 10, state: 'current', banner: doc.rounds[8].banner, items: [{ id: 'c-next', kind: 'decided', body: { type: 'text', props: { text: 'The next round.' } } }] });
    writeFileSync(json, JSON.stringify(doc));
    step('render the next round', engine('render', json).ok);
    await until(`!!document.querySelector('input[name="choice:c-next"][value="accept"]')`, 'the next round');
    step('settled by note shows differently', await ev(`document.querySelector('[data-afkv2-element="c-note-only"]').getAttribute('data-afkv2-point') === 'settled_by_note' && document.body.textContent.includes('The reading of the agent.')`));
    await until(`!!window.lavish && typeof window.lavish.queuePrompt === 'function'`, 'the host bridge');
    await click('input[name="choice:c-next"][value="accept"]');
    doc = checkIngest(json, await sendRound());
    step('a later round ingests', itemOf(doc, 'c-next').state === 'settled_by_mark');
    engine('render', json);
    await width(390);
    await frameOnTop();
    await checkLayout('next-round-390', [['top', '.afkv2-page']]);
    await width(1280);

    await cdp.send('Page.navigate', { url: 'about:blank' }, top);
    frameContext = null;
    endSession(json);
    const reopened = engine('show', json, '--no-open');
    step('show a saved session again', reopened.ok && reopened.url, reopened);
    await openPage(reopened.url);
    step('the saved notes are on the page', await ev(`document.body.textContent.includes('This settled point is wrong now.') && document.body.textContent.includes('The reading of the agent.')`));
    await cdp.send('Page.navigate', { url: 'about:blank' }, top);
    endSession(json);
  } catch (error) {
    await shot('failure').catch(() => {});
    throw error;
  } finally {
    /* Browser.close ends every Edge process; a kill alone leaves children holding the profile. */
    if (cdp) cdp.send('Browser.close').catch(() => {});
    await pause(1500);
    edge.kill();
    endSession(json);
    endSession(diagrams);
  }
}

let code = 0;
try { await main(); } catch (error) {
  code = 1;
  result.error = String(error.stack || error);
  console.error(result.error);
}
writeFileSync(path.join(SCRATCH, 'live-result.json'), JSON.stringify(result, null, 2));
process.exit(code);
```

## Result

| Date | Commit | Result | Layout audit |
|---|---|---|---|
| 2026-11-02 | 6767c12a | 47 of 47 steps pass, lavish-axi 0.1.80, headless Edge | 0 severe findings at window widths 1280 and 390, on the full page and on the page of only diagrams |
