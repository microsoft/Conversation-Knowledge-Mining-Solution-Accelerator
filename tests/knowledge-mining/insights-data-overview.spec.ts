// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights data overview shows scenario record and enrichment counts', async ({ page }) => {
    // 1. Navigate to the insights dashboard and wait for it to load.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('Data overview').first().waitFor({ state: 'visible' });

    // expect: 'Data overview' section is visible with its caption.
    await expect(page.getByText('Data overview')).toBeVisible();
    await expect(
      page.getByText('A quick snapshot of record count, extracted topics, entities, and links.')
    ).toBeVisible();

    // 2. Read the four KPI tiles inside 'Data overview'.
    const tile = (label: string) =>
      page.getByRole('group').filter({ has: page.getByText(label, { exact: true }) }).first();

    // expect: 'Records analyzed' tile shows the numeric value '10'.
    const recordsTile = tile('Records analyzed');
    await expect(recordsTile.getByText('Records analyzed', { exact: true })).toBeVisible();
    await expect(recordsTile.getByText('10', { exact: true })).toBeVisible();

    // expect: 'Topics identified' tile shows the numeric value '25'.
    const topicsTile = tile('Topics identified');
    await expect(topicsTile.getByText('Topics identified', { exact: true })).toBeVisible();
    await expect(topicsTile.getByText('25', { exact: true })).toBeVisible();

    // expect: 'Entities extracted' tile shows the numeric value '13'.
    const entitiesTile = tile('Entities extracted');
    await expect(entitiesTile.getByText('Entities extracted', { exact: true })).toBeVisible();
    await expect(entitiesTile.getByText('13', { exact: true })).toBeVisible();

    // expect: 'Relationship links' tile shows the numeric value '3'.
    const linksTile = tile('Relationship links');
    await expect(linksTile.getByText('Relationship links', { exact: true })).toBeVisible();
    await expect(linksTile.getByText('3', { exact: true })).toBeVisible();

    // expect: Each tile shows a short helper caption describing what it counts.
    await expect(recordsTile.getByText('How many records are in the current view.')).toBeVisible();
    await expect(topicsTile.getByText('Distinct topics found in document content.')).toBeVisible();
    await expect(entitiesTile.getByText('Named entities detected across records.')).toBeVisible();
    await expect(linksTile.getByText('Detected links between entities/topics.')).toBeVisible();
  });
});
