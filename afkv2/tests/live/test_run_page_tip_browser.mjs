import assert from "node:assert/strict";
import test from "node:test";

import { withDeadline } from "./run_page_tip_browser.mjs";

test("a stalled Chrome DevTools operation is canceled", async () => {
  let canceled = false;
  await assert.rejects(
    withDeadline(new Promise(() => {}), 20, "stalled operation", () => { canceled = true; }),
    /Timed out waiting for stalled operation/,
  );
  assert.equal(canceled, true);
});
