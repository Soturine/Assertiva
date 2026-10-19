package dev.assertiva.pit;

public final class Pricing {
    private Pricing() {
    }

    /** Member discount: 10% of orders of 100.00 or more, in whole cents (rounded down). */
    public static int discountCents(int totalCents, boolean member) {
        if (member && totalCents >= 10000) {
            return totalCents / 10;
        }
        return 0;
    }
}
