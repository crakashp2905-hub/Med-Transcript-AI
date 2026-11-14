import { test, expect } from './fixtures/offline';

const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

for (const viewport of viewports) {
  test(`investor preview visual baseline · ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto('/investor-demo');
    await expect(page.getByRole('heading', {
      name: 'Keep every proposed statement connected to its source.',
    })).toBeVisible();
    await expect(page).toHaveScreenshot(`investor-preview-${viewport.name}.png`, {
      fullPage: true,
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.005,
    });
  });
}
