const INVENTORY_PATH = "/studio-inventory";
const INVENTORY_MODES = new Set(["receive", "consume", "count"]);
const STUDIO_MODES = new Set([...INVENTORY_MODES, "price"]);

const MODE_COMMANDS = {
  R: "receive",
  RECEIVE: "receive",
  U: "consume",
  USE: "consume",
  CONSUME: "consume",
  C: "count",
  COUNT: "count",
};

const ENTRY_COMMANDS = {
  A: "amount",
  AMOUNT: "amount",
  R: "ending",
  ENDING: "ending",
  REMAINING: "ending",
};

const KEY_COMMANDS = {
  ".": ".",
  DOT: ".",
  C: "clear",
  CLEAR: "clear",
  B: "backspace",
  BACKSPACE: "backspace",
};

const ACTION_COMMANDS = {
  OK: "confirm",
  CONFIRM: "confirm",
  X: "cancel",
  CANCEL: "cancel",
  UNDO: "undo",
};

function normalizedPath(pathname) {
  const path = pathname.replace(/\/+$/, "");
  return path || "/";
}

export function inventoryUrl(origin, mode = null) {
  const url = new URL(INVENTORY_PATH, origin);
  if (mode) {
    const normalizedMode = String(mode).trim().toLowerCase();
    if (!INVENTORY_MODES.has(normalizedMode)) throw new Error(`Unknown inventory mode: ${mode}`);
    url.searchParams.set("mode", normalizedMode);
  }
  return url.toString();
}

export function inventoryModeFromUrl(value, origin) {
  const mode = studioModeFromUrl(value, origin);
  return INVENTORY_MODES.has(mode) ? mode : null;
}

export function studioModeFromUrl(value, origin) {
  let url;
  try {
    url = new URL(value, origin);
  } catch {
    return null;
  }
  if (url.origin !== new URL(origin).origin || normalizedPath(url.pathname) !== INVENTORY_PATH) return null;
  const mode = String(url.searchParams.get("mode") || "").trim().toLowerCase();
  return STUDIO_MODES.has(mode) ? mode : null;
}

export function parseScannerCommand(value, origin) {
  const text = String(value || "").trim();
  if (!text) return null;

  let url;
  try {
    url = new URL(text);
  } catch {
    url = null;
  }
  if (url && url.origin === new URL(origin).origin && normalizedPath(url.pathname) === INVENTORY_PATH) {
    return { type: "open", mode: inventoryModeFromUrl(url.toString(), origin) };
  }

  const [prefix, group, rawValue, ...extra] = text.toUpperCase().split(":");
  if (prefix !== "SI" || !group || !rawValue || extra.length) return null;

  if (group === "M" || group === "MODE") {
    const mode = MODE_COMMANDS[rawValue];
    return mode ? { type: "mode", mode } : null;
  }
  if (group === "E" || group === "ENTRY") {
    const mode = ENTRY_COMMANDS[rawValue];
    return mode ? { type: "entry", mode } : null;
  }
  if (group === "K" || group === "KEY") {
    if (/^\d$/.test(rawValue)) return { type: "key", key: rawValue };
    const key = KEY_COMMANDS[rawValue];
    return key ? { type: "key", key } : null;
  }
  if (group === "A" || group === "ACTION") {
    const action = ACTION_COMMANDS[rawValue];
    return action ? { type: "action", action } : null;
  }
  return null;
}

export function applyNumericKey(current, key, { allowDecimal = true } = {}) {
  const value = String(current || "");
  if (key === "clear") return "";
  if (key === "backspace") return value.slice(0, -1);
  if (key === ".") {
    if (!allowDecimal || value.includes(".")) return value;
    return value ? `${value}.` : "0.";
  }
  if (!/^\d$/.test(key)) return value;
  if (value === "0") return key;
  return `${value}${key}`;
}
