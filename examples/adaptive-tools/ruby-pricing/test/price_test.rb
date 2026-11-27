require "minitest/autorun"
require_relative "../lib/price"

class PriceTest < Minitest::Test
  def test_small_order_has_no_discount
    assert_equal 900, Price.total(100, 9)
  end

  def test_bulk_order_is_discounted
    assert Price.total(100, 20) < 2000
  end

  def test_rejects_zero_quantity
    assert_raises(ArgumentError) { Price.total(100, 0) }
  end
end
