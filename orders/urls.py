from django.urls import path, re_path

from . import views

# ids are capped at nine digits (no ORM overflow is reachable), like the public pages' routes
urlpatterns = [
    path("shop/<slug:slug>/get/", views.get_grant, name="get_grant"),
    re_path(r"^dashboard/orders/(?P<pk>\d{1,9})/cancel/$", views.cancel_order, name="order_cancel"),
    re_path(r"^dashboard/orders/(?P<pk>\d{1,9})/cart/$", views.cart, name="order_cart"),
]
