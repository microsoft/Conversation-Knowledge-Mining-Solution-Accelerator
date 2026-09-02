// spec: n/a
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('explore', () => {
  test('Explore page loads sources, filter dimensions, and chat panel', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await page.getByText('10 ready sources').first().waitFor({ state: 'visible' });

    await expect(page.getByText('10 ready sources')).toBeVisible();
    // Header renders '10' in its own generic followed by an adjacent 'records' text node,
    // so match the combined header content via regex instead of an exact-text lookup.
    await expect(page.locator('body')).toContainText(/10\s+records/);
    await expect(page.getByRole('button', { name: /^History \(\d+\)$/ })).toBeVisible();

    // 2. Inspect the 'Sources' panel on the left.
    await expect(page.getByRole('button', { name: 'Sources' })).toBeVisible();

    // Each source row renders '<filename> <count>' as its inner text, so match the leading
    // filename fragment without anchoring the trailing count.
    const sourceItems = page.getByText(/^convo_[0-9a-f-]+.*\.(wav|json)\b/);
    await expect(sourceItems).toHaveCount(10);
    for (let i = 0; i < 10; i++) {
      const row = sourceItems.nth(i).locator('..');
      await expect(row).toContainText(/\d+/);
    }

    // 3. Inspect the 'Filter dimensions' panel.
    await expect(page.getByText('Filter dimensions')).toBeVisible();
    await expect(page.getByTitle('Use these to narrow records before asking questions')).toBeVisible();

    const filterLabels = [
      'Source Type',
      'Topic',
      'Document Type',
      'Interaction Type',
      'Resolution Status',
      'Interaction Reason',
      'Agent',
      'Products Or Programs',
      'Organization',
      'Customer',
      'Topics',
      'Issue Type',
      'Issue Category',
      'Customer Intent',
      'Account Number',
      'Support Agent',
      'Primary Service Area',
      'Key Phrases',
      'Entities',
    ];
    for (const label of filterLabels) {
      const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      await expect(
        page.getByRole('button', { name: new RegExp(`^${escaped} \\(\\d+\\)$`) })
      ).toBeVisible();
    }

    // 4. Inspect the chat panel on the right.
    await expect(page.getByText('Ask your data')).toBeVisible();
    await expect(
      page.getByText('Summaries, trends, and analysis — all through conversation.')
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'New conversation' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Ask a question...' })).toBeVisible();
    const sendButton = page.getByRole('button', { name: 'Send' });
    await expect(sendButton).toBeVisible();
    await expect(sendButton).toBeDisabled();
  });
});
