from django.urls import path

from . import views

app_name = "core_app"

urlpatterns = [
    path("register/", views.self_register, name="patient_register"),
    path("dashboard/", views.patient_dashboard, name="patient_dashboard"),
    path("appointments/new/", views.request_appointment, name="patient_request_appointment"),
    path("appointments/", views.patient_appointments, name="patient_appointments"),
    path("encounters/", views.patient_encounter_list, name="patient_encounters"),
    path("encounters/number/<int:encounter_number>/", views.patient_encounter_detail_by_number, name="patient_encounter_detail_by_number"),
    path("encounters/<int:encounter_id>/", views.patient_encounter_detail, name="patient_encounter_detail"),
    path("invoices/", views.patient_invoices, name="patient_invoices"),
]
