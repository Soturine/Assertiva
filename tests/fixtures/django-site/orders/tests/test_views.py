import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from orders import views
from orders.models import Order


class RoutingTests(SimpleTestCase):
    def test_detail_route_resolves_to_the_view(self):
        self.assertIs(resolve("/orders/X9/").func, views.order_detail)


class OrderApiTests(TestCase):
    def test_anonymous_detail_redirects_to_login(self):
        response = self.client.get(reverse("order-detail", args=["A1"]))
        self.assertEqual(response.status_code, 302)

    def test_detail_returns_the_order_for_a_logged_in_user(self):
        User.objects.create_user("ana", password="pw-ana-123")
        Order.objects.create(code="A1", total=Decimal("12.50"))
        self.client.login(username="ana", password="pw-ana-123")
        response = self.client.get(reverse("order-detail", args=["A1"]))
        self.assertEqual(response.json(), {"code": "A1", "total": "12.50", "paid": False})

    def test_a_non_positive_total_is_rejected_with_the_field(self):
        response = self.client.post(reverse("order-create"), json.dumps({"code": "B1", "total": 0}), content_type="application/json")
        self.assertEqual((response.status_code, response.json()["field"]), (400, "total"))
        self.assertFalse(Order.objects.filter(code="B1").exists())

    async def test_health_answers_asynchronously(self):
        response = await self.async_client.get("/health/")
        self.assertEqual(response.json(), {"status": "ok"})
