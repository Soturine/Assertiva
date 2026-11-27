# Order pricing (synthetic demo for Assertiva's adaptive tool discovery).
# Rule: orders of 10 items or more get 5% off; the total is rounded to cents, half up.
module Price
  BULK_THRESHOLD = 10
  BULK_DISCOUNT = 0.05

  def self.total(unit_cents, quantity)
    raise ArgumentError, "quantity must be positive" unless quantity.is_a?(Integer) && quantity.positive?

    gross = unit_cents * quantity
    gross -= (gross * BULK_DISCOUNT).round if quantity >= BULK_THRESHOLD
    gross
  end
end
