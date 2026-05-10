import hashlib
import hmac
import json
from django.conf import settings


def compute_prescription_signature(prescription) -> str:
    items_data = list(
        prescription.items.order_by('id').values('medicineName_id', 'quantity')
    )

    payload = json.dumps(
        {
            'prescription_id': str(prescription.pk),
            'prescriber_id': str(prescription.encounter.staff_id),
            'items': items_data,
        },
        sort_keys=True,
        separators=(',', ':'),
    )

    secret = settings.SECRET_KEY.encode('utf-8')
    return hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()


def sign_prescription(prescription) -> None:
    prescription.digitalSignature = compute_prescription_signature(prescription)
    prescription.save(update_fields=['digitalSignature'])
