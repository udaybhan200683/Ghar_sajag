// Exercise the shipped caregiver PWA against the local authenticated API.
// UI assets come from the canonical PWA source; API requests use HTTPS and
// Node's TLS verifier trusts only the owner-private GS-179 TEST_ONLY CA.
const {chromium, expect} = require('../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

(async () => {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  const config = JSON.parse(input);
  const origin = new URL(config.origin).origin;
  const repo = path.resolve(__dirname, '../../..');
  const pwaRoot = path.join(repo, 'code/tools/sim/pwa');
  const prefix = '/__caregiver_app__/';
  const candidates = fs.readdirSync(path.join(os.homedir(), '.cache', 'ms-playwright'))
    .filter(name => name.startsWith('chromium-')).flatMap(name => [
      path.join(os.homedir(), '.cache', 'ms-playwright', name, 'chrome-linux64', 'chrome'),
      path.join(os.homedir(), '.cache', 'ms-playwright', name, 'chrome-linux', 'chrome'),
    ]);
  const executablePath = process.env.GS178_CHROMIUM || candidates.find(file => fs.existsSync(file));
  if (!executablePath) throw new Error('installed_test_chromium_unavailable');
  if (config.gs179LocalLanTestOnly !== true || !config.eventKey || !config.homeId) {
    throw new Error('explicit_local_test_profile_and_committed_event_required');
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath,
    args: ['--no-sandbox', '--disable-background-networking'],
  });
  try {
    const context = await browser.newContext();
    context.setDefaultTimeout(10000);
    const apiRequests = [];
    let activeRouteHandlers = 0;
    await context.route('**/*', async route => {
      activeRouteHandlers += 1;
      try {
      const url = new URL(route.request().url());
      if (url.origin !== origin) throw new Error(`unexpected_external_origin:${url.origin}`);
      if (url.pathname.startsWith('/lite/v1/')) {
        const response = await route.fetch();
        apiRequests.push({method: route.request().method(), path: url.pathname, status: response.status()});
        await route.fulfill({response});
        return;
      }
      if (!url.pathname.startsWith(prefix)) {
        await route.fulfill({status: 404, body: 'not found'});
        return;
      }
      const relative = url.pathname.slice(prefix.length);
      if (!relative || relative.startsWith('/') || relative.includes('\\') ||
          relative.split('/').some(part => part === '.' || part === '..')) {
        await route.fulfill({status: 404, body: 'not found'});
        return;
      }
      if (relative === 'runtime-config.js') {
        const body = `window.PARIVAR_SAATHI_RUNTIME=Object.freeze({mode:"caregiver",backendOrigin:${JSON.stringify(origin)},caregiverApiConfigured:true,gs179LocalLanTestOnly:true,appVersion:"GS179_LOCAL_LAN_TEST_ONLY",sourceRevision:"local"});`;
        await route.fulfill({status: 200, contentType: 'text/javascript', body,
          headers: {'cache-control': 'no-store'}});
        return;
      }
      const file = path.resolve(pwaRoot, relative);
      if (!file.startsWith(pwaRoot + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        await route.fulfill({status: 404, body: 'not found'});
        return;
      }
      const ext = path.extname(file).toLowerCase();
      const mime = ({'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript',
        '.css':'text/css','.webmanifest':'application/manifest+json','.json':'application/json',
        '.png':'image/png','.svg':'image/svg+xml','.ico':'image/x-icon'})[ext] || 'application/octet-stream';
      await route.fulfill({status: 200, contentType: mime, body: fs.readFileSync(file),
        headers: {'cache-control': 'no-store'}});
      } finally {
        activeRouteHandlers -= 1;
      }
    });

    const page = await context.newPage();
    await page.goto(`${origin}${prefix}index.html`);
    await page.getByLabel('Email').fill(config.email);
    await page.getByLabel('Password', {exact: true}).fill(config.password);
    await page.getByRole('button', {name: 'Log in', exact: true}).click();
    const eventCard = page.locator('[data-event-key]');
    await expect(eventCard).toHaveCount(1);
    const renderedKey = await eventCard.evaluate(node => JSON.parse(node.getAttribute('data-event-key')));
    expect(renderedKey).toEqual(config.eventKey);
    await expect(page.locator('#homeTab')).toContainText(config.eventDisplayKind);
    await expect(page.locator('#homeTab')).toContainText(config.room);
    await expect(eventCard).toHaveAttribute('data-source-origin', config.eventOrigin);
    await expect(page.locator('#homeTab')).toContainText('physical C3/S3 qualification NOT_RUN');
    if (config.sourceFreshness === 'CURRENT') {
      await expect(page.locator('#homeTab')).toContainText('Current observation coverage');
      expect(config.monitoring).toBe('COVERED');
      expect(config.nodeStatus).toBe('ONLINE');
      expect(config.nodeCoverage).toBe('COVERED');
    } else {
      await expect(page.locator('#homeTab')).toContainText(config.sourceFreshness === 'STALE'
        ? 'Monitoring source is stale'
        : 'Monitoring status is unknown');
      await expect(page.locator('#homeTab')).toContainText(
        'Device status is unavailable until source freshness and coverage are current.');
      expect(config.monitoring).toBe('UNKNOWN');
    }
    await expect(page.locator('#homeTab')).toContainText('Authenticated GS-148 TEST_ONLY caregiver data');

    await page.locator('[data-tab="devices"]').click();
    const node = page.locator(`[data-node-id="${config.physicalNodeId}"]`);
    await expect(node).toContainText(`${config.room} · ${config.nodeStatus}`);
    await expect(node).toContainText(config.nodeCoverage);
    for (const tabName of ['reports', 'settings']) {
      await expect(page.locator(`[data-tab="${tabName}"]`)).toBeVisible();
    }

    const engineeringStatus = await page.evaluate(async homeId => {
      const response = await fetch(`/lite/v1/homes/${encodeURIComponent(homeId)}/engineering`,
        {credentials: 'include'});
      return response.status;
    }, config.homeId);
    if (config.role === 'CAREGIVER') {
      expect(engineeringStatus).toBe(403);
      await expect(page.locator('[data-tab="engineering"]')).toHaveCount(0);
    } else if (config.role === 'ADMIN' && config.testOnly === true) {
      expect(engineeringStatus).toBe(200);
      await expect(page.locator('[data-tab="engineering"]')).toHaveCount(1);
    }

    await page.reload();
    await expect(page.locator('[data-event-key]')).toHaveCount(1);
    const reloadedKey = await page.locator('[data-event-key]')
      .evaluate(node => JSON.parse(node.getAttribute('data-event-key')));
    expect(reloadedKey).toEqual(config.eventKey);
    if (!apiRequests.some(item => item.path.endsWith('/overview') && item.status === 200) ||
        !apiRequests.some(item => item.path.endsWith('/devices') && item.status === 200)) {
      throw new Error('caregiver_api_projection_not_observed');
    }
    if (apiRequests.some(item => /\/sim\//.test(item.path))) {
      throw new Error('authorized_home_requested_simulator_data');
    }
    const loggedOut = await page.evaluate(async () => {
      const response = await fetch('/lite/v1/auth/logout', {method: 'POST', credentials: 'include'});
      return response.status;
    });
    expect(loggedOut).toBe(200);
    // Let any authorized freshness poll already in flight finish before the
    // browser context closes. Teardown must not turn a valid API response into
    // a disposed-context transport failure.
    await context.unroute('**/*');
    const routeDrainDeadline = Date.now() + 5000;
    while (activeRouteHandlers > 0 && Date.now() < routeDrainDeadline) {
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    if (activeRouteHandlers !== 0) throw new Error('browser_route_handlers_did_not_drain');
    console.log(JSON.stringify({
      status: 'HOST_SIM_PASS',
      pwa: 'canonical_bundle_against_laptop_https_api',
      event_key: renderedKey,
      event_kind: config.eventKind,
      room: config.room,
      event_origin: config.eventOrigin,
      source_freshness: config.sourceFreshness,
      monitoring: config.monitoring,
      node_status: config.nodeStatus,
      engineering_access: config.role === 'CAREGIVER' ? 'DENIED_AS_REQUIRED' : 'ROLE_GRANTED',
      reload_event_count: 1,
      api_requests: apiRequests,
      physical_phone: 'NOT_RUN',
    }));
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.stack);
  process.exit(1);
});
