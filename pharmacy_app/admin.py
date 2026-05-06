from django.contrib import admin
from .models import Prescription, PrescriptionItem


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
	list_display = ('id', 'encounter', 'status', 'validatedAt', 'dispensedAt')
	list_filter = ('status',)
	search_fields = ('id',)


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
	list_display = ('id', 'prescription', 'medicineName', 'quantity')
	search_fields = ('medicineName', 'itemId')
