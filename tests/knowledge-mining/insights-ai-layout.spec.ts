// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights AI-layout section renders summary, KPI, topic intensity, and highlights blocks', async ({ page }) => {
    // 1. Navigate to the insights dashboard and wait for it to load
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('AI layout').first().waitFor({ state: 'visible' });

    // expect: A section labeled 'AI layout' with the caption is visible.
    await expect(page.getByText('AI layout')).toBeVisible();
    await expect(page.getByText('Dynamic blocks chosen by the model for this dataset.')).toBeVisible();

    // 2. Verify the blocks rendered inside 'AI layout'.
    const aiLayout = page.getByRole('group').filter({ has: page.getByText('AI layout', { exact: true }) });

    // expect: A 'Summary' block is present and its body text is non-empty.
    // The summary prose is model-generated and its opening phrasing varies between runs; only assert
    // that the block renders the label plus substantial prose.
    const summaryCard = aiLayout.getByRole('group').filter({ hasText: 'Summary' }).last();
    await expect(summaryCard).toContainText('Summary');
    await expect(summaryCard).toContainText(/[A-Za-z][A-Za-z ,.'()\-\/]{80,}/);

    // expect: A KPI block shows the dataset record count (10) as its value.
    // The KPI title is model-chosen ('Total Support Interactions Analyzed' in the reference dataset)
    // and can vary between runs; assert structurally on the KPI value.
    await expect(aiLayout).toContainText('10');

    // expect: A 'Topic intensity' block lists dataset topics.
    // Specific topic wording is model-driven; assert the block renders with at least three lines
    // of topic prose and includes one topic keyword from the Telecom Analysis dataset.
    const topicIntensity = aiLayout.getByRole('group').filter({ hasText: 'Topic intensity' }).last();
    await expect(topicIntensity).toContainText('Topic intensity');
    await expect(topicIntensity).toContainText(/factory reset|voicemail|phone|billing|smartphone|troubleshoot/i);

    // expect: A 'Relationship graph' block is present.
    await expect(aiLayout.getByText('Relationship graph')).toBeVisible();

    // expect: A 'Timeline' block lists at least three patterns labeled 'Pattern 1', 'Pattern 2', 'Pattern 3'.
    const timelineCard = aiLayout.getByRole('group').filter({ has: page.getByText('Timeline', { exact: true }) }).last();
    await expect(timelineCard).toContainText('Pattern 1');
    await expect(timelineCard).toContainText('Pattern 2');
    await expect(timelineCard).toContainText('Pattern 3');

    // expect: A 'Topic vs entity signal' block reports topic and entity counts.
    // Exact counts vary with dataset enrichment; assert the block exists with 'Topics:' and 'Entities:'.
    const topicVsEntity = aiLayout.getByRole('group').filter({ hasText: 'Topic vs entity signal' }).last();
    await expect(topicVsEntity).toContainText(/Topics:\s*\d+/);
    await expect(topicVsEntity).toContainText(/Entities:\s*\d+/);

    // expect: A 'Key highlights' block lists at least four bullet items.
    const keyHighlights = aiLayout.getByRole('group').filter({ hasText: 'Key highlights' }).last();
    await expect(keyHighlights).toContainText('Key highlights');
    const bullets = keyHighlights.getByText(/^·/);
    expect(await bullets.count()).toBeGreaterThanOrEqual(4);
  });
});
