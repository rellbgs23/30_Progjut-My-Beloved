import uuid
from django.db import models
from auth_app.models import Staff

class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mrn = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255) # Akan dienkripsi? (Sesuai UML: sensitive)
    dateOfBirth = models.DateField()

class Encounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.RESTRICT) # OCL: staff.role='DOCTOR'
    dateTime = models.DateTimeField(auto_now_add=True)
    complaint = models.TextField()

class MedicalRecordEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE)
    diagnosis_encrypted = models.TextField() # <<crypto>>
    treatmentPlan_encrypted = models.TextField() # <<crypto>>
    createdAt = models.DateTimeField(auto_now_add=True)

    def encrypt_data(self, raw_diagnosis, raw_treatment):
        # TODO: Implement cryptography fernet here
        pass
    
    def decrypt_data(self):
        # TODO: Implement decrypt here
        pass