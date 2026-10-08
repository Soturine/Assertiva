import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Order


def health(request):
    return JsonResponse({"status": "ok"})


@login_required
def order_detail(request, code):
    try:
        order = Order.objects.get(code=code)
    except Order.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse({"code": order.code, "total": str(order.total), "paid": order.paid})


@require_POST
def create_order(request):
    try:
        data = json.loads(request.body)
        total = Decimal(str(data["total"]))
    except (ValueError, KeyError, InvalidOperation):
        return JsonResponse({"error": "invalid", "field": "total"}, status=400)
    if total <= 0:
        return JsonResponse({"error": "invalid", "field": "total"}, status=400)
    order = Order.objects.create(code=data.get("code", ""), total=total)
    return JsonResponse({"code": order.code}, status=201)
