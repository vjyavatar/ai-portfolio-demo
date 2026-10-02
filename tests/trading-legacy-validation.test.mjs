import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
test("legacy validation panel makes no invented performance claim", () => {
  const source=fs.readFileSync(new URL("../static/options-engine.js",import.meta.url),"utf8");
  const body=source.slice(source.indexOf("window._renderBacktest=function"),source.indexOf("// ─── FEATURE 4:"));
  const context={window:{}};vm.runInNewContext(body,context);
  const html=context.window._renderBacktest();
  assert.match(html,/not established/);
  assert.match(html,/unavailable/);
  assert.doesNotMatch(html,/\d+%|Historical win rate/);
});
