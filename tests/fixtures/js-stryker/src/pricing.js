// Member discount: 10% of orders of 100.00 or more, in whole cents (rounded down).
function discountCents(totalCents, member) {
  if (member && totalCents >= 10000) {
    return Math.floor(totalCents / 10);
  }
  return 0;
}

module.exports = { discountCents };
