// spec: insights
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights suggested explorations expose clickable, dataset-specific prompts', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');

    // The section is rendered as a role=group whose accessible text starts with the section title
    // and caption run together as a single text node.
    const suggestedSection = page.getByRole('group').filter({ hasText: 'Suggested explorations' }).first();

    await expect(suggestedSection).toBeVisible();
    await expect(suggestedSection).toContainText('Suggested explorations');
    await expect(suggestedSection).toContainText('Conversation-ready prompts to drill into AI findings.');

    const promptButtons = suggestedSection.getByRole('button');
    expect(await promptButtons.count()).toBeGreaterThanOrEqual(6);

    await expect(
      suggestedSection.getByRole('button', { name: 'How do the findings change by year?' }),
    ).toBeVisible();
    await expect(
      suggestedSection.getByRole('button', { name: 'How do the findings change by source type?' }),
    ).toBeVisible();

    const datasetSpecificPrompt = suggestedSection.getByRole('button', {
      name: /interaction_type|resolution_status|source_type|issue_type/,
    });
    await expect(datasetSpecificPrompt.first()).toBeVisible();
    expect(await datasetSpecificPrompt.count()).toBeGreaterThanOrEqual(1);
  });
});
