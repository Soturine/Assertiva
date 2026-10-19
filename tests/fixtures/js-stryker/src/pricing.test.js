const { discountCents } = require('./pricing');

test('member gets a discount', () => {
  expect(discountCents(15000, true)).toBeDefined();
});

test('non-member pays full price', () => {
  expect(discountCents(15000, false)).toBe(0);
});
