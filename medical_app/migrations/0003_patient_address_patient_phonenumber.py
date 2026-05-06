from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("medical_app", "0002_medicalrecordentry_notes_encrypted_patient_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="patient",
            name="address",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="patient",
            name="phoneNumber",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
