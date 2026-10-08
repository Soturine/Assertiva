package demo

import io.mockk.impl.annotations.MockK
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class GatewayIntegrationTest {
    @MockK
    lateinit var gateway: PriceGateway

    @Test
    fun publishesTotal() {
        assertEquals(5.0, total(listOf(2.0, 3.0)))
    }
}
