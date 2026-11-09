// npm install --no-save playwright axe-core; node frontend/tests/accessibility.mjs
// Only runs against a local demo app, in fresh browser contexts without credentials.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const axePath = process.env.AXE_PATH || require.resolve('axe-core/axe.min.js');
const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:8770';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, headless: true });
const results = [];
async function test(name, fn) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage(); const errors = [];
  page.setDefaultTimeout(10000);
  page.on('pageerror', e => errors.push(e.message));
  try { await fn(page); assert.deepEqual(errors, []); results.push({ name, passed: true }); }
  catch (e) { results.push({ name, passed: false, error: e.message }); }
  finally { console.log(name, results.at(-1).passed ? 'PASS' : results.at(-1).error); await context.close(); }
}
async function audit(page) {
  await page.addScriptTag({ path: axePath });
  const violations = await page.evaluate(async () => (await axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] }
  })).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })));
  assert.deepEqual(violations, []);
}
async function event(page) {
  await page.goto(base + '/customer/');
  await page.getByLabel('יום הולדת', { exact: true }).focus();
  await page.keyboard.press('Space');
  const date = page.locator('#f-date'); await date.fill(await date.getAttribute('min'));
  await page.locator('#f-slot').selectOption({ index: 1 });
}
async function menu(page) {
  await event(page); await page.getByRole('button', { name: 'המשך לתפריט' }).click();
  await page.locator('.dish-card').first().waitFor();
}
try {
  await test('Landing skip, statement, axe and 320px reflow', async page => {
    await page.goto(base); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'main'); await audit(page);
    await page.setViewportSize({ width: 320, height: 740 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.getByRole('link', { name: 'הצהרת נגישות', exact: true }).click();
    await page.getByRole('heading', { name: 'הצהרת נגישות', exact: true }).waitFor(); await audit(page);
    assert.equal(await page.locator('a[href^="mailto:"]').getAttribute('href'), 'mailto:ravvitre@gmail.com');
    if (process.env.EVIDENCE_DIR) {
      await page.setViewportSize({ width: 1000, height: 1000 });
      await page.screenshot({ path: process.env.EVIDENCE_DIR + '/accessibility-statement.png', fullPage: true });
    }
  });
  await test('Dietary/adult errors block navigation, focus and describe inputs', async page => {
    await event(page);
    await page.locator('#f-adults').fill('1'); await page.locator('#f-adults').blur();
    await page.locator('#f-vegan').fill('2'); await page.locator('#f-vegan').blur();
    await page.getByRole('button', { name: 'המשך לתפריט' }).click();
    assert.ok(page.url().endsWith('#event'));
    assert.equal(await page.locator('#f-vegan').getAttribute('aria-invalid'), 'true');
    assert.match(await page.locator('#f-vegan').getAttribute('aria-describedby'), /err-dietary/);
    assert.ok(['f-vegetarian', 'f-vegan', 'f-restricted'].includes(await page.evaluate(() => document.activeElement.id)));
    await audit(page);
    await page.locator('#f-vegan').fill('0'); await page.locator('#f-vegan').blur();
    await page.locator('#f-adults').fill('0'); await page.locator('#f-adults').blur();
    await page.getByRole('button', { name: 'המשך לתפריט' }).click();
    assert.equal(await page.evaluate(() => document.activeElement.id), 'f-adults');
    assert.match(await page.locator('#f-adults').getAttribute('aria-describedby'), /err-adults/);
  });
  await test('Mobile chat traps keyboard, restores focus and releases on resize', async page => {
    await page.setViewportSize({ width: 390, height: 844 }); await menu(page);
    await page.getByRole('button', { name: 'שאלו את העוזר' }).click();
    assert.equal(await page.locator('#chat-panel').getAttribute('aria-modal'), 'true');
    assert.equal(await page.locator('#app').evaluate(el => el.inert), true);
    for (const key of ['Tab', 'Shift+Tab']) for (let i = 0; i < 12; i++) {
      await page.keyboard.press(key);
      assert.equal(await page.evaluate(() => document.querySelector('#chat-panel').contains(document.activeElement)), true);
    }
    await audit(page);
    if (process.env.EVIDENCE_DIR) await page.screenshot({ path: process.env.EVIDENCE_DIR + '/accessibility-mobile-chat.png' });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.waitForFunction(() => !document.querySelector('#app').inert);
    assert.equal(await page.locator('#chat-panel').getAttribute('aria-modal'), null);
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(() => document.activeElement.classList.contains('chat-fab')), true);
  });
  await test('Catalog dialog, summary removal, validation, demo submission and reload', async page => {
    await menu(page); await audit(page);
    const card = page.locator('.dish-card').first();
    const allergen = card.getByRole('button', { name: /מידע על אלרגנים/ });
    await allergen.click(); await audit(page); await page.keyboard.press('Escape');
    assert.equal(await allergen.evaluate(el => el === document.activeElement), true);
    await card.getByRole('button', { name: /^הוספה:/ }).click();
    await page.getByRole('button', { name: 'לסיכום ההזמנה', exact: true }).first().click(); await audit(page);
    await page.getByRole('button', { name: /^הפחתת כמות:/ }).click();
    assert.equal(await page.evaluate(() => document.activeElement.textContent), 'חזרה לתפריט');
    await page.keyboard.press('Enter');
    await page.locator('.dish-card').first().getByRole('button', { name: /^הוספה:/ }).click();
    await page.getByRole('button', { name: 'לסיכום ההזמנה', exact: true }).first().click();
    await page.getByRole('button', { name: 'שליחת בקשה להצעת מחיר', exact: true }).click();
    assert.equal(await page.evaluate(() => document.activeElement.id), 'f-name');
    await page.getByLabel('שם מלא', { exact: true }).fill('בדיקת נגישות');
    await page.getByLabel('טלפון', { exact: true }).fill('0500000000');
    await page.getByRole('button', { name: 'שליחת בקשה להצעת מחיר', exact: true }).click();
    await page.waitForURL('**/#status'); await audit(page); await page.reload();
    await page.locator('#app h1').waitFor(); assert.ok(page.url().endsWith('#status')); await audit(page);
  });
  await test('Admin status and statement link', async page => {
    await page.goto(base + '/admin/');
    await page.waitForFunction(() => document.querySelector('#status').textContent === 'השרת זמין'); await audit(page);
  });
} finally { await browser.close(); }
console.log(JSON.stringify(results, null, 2));
if (process.env.RESULT_PATH) await writeFile(process.env.RESULT_PATH, JSON.stringify(results, null, 2));
if (results.some(r => !r.passed)) process.exitCode = 1;
