from django.contrib import admin
from .models import Medicine, Prescription, PrescriptionItem


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
	list_display = ('name',)
	search_fields = ('name',)


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
	list_display = ('id', 'encounter', 'status', 'validatedAt', 'dispensedAt')
	list_filter = ('status',)
	search_fields = ('id',)


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
	list_display = ('id', 'prescription', 'medicineName', 'quantity')
	search_fields = ('medicineName__name', 'itemId')
