from django.urls import path
from . import views

app_name = 'billing_app'

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('<uuid:invoice_id>/pay/', views.invoice_pay, name='invoice_pay'),
]
