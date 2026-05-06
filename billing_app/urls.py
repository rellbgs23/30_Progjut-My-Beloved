from django.urls import path
from . import views

app_name = 'billing_app'

urlpatterns = [
    path('pay/', views.process_payment, name='process_payment'),
]
