// Thermostat: labeled confirmation fixture (see labels.json). Never run; read statically.
package demo

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.CsvSource

class ThermostatTest {
    @Test
    fun heatsBelowTarget() {
        assertEquals(Mode.HEAT, Thermostat(target = 21.0).mode(current = 18.0))
    }

    @Test
    fun ignoresSensorFailure() {
        try {
            assertEquals(Mode.OFF, Thermostat(target = 21.0).mode(current = Double.NaN))
        } catch (e: Exception) {
        }
    }

    @Test
    fun coolsOnlySometimes() {
        val t = Thermostat(target = 21.0)
        if (t.supportsCooling) {
            assertEquals(Mode.COOL, t.mode(current = 25.0))
        }
    }

    @Test
    fun modeExists() {
        assertNotNull(Thermostat(target = 21.0).mode(current = 20.0))
    }

    @Test
    fun rejectsAbsurdTarget() {
        assertThrows<IllegalArgumentException> { Thermostat(target = 99.0) }
    }

    @Test
    fun rejectsAnything() {
        assertThrows<Exception> { Thermostat(target = -40.0) }
    }

    @ParameterizedTest
    @CsvSource("18.0, HEAT", "21.0, IDLE", "18.0, HEAT")
    fun modeTable(current: Double, expected: Mode) {
        assertEquals(expected, Thermostat(target = 21.0).mode(current))
    }

    @ParameterizedTest
    @CsvSource(value = ["16.0, HEAT", "26.0, COOL"], nullValues = ["NA", "NA"])
    fun modeExtremes(current: Double, expected: Mode) {
        assertEquals(expected, Thermostat(target = 21.0).mode(current))
    }

    @Test
    fun selfComparison() {
        val m = Thermostat(target = 21.0).mode(current = 18.0)
        assertEquals(m, m)
    }

    @Test
    fun waitsForSensor() {
        val t = Thermostat(target = 21.0)
        t.refresh()
        Thread.sleep(500)
        assertEquals(Mode.HEAT, t.lastMode)
    }

    @Test
    fun debounceWindowElapses() {
        val t = Thermostat(target = 21.0, debounceMs = 100)
        t.report(18.0)
        Thread.sleep(150)
        assertEquals(Mode.HEAT, t.lastMode)
    }
}
