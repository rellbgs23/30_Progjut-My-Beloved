from django.urls import path
from . import views

app_name = "medical_app"

urlpatterns = [
    path("appointments/new/", views.create_appointment, name="appointment_create"),
    path("appointments/<uuid:appointment_id>/", views.appointment_detail, name="appointment_detail"),

    path("encounters/<uuid:encounter_id>/records/new/", views.create_medical_record, name="medical_record_create"),
    path("records/<uuid:record_id>/", views.medical_record_detail, name="medical_record_detail"),
]