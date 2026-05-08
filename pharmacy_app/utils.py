"""Cryptographic utilities for prescription integrity.

Signature HMAC-SHA256 melindungi prescription dari tampering, termasuk
upaya mengubah *dosage*, *instruction*, atau *itemId* secara diam-diam
setelah dokter menandatangani. Semua field yang klinikal-signifikan
dimasukkan ke payload signature, diurutkan deterministik supaya signature
identik di sisi signer dan verifier.
"""

import hashlib
import hmac
import json

from django.conf import settings


def _signing_key() -> bytes:
    """Kunci untuk HMAC. Diambil dari PRESCRIPTION_SIGNING_KEY bila di-set,
    kalau tidak fallback ke SECRET_KEY. Fallback ini hanya boleh terjadi
    pada dev/local — di production env var harus selalu di-set (lihat
    .env.example) agar rotasi SECRET_KEY tidak otomatis menginvalidasi
    signature rekam medis yang sudah ada.
    """

    key = getattr(settings, "PRESCRIPTION_SIGNING_KEY", None) or settings.SECRET_KEY
    return key.encode("utf-8")


def _build_payload(prescription) -> bytes:
    items_data = list(
        prescription.items.order_by("id").values(
            "itemId",
            "medicineName",
            "dosage",
            "quantity",
            "instruction",
        )
    )

    payload = {
        "prescription_id": str(prescription.pk),
        "encounter_id": str(prescription.encounter_id),
        "prescriber_id": str(prescription.encounter.staff_id),
        "items": items_data,
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_prescription_signature(prescription) -> str:
    return hmac.new(_signing_key(), _build_payload(prescription), hashlib.sha256).hexdigest()


def sign_prescription(prescription) -> None:
    prescription.digitalSignature = compute_prescription_signature(prescription)
    prescription.save(update_fields=["digitalSignature"])
