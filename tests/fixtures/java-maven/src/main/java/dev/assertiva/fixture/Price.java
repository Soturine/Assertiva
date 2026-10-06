package dev.assertiva.fixture;

public final class Price {
    private Price() {
    }

    /** Total after the tier discount; VIP orders of 100 or more get 10% off. */
    public static int discount(int total, String tier) {
        if (total < 0) {
            throw new IllegalArgumentException("total must not be negative");
        }
        if ("VIP".equals(tier) && total >= 100) {
            return total * 90 / 100;
        }
        return total;
    }
}
