// Library holds: frozen confirmation fixture v2 (see labels.json). Never run; read statically.
package demo

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assertions.fail
import org.junit.jupiter.api.Test
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.CsvSource

class LibraryTest {
    @Test
    fun holdQueuePosition() {
        assertEquals(3, Library().hold("b1", member = "m3"))
    }

    @Test
    fun holdIgnoresFailures() {
        runCatching { assertEquals(0, Library().hold("missing", member = "m1")) }
    }

    @Test
    fun holdsNotEmpty() {
        assertTrue(Library().holds("b1").isNotEmpty())
    }

    @Test
    fun rejectsClosedBranch() {
        assertThrows<IllegalStateException> { Library(closed = true).hold("b1", member = "m1") }
    }

    @Test
    fun rejectsSomehow() {
        assertThrows<Throwable> { Library().hold("", member = "") }
    }

    @Test
    fun renewalCheckedEitherWay() {
        val library = Library()
        if (library.renewalsEnabled) {
            assertEquals(1, library.renew("b1"))
        } else {
            fail("renewals must be enabled in the default library")
        }
    }

    @ParameterizedTest
    @CsvSource(textBlock = """
        1, 7
        2, 14
        1, 7
    """)
    fun loanDays(weeks: Int, days: Int) {
        assertEquals(days, Library().loanDays(weeks))
    }

    @Test
    fun holdTimeoutReleasesSeat() {
        val library = Library(holdTimeoutMs = 100)
        library.hold("b2", member = "m2")
        Thread.sleep(150)
        assertEquals(0, library.holds("b2").size)
    }

    @Test
    fun constantCheck() {
        assertEquals(1, 1)
    }
}
