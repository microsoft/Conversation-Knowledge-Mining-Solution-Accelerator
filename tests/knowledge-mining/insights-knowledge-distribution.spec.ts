// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Insights', () => {
  test('Insights knowledge distribution shows Topic share ranking and Entity frequency chart', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('Knowledge distribution').first().waitFor({ state: 'visible' });

    await expect(page.getByText('Knowledge distribution')).toBeVisible();
    await expect(page.getByText('See which topics dominate and which entities are mentioned most.')).toBeVisible();

    // 2. Inspect the 'Topic share' block.
    const topicShareBlock = page.getByRole('group').filter({ hasText: 'Topic share' }).first();
    await expect(topicShareBlock).toBeVisible();
    // The block contains two '8' badges (topic count + adjacent legend); assert at least one.
    await expect(topicShareBlock.getByText('8', { exact: true }).first()).toBeVisible();
    await expect(topicShareBlock.getByText('factory reset')).toBeVisible();
    await expect(topicShareBlock.getByText('22.2%')).toBeVisible();
    await expect(topicShareBlock.getByText('Voicemail and call forwarding setup')).toBeVisible();
    await expect(topicShareBlock.getByText('Reporting and securing a lost phone')).toBeVisible();
    await expect(topicShareBlock.getByText('Phone troubleshooting: freezing and battery drain')).toBeVisible();
    await expect(topicShareBlock.getByText('11.1%').first()).toBeVisible();

    // 3. Inspect the 'Entity frequency' block.
    const entityFrequencyBlock = page.getByRole('group').filter({ hasText: 'Entity frequency' }).first();
    await expect(entityFrequencyBlock).toBeVisible();
    await expect(entityFrequencyBlock.getByText('8', { exact: true }).first()).toBeVisible();
    await expect(entityFrequencyBlock.getByRole('img')).toBeVisible();
  });
});
