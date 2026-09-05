# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: e2e.spec.js >> critical demo flow: search, negotiation, checkout
- Location: tests/e2e.spec.js:3:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('textarea').first()
Expected: visible
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 15000ms
  - waiting for locator('textarea').first()

```

```yaml
- img
- img
- img
- banner:
  - img
  - text: MerchantMesh
  - navigation:
    - list:
      - listitem: Overview
      - listitem: Buyer Agent
      - listitem: Catalog Bot
      - listitem: Sales Bot
- main:
  - text: Razorpay AI Buildathon 2026
  - heading "The Agent-to-Agent Commerce Protocol." [level=1]
  - paragraph: India is home to 63 million informal micro-merchants. MerchantMesh connects their ephemeral, invisible WhatsApp catalogs to autonomous AI buyers via Razorpay rails.
  - button "Spawn Buyer Agent"
  - button "View Architecture"
  - heading "The Journey" [level=4]
  - heading "We started with one problem. It kept getting bigger." [level=2]
  - paragraph: Informal commerce didn't need a new storefront. It needed an entirely new layer of autonomous infrastructure to secure and verify intent.
  - text: 01 · Market
  - img
  - img
  - heading "Invisible Catalogs" [level=3]
  - paragraph: 63M merchants rely on fleeting status updates.
  - heading "No Shopify" [level=3]
  - paragraph: Micro-merchants don't use SEO or store builders. They drop blurry photos on WhatsApp. It's a massive localized supply with zero discoverability.
  - text: 02 · Friction
  - img
  - img
  - heading "Manual Exhaustion" [level=3]
  - paragraph: Buyers must DM dozens of sellers manually.
  - heading "Slow Haggling" [level=3]
  - paragraph: To find the best price, a buyer has to DM 10 different sellers, negotiate base prices, and wait hours for replies while inventory disappears.
  - text: 03 · Risk
  - img
  - img
  - heading "The Trust Gap" [level=3]
  - paragraph: Paying strangers via UPI with no guarantee.
  - heading "No Buyer Guard" [level=3]
  - paragraph: Even if they agree on a price, transferring money directly requires immense trust. Scams and ghosting kill conversions in informal markets.
  - text: 04 · Solution
  - img
  - img
  - heading "AI Matchmaking" [level=3]
  - paragraph: What if code did the haggling for you?
  - heading "Parallel Agents" [level=3]
  - paragraph: MerchantMesh spawns parallel AI agents to instantly negotiate with every local seller at once, relentlessly driving prices down to the true market floor.
  - text: 05 · Trust
  - img
  - img
  - heading "Escrow Autopilot" [level=3]
  - paragraph: Code-enforced trust via Razorpay Route.
  - heading "Split Settlement" [level=3]
  - paragraph: Once the AI locks in the lowest bid, Razorpay secures the funds in escrow, taking our 2% cut without human intervention.
  - heading "Architecture" [level=4]
  - heading "One network. Infinite connections." [level=2]
  - paragraph: Hover over the nodes to see exactly how the LangGraph orchestrator secures the AI transaction layer.
  - img
  - text: WhatsApp Seller
  - img
  - text: Buyer RFQ
  - img
  - text: Catalog Agent
  - img
  - text: Sales Agent
  - img
  - text: Buyer Agent
  - img
  - text: LangGraph Supervisor
  - img
  - text: SQLite Data
  - img
  - text: Python Guardrails
  - img
  - text: MCP Server
  - img
  - text: Razorpay Route
  - img
  - img
  - img
  - img
  - img
  - img
  - img
  - img
  - img
  - img
  - heading "Live Unit Economics" [level=2]
  - paragraph: Watch our multi-dealer Reverse Auction engine haggle and capture platform fees in real-time.
  - application
  - img
  - text: Live GMV & Bidding Agents haggling in real-time. ₹ 0
  - img
  - text: Platform Revenue 2.0% Razorpay Route capture.
  - application: 94%
  - img
  - text: Conversion Rates Successful vs Deadlocks.
  - code: "> Initiating Reverse Auction RFQ... > TechCorp Bot bid ₹1,150,000. Input: 320 tokens. Cost: ₹0.04 > GlobalIT Bot undercut ₹1,120,000. Input: 640 tokens. Cost: ₹0.08 > Acme Supplier bid ₹1,050,000. Input: 960 tokens. Cost: ₹0.12 > TechCorp Bot counter-bid ₹950,000. Input: 1280 tokens. Cost: ₹0.16 > DEAL CLOSED at ₹950,000. > Total Tokens: 4,500. Exact LLM Cost: ₹0.43"
  - img
  - text: Net Profit Margin (LLM Token Log) Verifiable operational costs in real-time.
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test('critical demo flow: search, negotiation, checkout', async ({ page }) => {
  4  |   await page.goto('http://localhost:5178');
  5  |   
  6  |   const searchInput = page.locator('textarea').first();
> 7  |   await expect(searchInput).toBeVisible({ timeout: 15000 });
     |                             ^ Error: expect(locator).toBeVisible() failed
  8  |   
  9  |   await searchInput.fill('black hoodie under 1500');
  10 |   await page.keyboard.press('Enter');
  11 |   
  12 |   await expect(page.getByText(/Do you want to proceed to secure the escrow via Razorpay Route\?/i)).toBeVisible({ timeout: 30000 });
  13 |   
  14 |   const checkoutBtn = page.getByRole('button', { name: /Pay & Secure Inventory/i });
  15 |   await expect(checkoutBtn).toBeVisible({ timeout: 10000 });
  16 |   
  17 |   await checkoutBtn.click();
  18 |   
  19 |   await expect(page.getByText(/Payment successful and settlement executed via Razorpay Route! Order/i)).toBeVisible({ timeout: 15000 });
  20 | });
  21 | 
```