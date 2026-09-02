// spec: chat-sample-questions
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('chat-sample-questions', () => {
  test('Sample question 1: Total number of calls by date for last 7 days.', async ({ page }) => {
    test.setTimeout(120_000);
    const askInput = page.getByRole('textbox', { name: 'Ask a question...' });
    const historyButton = page.getByRole('button', { name: /^History \(\d+\)$/ });

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await expect(askInput).toBeVisible();
    await expect(historyButton).toBeVisible();
    const initialHistoryText = (await historyButton.textContent()) ?? '';
    const initialHistoryCount = parseInt(initialHistoryText.match(/\d+/)![0], 10);

    // 2. Type the verbatim sample question and press Enter.
    await askInput.fill('Total number of calls by date for last 7 days.');
    await askInput.press('Enter');

    // The user question is echoed and the assistant response finishes (marked by the disclaimer).
    await expect(page.getByText('Total number of calls by date for last 7 days.')).toBeVisible();
    await expect(page.getByText('AI-generated content may be incorrect').first()).toBeVisible({ timeout: 90_000 });

    // Structural check: the assistant renders a two-column table with a date-like column header
    // and a totals column, plus at least one row whose last cell is a positive integer.
    const table = page.locator('table').first();
    await expect(table).toBeVisible();
    await expect(table.locator('th')).toContainText([/date/i, /calls|total/i]);
    await expect(
      table.locator('tbody tr').first().locator('td').last(),
    ).toHaveText(/^[1-9]\d*$/);

    // 3. Observe the 'History' button counter increases by at least 1.
    // The counter ticks asynchronously; poll the button label numerically instead of waiting
    // for a specific value string, which is subject to concurrent test-run drift.
    await expect
      .poll(
        async () => {
          const text = (await historyButton.textContent()) ?? '';
          const match = text.match(/\d+/);
          return match ? parseInt(match[0], 10) : -1;
        },
        { timeout: 60_000 },
      )
      .toBeGreaterThan(initialHistoryCount);
  });
});
