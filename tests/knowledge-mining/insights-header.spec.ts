// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights dashboard renders Unified Knowledge Insights header and metadata', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the 'Loading dashboard' progressbar to disappear.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('Loading dashboard').first().waitFor({ state: 'hidden' });

    await expect(page.getByRole('heading', { name: 'Unified Knowledge Insights', level: 1 })).toBeVisible();
    await expect(page.getByText('Insights overview')).toBeVisible();
    await expect(page.getByText(/^Dataset:/)).toBeVisible();
    await expect(page.getByText('Source: documents')).toBeVisible();
    await expect(page.getByText(/^Updated:\s*\d/)).toBeVisible();

    // 2. Observe the header actions.
    await expect(page.getByRole('button', { name: 'Ask your data' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });
});
