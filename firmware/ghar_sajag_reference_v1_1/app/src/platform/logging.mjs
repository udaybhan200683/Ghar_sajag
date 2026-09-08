/** Bounded client diagnostics. Production keeps ERROR; trace is build-injected. */
const traceEnabled = globalThis.__GS_TRACE__ === true || globalThis.process?.env?.GS_TRACE === "1";
const capacity = 128;
const records = [];

function append(level, category, moduleId, event, detail = "-") {
  if (level === "TRACE" && !traceEnabled) return;
  const safe = String(detail).replace(/[\r\n]/g, " ").slice(0, 96);
  if (records.length === capacity) records.shift();
  records.push(`level=${level} category=${category} module=${moduleId} event=${event} detail=${safe}`);
}

export function logError(category, moduleId, event, detail) {
  append("ERROR", category, moduleId, event, detail);
}

export function logTrace(category, moduleId, event, detail = "-") {
  append("TRACE", category, moduleId, event, detail);
}

export function exportLogText() {
  return `${records.join("\n")}${records.length ? "\n" : ""}`;
}

export function clearLogsForTest() { records.length = 0; }
