package demo

fun total(prices: List<Int>, discountPercent: Int = 0): Int {
    require(discountPercent in 0..100) { "discount out of range" }
    return prices.sum() * (100 - discountPercent) / 100
}
