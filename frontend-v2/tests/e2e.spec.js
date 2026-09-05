import { test, expect } from '@playwright/test';

test('critical demo flow: search, negotiation, checkout', async ({ page }) => {
  await page.goto('http://localhost:5173'); // Default vite port
  
  const searchInput = page.locator('textarea').first();
  await expect(searchInput).toBeVisible({ timeout: 15000 });
  
  await searchInput.fill('black hoodie under 1500');
  await page.keyboard.press('Enter');
  
  await expect(page.getByText(/Do you want to proceed to secure the split settlement via Razorpay Route\?/i)).toBeVisible({ timeout: 30000 });
  
  const checkoutBtn = page.getByRole('button', { name: /Pay & Secure Inventory/i });
  await expect(checkoutBtn).toBeVisible({ timeout: 10000 });
  
  await checkoutBtn.click();
  
  await expect(page.getByText(/Payment successful and settlement executed via Razorpay Route! Order/i)).toBeVisible({ timeout: 15000 });
});
