package demo

import kotlin.test.Test
import kotlin.test.assertEquals

class JsTotalsTest {
    @Test
    fun emptyIsZero() = assertEquals(0, total(emptyList()))
}
