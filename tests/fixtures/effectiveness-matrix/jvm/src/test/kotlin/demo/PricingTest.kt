package demo

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.CsvSource

class PricingTest {
    @Test
    fun appliesDiscount() {
        assertEquals(27.0, total(listOf(10.0, 20.0), 10))
    }

    @Test
    fun swallowed() {
        try {
            assertEquals(99.0, total(listOf(10.0)))
        } catch (e: AssertionError) {
        }
    }

    @Test
    fun conditional() {
        val flag = false
        if (flag) {
            assertEquals(1.0, total(listOf(1.0)))
        }
    }

    @Test
    fun tautology() {
        assertTrue(true)
    }

    @Test
    fun anyError() {
        assertThrows<Exception> { total(listOf(1.0), 200) }
    }

    @Test
    fun sumCopyOne() {
        val result = total(listOf(3.0, 4.0))
        assertEquals(7.0, result)
    }

    @Test
    fun sumCopyTwo() {
        val result = total(listOf(3.0, 4.0))
        assertEquals(7.0, result)
    }

    @ParameterizedTest
    @CsvSource("1, 1", "4, 4", "1, 1")
    fun rows(price: Double, expected: Double) {
        assertEquals(expected, total(listOf(price)))
    }

    @Test
    fun waits() {
        Thread.sleep(10)
        assertEquals(5.0, total(listOf(5.0)))
    }
}

class PricingEndpointTest {
    @Test
    fun statusOnly() {
        val response = PricingEndpoint().get("/total")
        assertEquals(200, response.status)
    }
}
