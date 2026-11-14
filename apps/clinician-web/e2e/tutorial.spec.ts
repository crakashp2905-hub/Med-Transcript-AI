import { expect, test } from './fixtures/offline';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const accessKey = JSON.parse(
  readFileSync(resolve('../..', 'data/local-config.json'), 'utf8'),
).access_key;

test('synthetic first-run tutorial requires correction of its deliberate dose error', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Access key').fill(accessKey);
  await page.getByRole('button', { name: 'Open workspace', exact: false }).click();
  await page.getByRole('button', { name: 'Open detailed public example' }).click();
  await page.getByRole('button', { name: 'Start guided walkthrough' }).click();

  await expect(page.getByRole('heading', { name: 'Step 1: Listen and inspect' })).toBeVisible();
  await page.getByRole('button', { name: 'Next step', exact: true }).click();
  await page.getByRole('button', { name: 'Next step', exact: true }).click();

  const exercise = page.getByRole('region', { name: 'Synthetic dose correction exercise' });
  await expect(exercise.getByText(/Source: Take amoxicillin 250 mg orally twice daily for five days\./)).toBeVisible();
  await expect(exercise.getByText(/Draft proposal: Take amoxicillin 25 mg orally twice daily for five days\./)).toBeVisible();
  const next = page.getByRole('button', { name: 'Next step', exact: true });
  await expect(next).toBeDisabled();

  await exercise.getByRole('button', { name: 'Correct the draft to 250 mg' }).click();
  await expect(exercise.getByRole('status')).toHaveText(
    'Corrected proposal: amoxicillin 250 mg. The source remains unchanged.',
  );
  await expect(next).toBeEnabled();
  await next.click();
  await expect(page.getByRole('heading', { name: 'Step 4: Approve and export' })).toBeVisible();
  await expect(page.getByText('No approval is implied by completing this walkthrough.')).toBeVisible();
});
