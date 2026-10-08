package demo.legacy;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Ignore;
import org.junit.Test;

public class StockTest {
    @Test
    public void reservingReducesUnits() {
        assertEquals(2, new Stock(5).reserve(3));
    }

    @Test
    public void shortfallKeepsStockUnchanged() {
        Stock stock = new Stock(1);
        assertThrows(IllegalStateException.class, () -> stock.reserve(2));
        assertEquals(1, stock.units());
    }

    @Ignore("waiting for the batch reservation rule")
    @Test
    public void batchReservation() {
    }
}
