from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_app", "0002_useraccount_failedloginattempts_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="is_patient",
            field=models.BooleanField(default=False),
        ),
    ]
