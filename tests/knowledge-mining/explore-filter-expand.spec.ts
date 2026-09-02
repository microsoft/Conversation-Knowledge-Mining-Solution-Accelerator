// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('explore', () => {
  test('Explore filter dimension can be expanded to show scenario values with counts', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await page.getByRole('button', { name: 'Sources' }).click();
    const sourceTypeButton = page.getByRole('button', { name: 'Source Type (2)' });
    await expect(sourceTypeButton).toBeVisible();

    // 2. Click 'Source Type (2)' to expand it.
    await sourceTypeButton.click();
    await expect(page.getByRole('button', { name: 'wav' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'json' })).toBeVisible();

    // 3. Click 'Interaction Type (7)' to expand it.
    await page.getByRole('button', { name: 'Interaction Type (7)' }).click();
    await expect(page.getByRole('button', { name: 'customer_support_call' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'customer support call' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'loyalty_rewards_inquiry' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'customer support conversation' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'support_call 1' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'lost_phone_report' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'device_troubleshooting_repair' })).toBeVisible();
  });
});
