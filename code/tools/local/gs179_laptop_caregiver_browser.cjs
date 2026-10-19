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
    await context.route('**/*', async route => {
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
    await expect(page.locator('#homeTab')).toContainText(config.eventKind);
    await expect(page.locator('#homeTab')).toContainText(config.room);
    await expect(page.locator('#homeTab .card').filter({
      has: page.getByRole('heading', {name: 'Home monitoring', exact: true}),
    })).toContainText('COVERED');
    await expect(page.locator('#homeTab')).toContainText('Backend source freshness: CURRENT');
    await expect(page.locator('#homeTab')).toContainText('AUTHENTICATED_GS148_TEST_ONLY');

    await page.getByRole('button', {name: 'devices', exact: true}).click();
    const node = page.locator(`[data-node-id="${config.physicalNodeId}"]`);
    await expect(node).toContainText(`${config.room} · ONLINE`);
    await expect(node).toContainText('COVERED');

    await page.reload();
    await expect(page.locator('[data-event-key]')).toHaveCount(1);
    const reloadedKey = await page.locator('[data-event-key]')
      .evaluate(node => JSON.parse(node.getAttribute('data-event-key')));
    expect(reloadedKey).toEqual(config.eventKey);
    if (!apiRequests.some(item => item.path.endsWith('/overview') && item.status === 200) ||
        !apiRequests.some(item => item.path.endsWith('/devices') && item.status === 200)) {
      throw new Error('caregiver_api_projection_not_observed');
    }
    console.log(JSON.stringify({
      status: 'HOST_SIM_PASS',
      pwa: 'canonical_bundle_against_laptop_https_api',
      event_key: renderedKey,
      event_kind: config.eventKind,
      room: config.room,
      monitoring: 'COVERED',
      node_status: 'ONLINE',
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
