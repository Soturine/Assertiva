package dev.assertiva.fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class PriceTest {
    @ParameterizedTest
    @CsvSource({"100, VIP, 90", "99, VIP, 99", "100, REGULAR, 100"})
    void appliesTierDiscount(int total, String tier, int expected) {
        assertEquals(expected, Price.discount(total, tier));
    }

    @Test
    void rejectsNegativeTotals() {
        assertThrows(IllegalArgumentException.class, () -> Price.discount(-1, "VIP"));
    }

    @Test
    @Disabled("pricing rules for coupons are not decided yet")
    void appliesCoupons() {
    }
}
