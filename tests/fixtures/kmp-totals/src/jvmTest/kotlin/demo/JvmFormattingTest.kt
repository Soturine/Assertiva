package demo

import kotlin.test.Test
import kotlin.test.assertEquals

class JvmFormattingTest {
    @Test
    fun formatsWithTheJvmFormatter() = assertEquals("30", String.format("%d", total(listOf(10, 20))))
}
