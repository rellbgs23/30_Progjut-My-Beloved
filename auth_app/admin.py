from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserAccount, Staff


@admin.register(UserAccount)
class UserAccountAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Security Fields", {
            "fields": (
                "mfaEnabled",
                "failedLoginAttempts",
                "lockedUntil",
            )
        }),
    )

    list_display = (
        "username",
        "email",
        "is_active",
        "mfaEnabled",
        "failedLoginAttempts",
        "lockedUntil",
    )


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "role")
    search_fields = ("name", "user__username")
    list_filter = ("role",)