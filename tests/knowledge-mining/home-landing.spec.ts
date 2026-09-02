// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('home', () => {
  test('Home page renders scenario summary and primary navigation', async ({ page }) => {
    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/');
    await expect(page).toHaveTitle('Knowledge Mining Platform');
    await expect(page.getByText('Knowledge Mining').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();

    const nav = page.getByRole('navigation');
    await expect(nav).toBeVisible();
    await expect(nav.getByText('Home', { exact: true })).toBeVisible();
    await expect(nav.getByText('Insights', { exact: true })).toBeVisible();
    await expect(nav.getByText('Explore', { exact: true })).toBeVisible();
    // Home is the selected/active nav item (CSS-module active class is on the parent div, not the span).
    await expect(nav.locator('[class*="navItemActive"]')).toContainText('Home');

    // 2. Observe the hero section on the Home view.
    await expect(page.getByText('Turn your data into answers and insights')).toBeVisible();
    await expect(page.getByText('Upload supported files to enrich your knowledge base.')).toBeVisible();

    // 3. Observe the loaded-dataset summary card in the hero row.
    await page.getByText('Telecom Analysis Dataset').first().waitFor({ state: 'visible' });
    await expect(page.getByText('Telecom Analysis Dataset')).toBeVisible();
    await expect(page.getByText('✓ 10 processed')).toBeVisible();
    await expect(page.getByText('📎 10 files')).toBeVisible();

    // 4. Live app renders a 'What you can do' capability section (spec called it 'Getting started').
    await expect(page.getByText('What you can do', { exact: true })).toBeVisible();
    await expect(page.getByText('Extract insights', { exact: true })).toBeVisible();
    await expect(page.getByText('Ask questions', { exact: true })).toBeVisible();
    await expect(page.getByText('Structure outputs', { exact: true })).toBeVisible();
  });
});
