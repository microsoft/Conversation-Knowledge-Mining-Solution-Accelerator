// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights AI findings cards show insight text, score, and tag chips', async ({ page }) => {
    // 1. Navigate to the insights dashboard and wait for it to load
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');

    // expect: A section titled 'AI findings' with caption is visible and the help button is next to it.
    const helpButton = page.getByRole('button', { name: 'Document findings help' });
    await expect(helpButton).toBeVisible();
    await expect(page.getByText('Ranked by impact score, confidence, and evidence.')).toBeVisible();

    // 2. Inspect the first four AI-finding cards in the section.
    const section = page.getByRole('group').filter({ has: helpButton });
    const cards = section.getByRole('group');

    for (let i = 0; i < 4; i++) {
      const card = cards.nth(i);
      // expect: A short leading badge (Insight, Risk, etc.) followed by a 'Score N' value.
      // The badge label is model-chosen and varies between findings; only assert the score.
      await expect(card).toContainText(/Score\s+\d+/);
      // expect: non-empty body paragraph (substantial prose beyond the labels).
      await expect(card.getByText(/[A-Za-z][A-Za-z ,.'()\-\/]{40,}/)).toBeVisible();
      // expect: footer with 'Unified Knowledge Insights' source label and at least one hashtag chip.
      await expect(card).toContainText('Unified Knowledge Insights');
      await expect(card).toContainText(/#\w+/);
    }
  });
});
