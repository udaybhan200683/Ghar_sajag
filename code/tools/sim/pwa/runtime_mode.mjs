const RESERVED_SUFFIXES = new Set(['localhost', 'local', 'test', 'example', 'invalid']);

function isTestOnlyPrivateIpv4(host) {
  const octets = host.split('.');
  if (octets.length !== 4 || octets.some(part => !/^(0|[1-9][0-9]{0,2})$/.test(part))) return false;
  const values = octets.map(Number);
  if (values.some(value => value < 0 || value > 255)) return false;
  return values[0] === 10 ||
    (values[0] === 172 && values[1] >= 16 && values[1] <= 31) ||
    (values[0] === 192 && values[1] === 168);
}

export function parseCaregiverBackendOrigin(value, {gs179LocalLanTestOnly = false} = {}) {
  if (typeof value !== 'string' || !value.trim() || value.length > 2048) return '';
  const raw = value.trim();
  const rawLanAuthority = gs179LocalLanTestOnly
    ? /^https:\/\/(\d{1,3}(?:\.\d{1,3}){3})(?::443)?\/?$/i.exec(raw)
    : null;
  if (gs179LocalLanTestOnly && !rawLanAuthority) return '';
  if (rawLanAuthority && !isTestOnlyPrivateIpv4(rawLanAuthority[1])) return '';
  let url;
  try {
    url = new URL(raw);
  } catch {
    return '';
  }
  if (url.protocol !== 'https:' || url.username || url.password || url.port && url.port !== '443' ||
      !['', '/'].includes(url.pathname) || url.search || url.hash) return '';
  const host = url.hostname.toLowerCase();
  if (gs179LocalLanTestOnly) {
    if (host !== rawLanAuthority[1].toLowerCase() || !isTestOnlyPrivateIpv4(host)) return '';
  } else {
    const labels = host.split('.');
    if (labels.length < 2 || labels.some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return '';
    if (labels.some(label => label.length > 63) || labels.at(-1).length < 2 || RESERVED_SUFFIXES.has(labels.at(-1))) return '';
  }
  return `https://${host}/`;
}

function sameOrigin(candidate, pageOrigin) {
  if (typeof candidate !== 'string' || !candidate) return '';
  try {
    const parsed = new URL(candidate);
    const page = new URL(pageOrigin);
    if (parsed.origin !== page.origin || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) return '';
    return parsed.origin;
  } catch {
    return '';
  }
}

export function normalizeRuntimeConfig(raw, pageOrigin) {
  if (raw?.mode === 'local-simulator' && raw.allowSimulator === true &&
      raw.actorId === 'simulation-owner' && raw.homeId === 'simulation-home') {
    const backendOrigin = sameOrigin(raw.backendOrigin, pageOrigin);
    if (backendOrigin) {
      return Object.freeze({
        mode: 'local-simulator',
        backendOrigin,
        actorId: raw.actorId,
        homeId: raw.homeId,
      });
    }
  }

  return Object.freeze({
    mode: 'caregiver',
    backendOrigin: parseCaregiverBackendOrigin(raw?.backendOrigin, {
      gs179LocalLanTestOnly: raw?.gs179LocalLanTestOnly === true,
    }),
    caregiverApiConfigured: !!parseCaregiverBackendOrigin(raw?.backendOrigin, {
      gs179LocalLanTestOnly: raw?.gs179LocalLanTestOnly === true,
    }),
    hubWifiNativeDiscovery: raw?.hubWifiNativeDiscovery === true,
    appVersion: typeof raw?.appVersion==='string'&&/^[a-zA-Z0-9._-]{1,80}$/.test(raw.appVersion)?raw.appVersion:'unknown',
    sourceRevision: typeof raw?.sourceRevision==='string'&&/^[a-fA-F0-9]{12}$/.test(raw.sourceRevision)?raw.sourceRevision:'unknown',
  });
}

export function requestHeaders(runtime, headers = {}) {
  const result = { ...headers };
  if (runtime?.mode === 'local-simulator' && runtime.actorId === 'simulation-owner') {
    result['X-Actor-Id'] = runtime.actorId;
  }
  return result;
}

export function requestUrl(runtime, path) {
  if (!runtime?.backendOrigin || typeof path !== 'string' || !path.startsWith('/')) return '';
  const url = new URL(path, runtime.backendOrigin);
  if (url.origin !== runtime.backendOrigin.replace(/\/$/, '')) return '';
  return url.href;
}
