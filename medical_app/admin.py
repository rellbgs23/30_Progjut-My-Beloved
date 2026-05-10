from django.contrib import admin
from .models import Patient, Appointment, Encounter, MedicalRecordEntry


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("mrn", "name", "dateOfBirth")
    search_fields = ("mrn", "name")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "scheduledAt", "status", "have_encounter")
    list_filter = ("status", "have_encounter", "scheduledAt")


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ("encounterNumber", "patient", "staff", "appointment", "dateTime")
    list_filter = ("dateTime",)


@admin.register(MedicalRecordEntry)
class MedicalRecordEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "encounter", "createdAt")
    readonly_fields = (
        "diagnosis_encrypted",
        "treatmentPlan_encrypted",
        "notes_encrypted",
        "createdAt",
    )
