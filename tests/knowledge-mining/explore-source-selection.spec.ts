// spec: n/a
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('explore', () => {
  test('Selecting a source narrows the record counter', async ({ page }) => {
    const header = page.getByText('records').first().locator('..');
    const closeButton = page.getByRole('button', { name: 'x' });

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await page.getByText('10 ready sources').first().waitFor({ state: 'visible' });
    // Header renders '10' + 'records' as sibling text nodes; use a substring regex on the body.
    await expect(page.locator('body')).toContainText(/10\s+records/);
    await expect(page.getByText('10 ready sources')).toBeVisible();

    // 2. Click the source row whose filename begins with 'convo_03b0e193-5b55-42d3-a258-b0ff9336ae18'.
    await page
      .getByText(/^convo_03b0e193-5b55-42d3-a258-b0ff9336ae18.*\.wav/)
      .click();
    await expect(page.getByText('1 selected')).toBeVisible();
    await expect(closeButton).toBeVisible();

    // 3. Click the close ('x') affordance to clear the source selection.
    await closeButton.click();
    await expect(page.getByText('10 ready sources')).toBeVisible();
    await expect(page.getByText('1 selected')).toHaveCount(0);
  });
});
