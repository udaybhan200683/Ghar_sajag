const RESERVED_SUFFIXES = new Set(['localhost', 'local', 'test', 'example', 'invalid']);

export function parseCaregiverBackendOrigin(value) {
  if (typeof value !== 'string' || !value.trim() || value.length > 2048) return '';
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    return '';
  }
  if (url.protocol !== 'https:' || url.username || url.password || url.port && url.port !== '443' ||
      !['', '/'].includes(url.pathname) || url.search || url.hash) return '';
  const host = url.hostname.toLowerCase();
  const labels = host.split('.');
  if (labels.length < 2 || labels.some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) return '';
  if (labels.some(label => label.length > 63) || labels.at(-1).length < 2 || RESERVED_SUFFIXES.has(labels.at(-1))) return '';
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
    backendOrigin: parseCaregiverBackendOrigin(raw?.backendOrigin),
    caregiverApiConfigured: false,
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
