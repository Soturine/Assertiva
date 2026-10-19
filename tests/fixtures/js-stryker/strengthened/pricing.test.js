const { discountCents } = require('./pricing');

test('member gets a discount', () => {
  expect(discountCents(15000, true)).toBe(1500);
});

test('non-member pays full price', () => {
  expect(discountCents(15000, false)).toBe(0);
});

test('the threshold is inclusive', () => {
  expect(discountCents(10000, true)).toBe(1000);
  expect(discountCents(9999, true)).toBe(0);
});

test('the discount rounds down to whole cents', () => {
  expect(discountCents(10005, true)).toBe(1000);
});
