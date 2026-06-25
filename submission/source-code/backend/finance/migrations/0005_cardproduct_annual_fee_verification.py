from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0004_benefitrule_benefit_group_cardservicelimittier"),
    ]

    operations = [
        migrations.AddField(
            model_name="cardproduct",
            name="annual_fee_source_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="cardproduct",
            name="annual_fee_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
