import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from finance.card_catalog import load_recommendation_candidates
from finance.recommendation import rank_card_recommendations


DEFAULT_INFRASTRUCTURE = {
    "cafe": {
        "count": 80,
        "sample_count": 45,
        "merchant_counts": {
            "스타벅스": 7,
            "메가커피": 5,
            "투썸플레이스": 4,
            "이디야": 3,
        },
    },
    "convenience": {
        "count": 35,
        "sample_count": 35,
        "merchant_counts": {
            "CU": 11,
            "GS25": 12,
            "세븐일레븐": 7,
            "이마트24": 5,
        },
    },
    "dining": {
        "count": 180,
        "sample_count": 45,
        "merchant_counts": {
            "맥도날드": 2,
            "버거킹": 1,
            "롯데리아": 1,
        },
    },
    "delivery": {
        "count": 0,
        "sample_count": 0,
        "merchant_counts": {},
    },
    "mart": {
        "count": 6,
        "sample_count": 6,
        "merchant_counts": {
            "이마트": 2,
            "롯데마트": 1,
            "홈플러스": 1,
        },
    },
}


class Command(BaseCommand):
    help = "VLM 더미 소비 프로필로 실제 카드 추천 결과를 비교합니다."

    def add_arguments(self, parser):
        parser.add_argument("--profile")
        parser.add_argument("--category")
        parser.add_argument("--limit", type=int, default=3)

    def handle(self, *args, **options):
        path = (
            Path(settings.BASE_DIR)
            / "finance"
            / "testdata"
            / "vlm_spending_profiles.json"
        )
        profiles = json.loads(path.read_text(encoding="utf-8"))
        if options["profile"]:
            profiles = [
                item
                for item in profiles
                if item["profile"] == options["profile"]
            ]
            if not profiles:
                raise CommandError("일치하는 VLM 더미 프로필이 없습니다.")

        cards = load_recommendation_candidates()["cards"]
        if not cards:
            raise CommandError("추천 가능한 active 카드가 없습니다.")

        limit = max(options["limit"], 1)
        for profile in profiles:
            spending = profile["spending"]
            previous_month_spending = sum(spending.values())
            ranking = rank_card_recommendations(
                cards=cards,
                spending=spending,
                infrastructure=DEFAULT_INFRASTRUCTURE,
                previous_month_spending=previous_month_spending,
                owned_card_ids=profile.get("owned_card_ids", []),
                spending_source="image_parser",
                selected_category=options["category"],
            )

            self.stdout.write(
                f"\n[{profile['profile']}] "
                f"user={profile['user']['nickname']} "
                f"total={previous_month_spending} "
                f"mode={'category' if options['category'] else 'overall'}"
            )
            for card_type in ("credit", "debit"):
                candidates = [
                    item
                    for item in ranking
                    if item["card_type"] == card_type
                    and (
                        not options["category"]
                        or options["category"] in item["category_scores"]
                    )
                ][:limit]
                result = [
                    self._result_item(item, options["category"])
                    for item in candidates
                ]
                self.stdout.write(
                    f"{card_type}={json.dumps(result, ensure_ascii=False)}"
                )

    @staticmethod
    def _result_item(item, selected_category):
        result = {
            "name": item["name"],
            "score": item["ranking_score"],
            "net_value": item["estimated_net_value"],
            "is_owned": item["is_owned"],
        }
        if selected_category:
            category_score = item["category_scores"][selected_category]
            result.update(
                {
                    "category_benefit_score": category_score[
                        "category_benefit_score"
                    ],
                    "merchant_accessibility": category_score[
                        "merchant_accessibility"
                    ],
                    "local_accessibility": category_score[
                        "local_accessibility"
                    ],
                }
            )
        else:
            result.update(
                {
                    "spending_benefit_fit": item["spending_benefit_fit"],
                    "local_brand_fit": item["local_brand_fit"],
                }
            )
        return result
