package dev.assertiva.fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class PriceIT {
    @Test
    void vipCheckoutEndToEnd() {
        int total = 0;
        for (int item : new int[] {60, 40}) {
            total += item;
        }
        assertEquals(90, Price.discount(total, "VIP"));
    }
}
