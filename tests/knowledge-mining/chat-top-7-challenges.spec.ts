// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('chat-sample-questions', () => {
  test('Sample question 2: What are top 7 challenges user reported.', async ({ page }) => {
    test.setTimeout(120_000);
    const askTextarea = page.getByRole('textbox', { name: 'Ask a question...' });

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await expect(askTextarea).toBeVisible();

    // 2. Type the verbatim sample question and press Enter.
    await askTextarea.click();
    await askTextarea.fill('What are top 7 challenges user reported.');
    await askTextarea.press('Enter');

    // Wait for the assistant response to finish rendering (AI disclaimer marks completion).
    await expect(page.getByText('AI-generated content may be incorrect').first()).toBeVisible({ timeout: 90_000 });

    await expect(page.getByText('What are top 7 challenges user reported.')).toBeVisible();

    // Structural check: the assistant renders a list of at least 3 challenge entries
    // that references at least one telecom-flavored topic surfaced in Insights.
    const challengeItems = page.locator('ol li, ul li');
    expect(await challengeItems.count()).toBeGreaterThanOrEqual(3);
    await expect(page.locator('body')).toContainText(/billing|lost phone|plan|device|reset/i);

    await expect(page.getByText('AI-generated content may be incorrect').first()).toBeVisible();
  });
});
