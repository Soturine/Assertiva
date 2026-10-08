package demo.pricing

enum class Tier { VIP, REGULAR }

fun discount(total: Int, tier: Tier): Int {
    require(total >= 0) { "negative total" }
    return if (tier == Tier.VIP) total * 90 / 100 else total
}
