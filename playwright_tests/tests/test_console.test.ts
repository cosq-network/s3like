import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:5000';

test('console can upload and list a file', async ({ page }) => {
  await page.goto(BASE);

  // If Basic Auth is configured, fill the login dialog
  const user = process.env.CONSOLE_USERNAME;
  const pass = process.env.CONSOLE_PASSWORD;
  if (user && pass) {
    await page.fill('input[name="username"]', user);
    await page.fill('input[name="password"]', pass);
    await page.click('button[type="submit"]');
  }

  // Upload a file
  const fileInput = page.locator('input[type="file"]');
  // Create a temporary file via playwright fixture approach; here we just set input files using a local path
  // For demo, assume 'upload_test.txt' exists in the test directory; playwright can accept a file path.
  await fileInput.setInputFiles('upload_test.txt');

  await page.click('button:has-text("Upload")');
  await expect(page.locator('text=upload_test.txt')).toBeVisible({ timeout: 5000 });

  // Verify the file appears in the bucket list
  await expect(page.locator('text=upload_test.txt')).toBeVisible();
});