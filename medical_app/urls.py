from django.urls import path

from . import views

app_name = "medical_app"

urlpatterns = [
    # Doctor
    path("doctor/", views.doctor_dashboard, name="doctor_dashboard"),
    path(
        "doctor/appointments/",
        views.doctor_appointments,
        name="doctor_appointments",
    ),
    path(
        "doctor/encounters/",
        views.doctor_encounters,
        name="doctor_encounters",
    ),
    path(
        "doctor/encounters/<uuid:encounter_id>/",
        views.doctor_encounter_detail,
        name="doctor_encounter_detail",
    ),
    path(
        "doctor/appointments/<uuid:appointment_id>/start-encounter/",
        views.create_encounter,
        name="encounter_create",
    ),

    # Registration
    path(
        "registration/",
        views.registration_dashboard,
        name="registration_dashboard",
    ),
    path(
        "registration/appointments/",
        views.registration_appointments,
        name="registration_appointments",
    ),
    path("appointments/new/", views.create_appointment, name="appointment_create"),
    path(
        "appointments/<uuid:appointment_id>/",
        views.appointment_detail,
        name="appointment_detail",
    ),

    # Medical record
    path(
        "encounters/<uuid:encounter_id>/records/new/",
        views.create_medical_record,
        name="medical_record_create",
    ),
    path(
        "records/<uuid:record_id>/",
        views.medical_record_detail,
        name="medical_record_detail",
    ),
]
