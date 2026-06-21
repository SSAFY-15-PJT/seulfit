from django.core.management.base import BaseCommand

from finance.models import Category


DEFAULT_CATEGORIES = [
    {"key": "cafe", "label": "카페", "kakao_code": "CE7"},
    {"key": "convenience", "label": "편의점", "kakao_code": "CS2"},
    {"key": "mart", "label": "마트", "kakao_code": "MT1"},
    {"key": "dining", "label": "음식점", "kakao_code": "FD6"},
    {"key": "delivery", "label": "배달", "kakao_code": "FD6"},
    {"key": "shopping", "label": "쇼핑", "kakao_code": ""},
    {"key": "etc", "label": "기타", "kakao_code": ""},
]


class Command(BaseCommand):
    help = "기본 카테고리 마스터를 메인 DB에 적재합니다."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for item in DEFAULT_CATEGORIES:
            _, is_created = Category.objects.update_or_create(
                key=item["key"],
                defaults={
                    "label": item["label"],
                    "kakao_code": item["kakao_code"],
                    "is_active": True,
                },
            )
            created += int(is_created)
            updated += int(not is_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"categories seeded\tcreated={created}\tupdated={updated}"
            )
        )
