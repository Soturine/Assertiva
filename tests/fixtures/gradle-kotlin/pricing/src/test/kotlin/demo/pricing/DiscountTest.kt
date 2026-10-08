package demo.pricing

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.CsvSource

class DiscountTest {
    @Test
    fun vipGetsTenPercentOff() {
        assertEquals(90, discount(100, Tier.VIP))
    }

    @Test
    fun negativeTotalIsRejected() {
        val error = assertFailsWith<IllegalArgumentException> { discount(-1, Tier.REGULAR) }
        assertEquals("negative total", error.message)
    }

    @ParameterizedTest
    @CsvSource("0,0", "100,100", "250,250")
    fun regularPaysFullPrice(total: Int, expected: Int) {
        assertEquals(expected, discount(total, Tier.REGULAR))
    }
}
