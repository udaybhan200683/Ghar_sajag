// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A05 App platform
// @requirements F11, F13, E04, E08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// ApiClient uses injected fetch and token providers so tests can simulate failures. VersionedCache refuses
// older snapshots and labels age. Browser cache and service-worker assets are not durable server state,
// and a push subscription is not notification delivery evidence.

import { logTrace, logError } from "./logging.mjs";
/** A05 — injected API transport, versioned cache and push-permission model. */

export class ApiClient {
  constructor(fetchImpl, tokenProvider) {
    this.fetchImpl = fetchImpl;
    this.tokenProvider = tokenProvider;
  }

  async request(command) {
    logTrace("APP", "A05", "request.enter");
    const token = await this.tokenProvider();
    const response = await this.fetchImpl(command.path, {
      method: command.method ?? "GET",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
        ...(command.idempotencyKey ? { "idempotency-key": command.idempotencyKey } : {}),
      },
      body: command.body == null ? undefined : JSON.stringify(command.body),
    });
    if (response.status === 401 || response.status === 403) {
      logError("APP", "A05", "request.failed", "authorization");
      throw new Error("AUTHORIZATION_FAILED");
    }
    if (!response.ok) {
      logError("APP", "A05", "request.failed", `service_status_${response.status}`);
      throw new Error(`SERVICE_ERROR_${response.status}`);
    }
    return response.status === 204 ? null : response.json();
  }
}

export class VersionedCache {
  constructor() {
    this.values = new Map();
  }

  put(key, version, value, storedAt) {
    const current = this.values.get(key);
    if (!current || version >= current.version) this.values.set(key, { version, value, storedAt });
    return this.values.get(key);
  }

  get(key, now, maxAgeSeconds) {
    const current = this.values.get(key);
    if (!current) return { hit: false, stale: true, value: null };
    return { hit: true, stale: now - current.storedAt > maxAgeSeconds, value: current.value, version: current.version };
  }
}

export function pushCapability(permission, subscriptionPresent) {
  logTrace("APP", "A05", "pushCapability.enter");
  if (permission === "denied") return { usable: false, reason: "permission_denied" };
  if (permission !== "granted") return { usable: false, reason: "permission_not_granted" };
  if (!subscriptionPresent) return { usable: false, reason: "subscription_missing" };
  return { usable: true, reason: "ready" };
}

export function classifyFetchFailure(error) {
  logTrace("APP", "A05", "classifyFetchFailure.enter");
  if (error?.name === "AbortError") return "TIMEOUT";
  if (error?.message === "AUTHORIZATION_FAILED") return "AUTHORIZATION";
  if (String(error?.message ?? "").startsWith("SERVICE_ERROR_")) return "SERVICE";
  return "OFFLINE_OR_NETWORK";
}
