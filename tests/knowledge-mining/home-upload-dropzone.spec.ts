// spec: specs/knowledge-mining.md
// seed: tests/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('home', () => {
  test('Upload dropzone advertises all supported file formats', async ({ page }) => {
    // Stub ingestion endpoints so the Home hero renders its empty-state dropzone.
    await page.route('**/api/ingestion/files', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.route('**/api/data-sources/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );

    // 1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/ and locate the upload dropzone in the hero section.
    await page.goto('https://app-ckmmpoxx4d.azurewebsites.net/');

    const dropzone = page.locator('[class*="uploadCard"]');
    await expect(dropzone).toBeVisible();
    await expect(dropzone.getByText('Upload supported files', { exact: true })).toBeVisible();
    await expect(dropzone.getByText('Drag & drop or click to browse')).toBeVisible();

    // 2. Read the format chips inside the dropzone. Live app renders chips as flat text nodes,
    //    so assert the full ordered chip sequence appears as substring content in the dropzone.
    const expectedChips = ['PDF', 'DOCX', 'JSON', 'CSV', 'XLSX', 'TXT', 'PNG', 'JPG', 'WAV', 'MP3', 'MP4'];
    for (const chip of expectedChips) {
      await expect(dropzone).toContainText(chip);
    }
    const chipOrderRegex = new RegExp(expectedChips.join('[\\s\\S]*'));
    await expect(dropzone).toContainText(chipOrderRegex);
  });
});
