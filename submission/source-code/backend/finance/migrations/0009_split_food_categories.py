from django.db import migrations


DELIVERY_KEYWORDS = (
    "배달",
    "배달앱",
    "배달의민족",
    "요기요",
    "쿠팡이츠",
    "땡겨요",
)


def split_food_categories(apps, schema_editor):
    BenefitRule = apps.get_model("finance", "BenefitRule")
    for benefit in BenefitRule.objects.filter(category="food").iterator():
        text = f"{benefit.raw_text} {benefit.condition_text}"
        benefit.category = (
            "delivery"
            if any(keyword in text for keyword in DELIVERY_KEYWORDS)
            else "dining"
        )
        benefit.save(update_fields=["category"])


def restore_food_category(apps, schema_editor):
    BenefitRule = apps.get_model("finance", "BenefitRule")
    BenefitRule.objects.filter(category__in=["dining", "delivery"]).update(
        category="food"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0008_benefitrule_end_hour_benefitrule_start_hour"),
    ]

    operations = [
        migrations.RunPython(split_food_categories, restore_food_category),
    ]
