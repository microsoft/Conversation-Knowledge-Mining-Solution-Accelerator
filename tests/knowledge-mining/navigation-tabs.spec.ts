// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('navigation', () => {
  test('Top navigation moves between Home, Insights, and Explore', async ({ page }) => {
    const nav = page.getByRole('navigation');
    const homeTab = nav.getByText('Home', { exact: true });
    const insightsTab = nav.getByText('Insights', { exact: true });
    const exploreTab = nav.getByText('Explore', { exact: true });

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/');
    await expect(page).toHaveURL('https://app-ckmmpoxx4d.azurewebsites.net/');
    // Active nav item is marked with a CSS-module class containing "navItemActive" on the parent div (not the span).
    await expect(nav.locator('[class*="navItemActive"]')).toContainText('Home');

    // 2. Click the 'Insights' navigation item.
    await insightsTab.click();
    await expect(page).toHaveURL('https://app-ckmmpoxx4d.azurewebsites.net/insights');
    await expect(page.getByText('Unified Knowledge Insights').first()).toBeVisible();

    // 3. Click the 'Explore' navigation item.
    await exploreTab.click();
    await expect(page).toHaveURL('https://app-ckmmpoxx4d.azurewebsites.net/explore');
    await expect(page.getByText('records', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('10 ready sources')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sources' })).toBeVisible();
    await expect(page.getByText('Filter dimensions')).toBeVisible();
    await expect(page.getByText('Ask your data')).toBeVisible();

    // 4. Click the 'Home' navigation item.
    await homeTab.click();
    await expect(page).toHaveURL('https://app-ckmmpoxx4d.azurewebsites.net/');
    await expect(page.getByText('Telecom Analysis Dataset')).toBeVisible();
  });
});
