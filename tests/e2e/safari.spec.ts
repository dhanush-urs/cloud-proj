import { test, expect } from '@playwright/test';

test('add CentryAI repository successfully in Safari', async ({ page }) => {
  test.setTimeout(120000); // 2 minutes just in case

  console.log("Step 1: Navigating to http://localhost:3000 ...");
  await page.goto('/');

  console.log("Step 2: Checking for 'Add Repository' button...");
  const addButton = page.getByRole('button', { name: 'Add Repository' });
  await expect(addButton).toBeVisible();

  console.log("Step 3: Filling GitHub URL: https://github.com/Swarooppnair/CentryAI.git");
  const urlInput = page.getByPlaceholder('https://github.com/owner/repo');
  await urlInput.fill('https://github.com/Swarooppnair/CentryAI.git');

  console.log("Step 4: Submitting form...");
  await addButton.click();

  console.log("Step 5: Waiting for navigation to repository page...");
  await page.waitForURL(/\/repos\/.+/);

  console.log(`Step 6: Navigation successful. Current URL: ${page.url()}`);

  console.log("Step 7: Validating Repository Overview appears...");
  await expect(page.locator('text=Repository Overview')).toBeVisible({ timeout: 15000 });

  console.log("Test completed successfully!");
});
