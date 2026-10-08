from django.db import models, transaction


class Item(models.Model):
    sku = models.CharField(max_length=20, unique=True)
    quantity = models.PositiveIntegerField(default=0)
    attributes = models.JSONField(default=dict)


def reserve(sku, amount):
    """Take `amount` units, all or nothing: a shortfall leaves the stock unchanged."""
    with transaction.atomic():
        item = Item.objects.select_for_update().get(sku=sku)
        if amount > item.quantity:
            raise ValueError("insufficient stock")
        item.quantity -= amount
        item.save(update_fields=["quantity"])
    return item.quantity
