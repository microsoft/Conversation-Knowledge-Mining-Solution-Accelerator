// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('chat-sample-questions', () => {
  test('Suggested exploration prompt from Insights triggers a chat response in Explore', async ({ page }) => {
    test.setTimeout(120_000);

    // 1. Navigate to the Insights dashboard and wait for it to load
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('Suggested explorations').first().waitFor({ state: 'visible' });
    await expect(page.getByText('Suggested explorations')).toBeVisible();

    // 2. Click a suggested prompt about resolution_status vs source_type. The exact prompt wording
    // is model-generated; prefer one that mentions both dimensions but fall back to any prompt that
    // references 'source_type' so the test survives Suggested-Explorations regeneration.
    const suggestedSection = page.getByRole('group').filter({ hasText: 'Suggested explorations' }).first();
    const preferredPrompt = suggestedSection.getByRole('button', {
      name: /resolution_status[\s\S]*source_type|source_type[\s\S]*resolution_status/i,
    });
    const fallbackPrompt = suggestedSection.getByRole('button', { name: /source_type/i });
    const promptButton = (await preferredPrompt.count()) > 0
      ? preferredPrompt.first()
      : fallbackPrompt.first();
    await expect(promptButton).toBeVisible({ timeout: 30_000 });
    const promptText = (await promptButton.textContent())?.trim() ?? '';
    await promptButton.click();

    // URL should route to the Explore chat surface
    await expect(page).toHaveURL(/\/explore/);

    // Wait for the assistant response to render (disclaimer marks completion).
    await expect(page.getByText('AI-generated content may be incorrect').first()).toBeVisible({ timeout: 90_000 });

    // The prompt is echoed as the user question in the transcript. Use a fragment of the button's
    // captured text so smart-quote / whitespace differences in the transcript don't break the check.
    const promptFragment = promptText.split(/[?.!]/)[0].trim().slice(0, 40);
    if (promptFragment.length > 0) {
      await expect(page.getByText(promptFragment, { exact: false }).first()).toBeVisible();
    }

    // The assistant response references the prompted dimensions plus at least one source-type value.
    // The response formatting is model-generated; assert on text content rather than a specific tag.
    await expect(page.locator('body')).toContainText('source_type');
    await expect(page.locator('body')).toContainText(/\bjson\b|\bwav\b/);

    // The AI disclaimer is shown below the response
    await expect(page.getByText('AI-generated content may be incorrect').first()).toBeVisible();
  });
});
