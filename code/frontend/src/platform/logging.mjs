// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S05 Diagnostics facade and sinks
// @requirements AI08, E10, NFR-05, NFR-09
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The atomic sink pointer only makes pointer publication atomic; it does not make sink lifetime or writes
// thread-safe. The host file sink performs synchronous I/O and rotation. Production should enqueue fixed
// records to one writer, reserve error capacity and expose drops; this future writer is not in the current
// source.

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

// @requirements AI08, E10, NFR-05, NFR-09
// Export the bounded browser diagnostic buffer as text; it is not an authoritative incident audit
// store.
export function exportLogText() {
  return `${records.join("\n")}${records.length ? "\n" : ""}`;
}

export function clearLogsForTest() { records.length = 0; }
