const { discount } = require("../src/price");

describe("discount", () => {
  test.each([
    [100, "VIP", 90],
    [150, "REGULAR", 150],
  ])("discount(%i, %s) is %i", (total, tier, expected) => {
    expect(discount(total, tier)).toBe(expected);
  });

  test("rejects a negative total", () => {
    expect(() => discount(-1, "VIP")).toThrow("negative total");
  });

  test.skip("waits for a currency rule", () => {
    expect(discount(1, "EUR")).toBe(1);
  });

  test.todo("handles rounding of fractional cents");
});
