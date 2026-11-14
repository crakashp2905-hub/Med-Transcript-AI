import { test, expect } from './fixtures/offline';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve('../..');
const token = process.env.MED_TRANSCRIPT_TEST_KEY ||
  JSON.parse(readFileSync(resolve(root, 'data/local-config.json'), 'utf8')).access_key;
const artifactDir = resolve(root, 'evaluation/usability/artifacts');

test('capture local synthetic desktop and mobile states for heuristic review', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  mkdirSync(artifactDir, { recursive: true });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to your workspace' })).toBeVisible();
  await page.keyboard.press('Tab');
  const firstFocus = await page.evaluate(() => ({
    tag: document.activeElement?.tagName.toLowerCase(),
    type: (document.activeElement as HTMLInputElement | null)?.type || null,
    label: document.activeElement?.getAttribute('aria-label') || null,
  }));
  await page.screenshot({ path: resolve(artifactDir, 'login-desktop.png') });

  await page.getByLabel('Access key').fill(token);
  const open = page.getByRole('button', { name: 'Open workspace', exact: false });
  await open.focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Open synthetic example', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Source transcript' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Encounters' })).toBeVisible();
  await expect(page.getByRole('main')).toBeVisible();
  await page.screenshot({ path: resolve(artifactDir, 'workspace-desktop.png'), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Source & transcript', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Source transcript' })).toBeVisible();
  const mobile = await page.evaluate(() => ({
    viewport_width: window.innerWidth,
    document_width: document.documentElement.scrollWidth,
    horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth,
  }));
  await page.screenshot({ path: resolve(artifactDir, 'source-mobile.png'), fullPage: true });

  const controls = await page.locator('button,input,select,textarea').evaluateAll(elements => {
    const nameOf = (element: Element) => {
      const control = element as HTMLInputElement;
      const labels = control.labels ? Array.from(control.labels).map(label => label.innerText).join(' ').trim() : '';
      return control.getAttribute('aria-label') || control.getAttribute('aria-labelledby') || labels || control.innerText?.trim() || '';
    };
    const unnamed = elements.filter(element =>
      element instanceof HTMLElement && element.checkVisibility() && !nameOf(element),
    ).map(element => ({
      tag: element.tagName.toLowerCase(),
      type: (element as HTMLInputElement).type || null,
      id: element.id || null,
    }));
    return { control_count: elements.length, unnamed_controls: unnamed };
  });
  const result = { first_focus: firstFocus, mobile, controls, page_errors: pageErrors };
  writeFileSync(
    resolve(artifactDir, 'browser-observations.json'),
    `${JSON.stringify(result, null, 2)}\n`,
    'utf8',
  );
  await test.info().attach('usability-audit-observations.json', {
    body: JSON.stringify(result, null, 2), contentType: 'application/json',
  });
  expect(firstFocus.tag).toBe('input');
  expect(mobile.horizontal_overflow).toBe(false);
  expect(controls.unnamed_controls).toEqual([]);
  expect(pageErrors).toEqual([]);
});
