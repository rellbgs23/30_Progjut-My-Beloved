from django.urls import path
from . import views

app_name = 'pharmacy_app'

urlpatterns = [
    path('prescriptions/', views.prescription_list, name='prescription_list'),
    path('dispense-queue/', views.dispense_queue, name='dispense_queue'),
    path('prescriptions/create/<int:encounter_id>/', views.create_prescription, name='create_prescription'),
    path('prescriptions/<uuid:prescription_id>/', views.prescription_detail, name='prescription_detail'),
    path('validate/<uuid:prescription_id>/', views.validate_prescription, name='validate_prescription'),
    path('dispense/<uuid:prescription_id>/', views.dispense_medicine, name='dispense_medicine'),
]
