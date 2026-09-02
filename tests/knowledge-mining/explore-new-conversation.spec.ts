// spec: 'New conversation' clears the chat input and starts a fresh session
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('explore', () => {
  // Live app regression: clicking 'New conversation' does not clear the textarea or disable Send.
  test.fixme("'New conversation' clears the chat input and starts a fresh session", async ({ page }) => {
    const askTextbox = page.getByRole('textbox', { name: 'Ask a question...' });
    const sendButton = page.getByRole('button', { name: 'Send' });
    const newConversationButton = page.getByRole('button', { name: 'New conversation' });

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore and type 'hello' into the 'Ask a question...' textarea (do NOT submit).
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await askTextbox.fill('hello');
    await expect(askTextbox).toHaveValue('hello');
    await expect(sendButton).toBeEnabled();

    // 2. Click 'New conversation'.
    await newConversationButton.click();
    await expect(page.getByText('Ask your data')).toBeVisible();
    await expect(page.getByText('Summaries, trends, and analysis — all through conversation.')).toBeVisible();
    await expect(askTextbox).toHaveValue('');
    await expect(sendButton).toBeDisabled();
  });
});
