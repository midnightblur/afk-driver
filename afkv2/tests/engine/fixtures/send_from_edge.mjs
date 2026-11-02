// Live seam-test driver: one tab in headless Edge, as a person keeps across rounds. Each stdin line names
// an item to mark, note and send. Argument: the session URL. Environment: AFKV2_NOTE, AFKV2_SHOT, NODE_PATH.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import readline from 'node:readline';

const require = createRequire(pathToFileURL(process.env.NODE_PATH + '/'));
const { chromium } = require('playwright-core');
const STATUS = '.afkv2-send-status';
const GO = '#afkv2-send-go';
const FRAME_TRIES = 300;

async function artifactFrame(page) {
  for (let tries = 0; tries < FRAME_TRIES; tries += 1) {
    const frame = page.frames().find((f) => f.url().includes('/artifact/'));
    if (frame) return frame;
    await page.waitForTimeout(100);
  }
  throw new Error('the page frame did not load');
}

// A live reload replaces the frame's document, so the driver looks the frame up again on each try.
async function cardFrame(page, item) {
  const choice = `input[name="choice:${item}"][value="accept"]`;
  for (let tries = 0; tries < FRAME_TRIES; tries += 1) {
    const frame = await artifactFrame(page);
    if (await frame.$(choice).catch(() => null)) return frame;
    await page.waitForTimeout(100);
  }
  throw new Error(`the card ${item} did not appear`);
}

async function send(page, item) {
  const frame = await cardFrame(page, item);
  await frame.check(`input[name="choice:${item}"][value="accept"]`);
  await frame.fill(`textarea[name="note:${item}"]`, process.env.AFKV2_NOTE);
  if (process.env.AFKV2_SHOT) await page.screenshot({ path: process.env.AFKV2_SHOT, fullPage: true });
  await frame.click(GO);
  await frame.waitForFunction(([s]) => /no mark|sent\./i.test(document.querySelector(s).textContent), [STATUS]);
  if (/no mark/i.test(await frame.textContent(STATUS))) {
    await frame.click(GO);
    await frame.waitForFunction(([s]) => /sent\./i.test(document.querySelector(s).textContent), [STATUS]);
  }
  await page.waitForTimeout(1000);
}

const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
  await page.goto(process.argv[2]);
  for await (const line of readline.createInterface({ input: process.stdin })) {
    await send(page, line.trim());
    console.log(`sent ${line.trim()}`);
  }
} finally {
  await browser.close();
}
