package demo

import kotlin.test.Test
import kotlin.test.assertEquals

class IosTotalsTest {
    @Test
    fun singlePrice() = assertEquals(7, total(listOf(7)))
}
