package demo

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class TotalsTest {
    @Test
    fun sumsWithoutDiscount() = assertEquals(30, total(listOf(10, 20)))

    @Test
    fun appliesTheDiscount() = assertEquals(27, total(listOf(10, 20), discountPercent = 10))

    @Test
    fun rejectsAnOutOfRangeDiscount() {
        assertFailsWith<IllegalArgumentException> { total(listOf(1), discountPercent = 101) }
    }
}
