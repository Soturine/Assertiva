from unittest import mock

from pricing import total


@mock.patch("pricing.requests.post")
def test_publishes_total(post):
    post.return_value.status_code = 201
    assert total([2, 3]) == 5
