export function total(prices, discount = 0) {
  if (discount < 0 || discount > 100) throw new RangeError('discount out of range')
  return Math.round(prices.reduce((a, b) => a + b, 0) * (100 - discount)) / 100
}
