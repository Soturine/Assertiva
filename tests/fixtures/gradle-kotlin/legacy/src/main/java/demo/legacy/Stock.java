package demo.legacy;

public final class Stock {
    private int units;

    public Stock(int units) { this.units = units; }

    public int reserve(int amount) {
        if (amount > units) {
            throw new IllegalStateException("insufficient stock");
        }
        units -= amount;
        return units;
    }

    public int units() { return units; }
}
