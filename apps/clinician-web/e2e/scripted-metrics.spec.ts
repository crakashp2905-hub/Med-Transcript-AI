import {test, expect, localTestKey} from './fixtures/offline';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const root = resolve('../..');
const token=localTestKey;

test('record scripted workspace access interaction metrics', async ({ page }, testInfo) => {
  const errors: string[] = [];
  const resourceErrors: { status: number; url: string }[] = [];
  let clickCount = 0;
  let keyboardSteps = 0;
  page.on('pageerror', error => errors.push(`pageerror:${error.message}`));
  page.on('requestfailed', request => errors.push(`requestfailed:${request.url()}`));
  page.on('response', response => {
    if (response.status() >= 400) {
      resourceErrors.push({ status: response.status(), url: response.url() });
    }
  });
  await page.addInitScript(() => {
    document.addEventListener('click', () => {
      (window as Window & { __scriptedClicks?: number }).__scriptedClicks =
        ((window as Window & { __scriptedClicks?: number }).__scriptedClicks || 0) + 1;
    }, true);
    document.addEventListener('keydown', () => {
      (window as Window & { __scriptedKeys?: number }).__scriptedKeys =
        ((window as Window & { __scriptedKeys?: number }).__scriptedKeys || 0) + 1;
    }, true);
  });

  const started = Date.now();
  await page.goto('/');
  const load = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return Math.round(navigation.loadEventEnd - navigation.startTime);
  });
  await page.getByLabel('Access key').fill(token);
  const open = page.getByRole('button', { name: 'Open workspace', exact: false });
  await open.focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Open synthetic example', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Source transcript' })).toBeVisible();
  clickCount = await page.evaluate(() =>
    (window as Window & { __scriptedClicks?: number }).__scriptedClicks || 0,
  );
  keyboardSteps = await page.evaluate(() =>
    (window as Window & { __scriptedKeys?: number }).__scriptedKeys || 0,
  );
  const result = {
    schema_version: 'scripted_browser_interaction_metrics_v1',
    execution_kind: 'playwright_script',
    task_id: 'open-synthetic-workspace',
    task_completed: true,
    clicks: clickCount,
    keyboard_steps: keyboardSteps,
    page_load_latency_ms: load,
    script_wall_time_ms: Date.now() - started,
    interaction_errors: errors,
    error_count: errors.length,
    resource_errors: resourceErrors,
    human_observations: 0,
    clinical_acceptance: false,
  };
  const serialized = JSON.stringify(result, null, 2);
  await testInfo.attach('scripted-browser-interaction-metrics.json', {
    body: serialized,
    contentType: 'application/json',
  });
  const output = process.env.MTA_METRICS_OUTPUT;
  if (output) {
    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, `${serialized}\n`, 'utf8');
  }
  console.log(`MTA_SCRIPTED_METRICS ${JSON.stringify(result)}`);
  expect(result.task_completed).toBe(true);
  expect(result.keyboard_steps).toBeGreaterThan(0);
  expect(result.error_count).toBe(result.interaction_errors.length);
});

