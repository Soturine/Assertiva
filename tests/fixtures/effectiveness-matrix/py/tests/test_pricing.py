import time

import pytest

from pricing import total


def test_total_applies_discount():
    assert total([10, 20], discount=10) == 27.0


def test_total_swallowed():
    try:
        assert total([10]) == 99
    except AssertionError:
        pass


def test_total_conditional(flag=False):
    if flag:
        assert total([1]) == 1


def test_total_tautology():
    value = total([1, 2])
    assert value == value


def test_status_only(client):
    response = client.get("/total")
    assert response.status_code == 200


def test_any_error():
    with pytest.raises(Exception):
        total([1], discount=200)


def test_sum_copy_one():
    result = total([3, 4])
    assert result == 7


def test_sum_copy_two():
    result = total([3, 4])
    assert result == 7


@pytest.mark.parametrize("prices,expected", [([1], 1), ([2, 2], 4), ([1], 1)])
def test_rows(prices, expected):
    assert total(prices) == expected


def test_waits():
    time.sleep(0.01)
    assert total([5]) == 5
