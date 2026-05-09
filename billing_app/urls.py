from django.urls import path

from . import views

app_name = "billing_app"

urlpatterns = [
    path("cashier/", views.cashier_dashboard, name="cashier_dashboard"),
    path("pay/", views.process_payment, name="process_payment"),
]
