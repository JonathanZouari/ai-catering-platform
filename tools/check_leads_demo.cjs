// Browser regression against the local synthetic-only demo.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || undefined });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:8771/admin/leads-demo/');
    await page.waitForFunction(() => document.querySelectorAll('article').length === 5);
    const fixture = await (await page.request.get('http://127.0.0.1:8771/demo/leads.json')).json();
    const expected = [...fixture.leads].sort((a, b) => b.demo_probability - a.demo_probability || a.id.localeCompare(b.id)).slice(0, 5).map(row => row.name);
    assert.deepEqual(await page.locator('article h2').allTextContents(), expected);
    assert.equal(await page.locator('#sort').isDisabled(), true);
    assert.ok((await page.locator('.notice').innerText()).includes('סינתטיים בלבד'));
    await page.selectOption('#filter', 'higher');
    const higher = await page.locator('article').count();
    assert.ok(higher > 0 && higher < 24);
    await page.selectOption('#filter', 'lower');
    assert.equal((await page.locator('article').count()) + higher, 24);
    await page.selectOption('#filter', 'all');
    assert.equal(await page.locator('article').count(), 24);
    assert.equal(await page.locator('#sort').isDisabled(), false);
    await page.selectOption('#sort', 'name');
    assert.equal(await page.locator('article h2').first().innerText(), 'פונה לדוגמה 1201');
    await page.selectOption('#filter', 'top5');
    assert.deepEqual(await page.locator('article h2').allTextContents(), expected);
    if (process.env.EVIDENCE_PATH) await page.screenshot({ path: process.env.EVIDENCE_PATH, fullPage: false });
    await page.setViewportSize({ width: 320, height: 740 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    console.log('PASS: exact top-five ranking by default and after switching, all 24 retained, filters, sorting, demo notice, 320px reflow, no JS errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
