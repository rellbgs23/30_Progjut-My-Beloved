"""Root URL configuration.

- `/`              -> core_app.home (role-aware router)
- `/admin/`        -> Django admin
- `/auth/`         -> login, logout, profile, denied
- `/patient/`      -> portal pasien
- `/medical/`      -> portal dokter & registration
- `/pharmacy/`     -> portal apoteker
- `/billing/`      -> portal kasir

Error handlers:
- 404 / 403 / 500  -> template bermerek MediCore (lihat templates/errors/)
"""

from django.contrib import admin
from django.urls import include, path

from core_app import views as core_views

urlpatterns = [
    path("", core_views.home, name="root"),
    path("admin/", admin.site.urls),
    path("auth/", include("auth_app.urls")),
    path("patient/", include("core_app.urls")),
    path("medical/", include("medical_app.urls")),
    path("pharmacy/", include("pharmacy_app.urls")),
    path("billing/", include("billing_app.urls")),
]


# Django memanggil handler ini saat DEBUG=False. Di DEBUG=True Django
# menampilkan halaman teknis sendiri, jadi handler di-register hanya
# untuk efek produksi.
handler404 = "core_app.views.page_not_found"
handler403 = "core_app.views.permission_denied"
handler500 = "core_app.views.server_error"
