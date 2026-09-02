// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('chat-sample-questions', () => {
  test('Sample question 3: What are the top recommendations to reduce these customer challenges?', async ({ page }) => {
    test.setTimeout(180_000);
    const askInput = page.getByRole('textbox', { name: 'Ask a question...' });
    const disclaimer = page.getByText('AI-generated content may be incorrect');

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await expect(askInput).toBeVisible();

    // 2. First send the challenges question, wait for its response, then send the follow-up.
    await askInput.click();
    await askInput.fill('What are top 7 challenges user reported.');
    await askInput.press('Enter');
    await expect(disclaimer.first()).toBeVisible({ timeout: 90_000 });

    // Wait for the input to be re-enabled before firing the follow-up.
    await expect(askInput).toBeEnabled();
    await askInput.fill('What are the top recommendations to reduce these customer challenges?');
    await askInput.press('Enter');
    await expect(disclaimer).toHaveCount(2, { timeout: 90_000 });

    await expect(page.getByText('What are top 7 challenges user reported.')).toBeVisible();
    await expect(page.getByText('What are the top recommendations to reduce these customer challenges?')).toBeVisible();

    // Structural check: the follow-up response includes a list of recommendations that
    // references concrete dataset themes (self-service, billing, security workflows, or website / plan issues).
    const listItems = page.locator('ol li, ul li');
    expect(await listItems.count()).toBeGreaterThanOrEqual(3);
    await expect(page.locator('body')).toContainText(
      /self[- ]?serv|billing|remote lock|device blocking|website|plan|security/i,
    );

    await expect(disclaimer.last()).toBeVisible();
  });
});
