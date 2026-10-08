from django.urls import path

from orders import views

urlpatterns = [
    path("orders/", views.create_order, name="order-create"),
    path("orders/<str:code>/", views.order_detail, name="order-detail"),
    path("health/", views.health, name="health"),
]
