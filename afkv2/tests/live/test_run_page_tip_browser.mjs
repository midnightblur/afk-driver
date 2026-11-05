import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import { parseCdpMessage, run, terminateProcess, withDeadline } from "./run_page_tip_browser.mjs";

test("a stalled Chrome DevTools operation is canceled", async () => {
  let canceled = false;
  await assert.rejects(
    withDeadline(new Promise(() => {}), 20, "stalled operation", () => { canceled = true; }),
    /Timed out waiting for stalled operation/,
  );
  assert.equal(canceled, true);
});

test("a stalled fixture builder is terminated", async () => {
  await assert.rejects(
    run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { timeout: 20 }),
    /Timed out waiting for subprocess/,
  );
});

test("subprocess and protocol diagnostics have size bounds", async () => {
  const result = await run(process.execPath, ["-e", "process.stdout.write('x'.repeat(2_000_000))"]);
  assert.match(result.stdout, /^\[truncated\]/);
  assert.throws(() => parseCdpMessage("x".repeat(2_000_000)), /exceeded/);
});

test("Chrome cleanup reports a process that survives hard termination", async () => {
  const child = new EventEmitter();
  child.exitCode = null;
  child.kill = () => true;
  await assert.rejects(terminateProcess(child, 10), /Chrome did not exit/);
});
