from decimal import Decimal

from django.db import models, transaction


class Order(models.Model):
    code = models.CharField(max_length=20, unique=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)

    def pay(self):
        if self.total <= Decimal("0"):
            raise ValueError("an order without a positive total cannot be paid")
        self.paid = True
        self.save(update_fields=["paid"])


def create_paid_pair(code_a, code_b, total):
    """Both orders or neither: a failure inside the block rolls back the first one."""
    with transaction.atomic():
        Order.objects.create(code=code_a, total=total)
        Order.objects.create(code=code_b, total=total)
