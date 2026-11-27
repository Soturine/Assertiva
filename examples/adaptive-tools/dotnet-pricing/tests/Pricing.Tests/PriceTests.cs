using Pricing;
using System;
using Xunit;

public class PriceTests
{
    [Fact]
    public void SmallOrderHasNoDiscount() => Assert.Equal(900, Price.Total(100, 9));

    [Fact]
    public void BulkOrderIsDiscounted() => Assert.True(Price.Total(100, 20) < 2000);

    [Fact]
    public void RejectsZeroQuantity() => Assert.Throws<ArgumentOutOfRangeException>(() => Price.Total(100, 0));
}
