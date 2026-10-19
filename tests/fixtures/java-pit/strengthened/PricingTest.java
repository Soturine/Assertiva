package dev.assertiva.pit;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class PricingTest {
    @Test
    void memberGetsADiscount() {
        assertEquals(1500, Pricing.discountCents(15000, true));
    }

    @Test
    void nonMemberPaysFullPrice() {
        assertEquals(0, Pricing.discountCents(15000, false));
    }

    @Test
    void theThresholdIsInclusive() {
        assertEquals(1000, Pricing.discountCents(10000, true));
        assertEquals(0, Pricing.discountCents(9999, true));
    }
}
