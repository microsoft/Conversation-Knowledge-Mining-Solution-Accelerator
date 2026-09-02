// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('insights', () => {
  test('Insights filter panel exposes scenario-specific dimensions and Clear all', async ({ page }) => {
    // 1. Navigate to /insights and wait for the dashboard to load.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await page.getByText('Filter insights').first().waitFor({ state: 'visible' });

    // Expect: A 'Filter insights' block is visible with a 'Clear all' button.
    await expect(page.getByText('Filter insights')).toBeVisible();
    const clearAll = page.getByRole('button', { name: 'Clear all' });
    await expect(clearAll).toBeVisible();

    // 2. Enumerate the filter comboboxes in the 'Filter insights' block.
    const yearCombo = page.getByRole('combobox', { name: 'Year' });
    const sourceTypeCombo = page.getByRole('combobox', { name: 'Source Type' });
    const orgVariantCombo = page.getByRole('combobox', { name: 'Organization Name Variant' });
    const sourceCombo = page.getByRole('combobox', { name: 'Source', exact: true });
    const typeCombo = page.getByRole('combobox', { name: 'Type', exact: true });

    // Expect: Comboboxes are shown for at least: Year, Source Type, Organization Name Variant, Source, Type.
    await expect(yearCombo).toBeVisible();
    await expect(sourceTypeCombo).toBeVisible();
    await expect(orgVariantCombo).toBeVisible();
    await expect(sourceCombo).toBeVisible();
    await expect(typeCombo).toBeVisible();

    // Expect: Each combobox defaults to the value 'All'.
    await expect(yearCombo).toHaveText('All');
    await expect(sourceTypeCombo).toHaveText('All');
    await expect(orgVariantCombo).toHaveText('All');
    await expect(sourceCombo).toHaveText('All');
    await expect(typeCombo).toHaveText('All');

    // 3. Open the 'Source Type' combobox.
    await sourceTypeCombo.click();

    // Expect: The dropdown includes 'All', 'json', and 'wav'.
    await expect(page.getByRole('option', { name: 'All' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'json' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'wav' })).toBeVisible();

    // 4. Select 'json' in the 'Source Type' combobox, then click 'Clear all'.
    await page.getByRole('option', { name: 'json' }).click();

    // Expect: After selection, the combobox value updates to 'json'.
    await expect(sourceTypeCombo).toHaveText('json');

    await clearAll.click();

    // Expect: After 'Clear all', every combobox is restored to 'All'.
    await expect(yearCombo).toHaveText('All');
    await expect(sourceTypeCombo).toHaveText('All');
    await expect(orgVariantCombo).toHaveText('All');
    await expect(sourceCombo).toHaveText('All');
    await expect(typeCombo).toHaveText('All');
  });
});
