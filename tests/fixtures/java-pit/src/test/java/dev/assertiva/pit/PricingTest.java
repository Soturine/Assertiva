package dev.assertiva.pit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class PricingTest {
    @Test
    void memberGetsADiscount() {
        assertTrue(Pricing.discountCents(15000, true) >= 0);
    }

    @Test
    void nonMemberPaysFullPrice() {
        assertEquals(0, Pricing.discountCents(15000, false));
    }
}
