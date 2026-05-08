from django.contrib import admin

from .models import AuditLog, Invoice, Payment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "encounter", "totalAmount", "status", "createdAt")
    list_filter = ("status", "createdAt")
    search_fields = ("id",)
    readonly_fields = ("id", "createdAt")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "paidAmount",
        "method",
        "processedBy",
        "paidAt",
    )
    list_filter = ("method", "paidAt")
    search_fields = ("id", "invoice__id")
    readonly_fields = ("id", "paidAt")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "actor", "entityType", "timestamp", "hash")
    list_filter = ("action", "entityType", "timestamp")
    search_fields = ("id", "entityId", "hash")
    # AuditLog harus append-only — tidak boleh diedit dari admin.
    readonly_fields = (
        "id",
        "payment",
        "actor",
        "entityType",
        "entityId",
        "detail",
        "timestamp",
        "action",
        "hash",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
