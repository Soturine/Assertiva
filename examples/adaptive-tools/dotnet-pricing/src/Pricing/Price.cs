using System;

namespace Pricing;

// Order pricing (synthetic demo for Assertiva's adaptive tool discovery).
// Rule: orders of 10 items or more get 5% off; the discount is rounded to cents, half away from zero.
public static class Price
{
    public const int BulkThreshold = 10;

    public static long Total(long unitCents, int quantity)
    {
        if (quantity <= 0) throw new ArgumentOutOfRangeException(nameof(quantity), "quantity must be positive");
        long gross = unitCents * quantity;
        if (quantity >= BulkThreshold) gross -= (long)Math.Round(gross * 0.05m, MidpointRounding.AwayFromZero);
        return gross;
    }
}
