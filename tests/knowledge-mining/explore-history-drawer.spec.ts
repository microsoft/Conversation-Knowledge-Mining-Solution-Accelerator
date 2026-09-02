// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('explore', () => {
  test('History drawer lists past conversations with message counts', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/explore');

    // Wait for the History button to render its numeric count and verify format.
    const historyButton = page.getByRole('button', { name: /^History \(\d+\)$/ });
    await expect(historyButton).toBeVisible();

    // 2. Click the 'History' button.
    await historyButton.click();

    // Verify the Chat History drawer opened with expected affordances. The drawer header renders
    // 'Chat History' as a text node next to the close button, so match it via substring.
    await expect(page.getByText('Chat History')).toBeVisible();
    await expect(page.getByText('New conversation').first()).toBeVisible();

    // Drawer lists at least one past conversation with an 'N messages' counter.
    const messageCounters = page.getByText(/^\d+ messages$/);
    await expect(messageCounters.first()).toBeVisible();
    expect(await messageCounters.count()).toBeGreaterThanOrEqual(1);

    // Close ('x') affordance inside the drawer.
    const closeButton = page.getByRole('button', { name: 'x' });
    await expect(closeButton).toBeVisible();

    // 3. Click the close ('x') affordance in the drawer.
    await closeButton.click();

    // Drawer closed; Explore sources / filters / chat panels are visible again.
    await expect(page.getByText('Chat History')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Sources' })).toBeVisible();
    // Layout re-mounts after the drawer overlay dismisses; give the text a longer settle window.
    await expect(page.getByText('Filter dimensions').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Ask your data')).toBeVisible();
  });
});
