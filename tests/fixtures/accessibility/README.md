# Accessibility fixtures

`axe-checkout.json` and `axe-receipt.json` are unedited axe-core 4.10.3 results from headless Chromium (Playwright's
headless shell), produced on 2026-10-20 by `run-axe.js` on `page.html` and `clean.html`:

```
node run-axe.js <path to node_modules/playwright> [page.html|clean.html] [url recorded in the result]
```

(axe-core 4.10.3 installed beside the script). The checkout page has four violations and one color-contrast item axe
could not decide (text over a gradient); the receipt page has none, which is not proof that it is accessible.
