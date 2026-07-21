import assert from "node:assert/strict";
import test from "node:test";

import commandCardData from "../src/commandCardData.json" with { type: "json" };
import {
  applyNumericKey,
  inventoryModeFromUrl,
  inventoryUrl,
  parseScannerCommand,
  studioModeFromUrl,
} from "../src/scannerCommands.js";

const ORIGIN = "https://erp.example.com";

test("builds stable app and mode URLs", () => {
  assert.equal(inventoryUrl(ORIGIN), `${ORIGIN}/studio-inventory`);
  assert.equal(inventoryUrl(ORIGIN, "consume"), `${ORIGIN}/studio-inventory?mode=consume`);
  assert.throws(() => inventoryUrl(ORIGIN, "manufacture"), /Unknown inventory mode/);
});

test("reads only same-site Studio Inventory deep links", () => {
  assert.equal(inventoryModeFromUrl(`${ORIGIN}/studio-inventory/?mode=count`, ORIGIN), "count");
  assert.equal(studioModeFromUrl(`${ORIGIN}/studio-inventory?mode=price`, ORIGIN), "price");
  assert.equal(inventoryModeFromUrl(`${ORIGIN}/studio-inventory?mode=price`, ORIGIN), null);
  assert.equal(inventoryModeFromUrl(`${ORIGIN}/studio-inventory?mode=unknown`, ORIGIN), null);
  assert.equal(inventoryModeFromUrl("https://example.com/studio-inventory?mode=count", ORIGIN), null);
});

test("turns app QR URLs into local open or mode commands", () => {
  assert.deepEqual(parseScannerCommand(`${ORIGIN}/studio-inventory`, ORIGIN), { type: "open", mode: null });
  assert.deepEqual(parseScannerCommand(`${ORIGIN}/studio-inventory?mode=receive`, ORIGIN), {
    type: "open",
    mode: "receive",
  });
  assert.equal(parseScannerCommand("https://example.com/studio-inventory?mode=receive", ORIGIN), null);
});

test("parses compact and readable scanner commands", () => {
  assert.deepEqual(parseScannerCommand("SI:M:U", ORIGIN), { type: "mode", mode: "consume" });
  assert.deepEqual(parseScannerCommand("si:entry:remaining", ORIGIN), { type: "entry", mode: "ending" });
  assert.deepEqual(parseScannerCommand("SI:K:7", ORIGIN), { type: "key", key: "7" });
  assert.deepEqual(parseScannerCommand("SI:K:B", ORIGIN), { type: "key", key: "backspace" });
  assert.deepEqual(parseScannerCommand("SI:A:OK", ORIGIN), { type: "action", action: "confirm" });
  assert.equal(parseScannerCommand("HAHN-PHOTO-BARYTA", ORIGIN), null);
});

test("applies scanner keypad edits without floating-point arithmetic", () => {
  assert.equal(applyNumericKey("", "1"), "1");
  assert.equal(applyNumericKey("1", "."), "1.");
  assert.equal(applyNumericKey("1.", "5"), "1.5");
  assert.equal(applyNumericKey("1.5", "."), "1.5");
  assert.equal(applyNumericKey("1", ".", { allowDecimal: false }), "1");
  assert.equal(applyNumericKey("10", "backspace"), "1");
  assert.equal(applyNumericKey("10", "clear"), "");
});

test("accepts every QR link and Code 128 value printed on the command card", () => {
  const { appPath, modes, entryModes, keys, actions } = commandCardData;
  assert.equal(inventoryUrl(ORIGIN), `${ORIGIN}${appPath}`);

  for (const mode of modes) {
    assert.deepEqual(parseScannerCommand(inventoryUrl(ORIGIN, mode.mode), ORIGIN), {
      type: "open",
      mode: mode.mode,
    });
  }

  for (const item of [...entryModes, ...keys, ...actions]) {
    assert.notEqual(parseScannerCommand(item.code, ORIGIN), null, item.code);
  }
});
