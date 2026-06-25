from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from finance.graph_repository import GraphRepository
from finance.graph_sync import build_card_graph_key
from finance.models import CardProduct, ParseStatus
from users.models import (
    UserCardEvent,
    UserConsumptionProfile,
    UserOwnedCard,
    UserProfile,
    UserUploadedReport,
)


DEMO_AREAS = {
    "demo_gangnam_station": {
        "name": "강남역/역삼",
        "store_counts": {
            "cafe": 18,
            "dining": 24,
            "convenience": 7,
            "mart": 4,
        },
    },
    "demo_jamsil_songpa": {
        "name": "잠실/송파",
        "store_counts": {
            "mart": 14,
            "dining": 16,
            "cafe": 9,
            "convenience": 7,
        },
    },
    "demo_hongdae_hapjeong": {
        "name": "홍대/합정",
        "store_counts": {
            "cafe": 22,
            "dining": 20,
            "convenience": 12,
            "mart": 3,
        },
    },
}


DEMO_USERS = [
    {
        "username": "demo_gangnam_cafe_user",
        "email": "demo_gangnam_cafe_user@example.com",
        "nickname": "강남 카페형",
        "preferred_area_id": "demo_gangnam_station",
        "preferred_area": "강남역/역삼",
        "monthly_expected_spend": 760000,
        "spending": {
            "cafe": 180000,
            "convenience": 70000,
            "dining": 260000,
            "delivery": 90000,
            "mart": 50000,
            "shopping": 80000,
            "etc": 30000,
        },
        "preferred_categories": ["cafe", "dining"],
    },
    {
        "username": "demo_jamsil_family_user",
        "email": "demo_jamsil_family_user@example.com",
        "nickname": "잠실 생활형",
        "preferred_area_id": "demo_jamsil_songpa",
        "preferred_area": "잠실/송파",
        "monthly_expected_spend": 920000,
        "spending": {
            "cafe": 70000,
            "convenience": 60000,
            "dining": 220000,
            "delivery": 80000,
            "mart": 260000,
            "shopping": 150000,
            "etc": 80000,
        },
        "preferred_categories": ["mart", "dining"],
    },
    {
        "username": "demo_hongdae_light_user",
        "email": "demo_hongdae_light_user@example.com",
        "nickname": "홍대 소액형",
        "preferred_area_id": "demo_hongdae_hapjeong",
        "preferred_area": "홍대/합정",
        "monthly_expected_spend": 540000,
        "spending": {
            "cafe": 130000,
            "convenience": 110000,
            "dining": 160000,
            "delivery": 50000,
            "mart": 30000,
            "shopping": 40000,
            "etc": 20000,
        },
        "preferred_categories": ["cafe", "convenience", "dining"],
    },
    {
        "username": "demo_balanced_user",
        "email": "demo_balanced_user@example.com",
        "nickname": "균형 소비형",
        "preferred_area_id": "demo_gangnam_station",
        "preferred_area": "강남역/역삼",
        "monthly_expected_spend": 830000,
        "spending": {
            "cafe": 100000,
            "convenience": 80000,
            "dining": 180000,
            "delivery": 100000,
            "mart": 160000,
            "shopping": 150000,
            "etc": 60000,
        },
        "preferred_categories": ["dining", "mart", "cafe"],
    },
]


EVENT_WEIGHTS = {
    "viewed": 5,
    "clicked": 3,
    "liked": 2,
    "applied_for": 1,
}


class Command(BaseCommand):
    help = "Seed deterministic demo users, VLM profiles, card events, and optional Neo4j graph data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-neo4j",
            action="store_true",
            help="Only seed SQLite data and skip Neo4j sync.",
        )
        parser.add_argument(
            "--sync-cards",
            action="store_true",
            help="Sync active cards and benefits to Neo4j before demo graph sync.",
        )
        parser.add_argument(
            "--password",
            default="demo1234!",
            help="Password for demo users.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        selected_cards = self._select_cards()
        if not selected_cards:
            self.stdout.write(
                self.style.ERROR(
                    "No active cards with active benefits were found. Seed card data first."
                )
            )
            return

        users = self._seed_sqlite(options["password"], selected_cards)

        graph_summary = {
            "skipped": bool(options["skip_neo4j"]),
            "card_sync": None,
            "area_sync_count": 0,
            "user_sync_count": 0,
            "event_sync_count": 0,
            "errors": [],
        }
        if not options["skip_neo4j"]:
            graph_summary = self._sync_graph(
                users=users,
                selected_cards=selected_cards,
                sync_cards=options["sync_cards"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                "demo seed completed "
                f"users={len(users)} "
                f"cards={len(selected_cards)} "
                f"neo4j_skipped={graph_summary['skipped']} "
                f"event_sync_count={graph_summary['event_sync_count']}"
            )
        )
        if graph_summary["errors"]:
            for error in graph_summary["errors"]:
                self.stdout.write(self.style.WARNING(error))

    def _select_cards(self):
        cards_by_category = {}
        base_queryset = (
            CardProduct.objects.filter(
                parse_status=ParseStatus.ACTIVE,
                annual_fee__isnull=False,
                benefits__parse_status=ParseStatus.ACTIVE,
            )
            .distinct()
            .order_by("pk")
        )
        for category in ["cafe", "dining", "mart", "convenience"]:
            cards_by_category[category] = list(
                base_queryset.filter(benefits__category=category)[:4]
            )

        selected = []
        seen = set()
        for area in DEMO_AREAS.values():
            for category in area["store_counts"]:
                for card in cards_by_category.get(category, [])[:2]:
                    if card.pk not in seen:
                        selected.append(card)
                        seen.add(card.pk)

        for card in base_queryset:
            if len(selected) >= 12:
                break
            if card.pk not in seen:
                selected.append(card)
                seen.add(card.pk)

        return selected

    def _cards_for_categories(self, selected_cards, categories, limit=4):
        result = []
        seen = set()
        for category in categories:
            for card in selected_cards:
                if card.pk in seen:
                    continue
                if card.benefits.filter(
                    parse_status=ParseStatus.ACTIVE,
                    category=category,
                ).exists():
                    result.append(card)
                    seen.add(card.pk)
                    if len(result) >= limit:
                        return result
        for card in selected_cards:
            if card.pk not in seen:
                result.append(card)
                seen.add(card.pk)
                if len(result) >= limit:
                    return result
        return result

    def _seed_sqlite(self, password, selected_cards):
        User = get_user_model()
        users = []
        for spec in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "first_name": spec["nickname"],
                },
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            else:
                changed = []
                if user.email != spec["email"]:
                    user.email = spec["email"]
                    changed.append("email")
                if user.first_name != spec["nickname"]:
                    user.first_name = spec["nickname"]
                    changed.append("first_name")
                if changed:
                    user.save(update_fields=changed)

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "nickname": spec["nickname"],
                    "preferred_area": spec["preferred_area"],
                    "monthly_expected_spend": spec["monthly_expected_spend"],
                },
            )
            UserConsumptionProfile.objects.update_or_create(
                user=user,
                defaults={
                    "source": "image_parser",
                    "spending_json": spec["spending"],
                    "is_cold_start": False,
                    "last_updated_at": timezone.now(),
                },
            )
            self._upsert_report(user, spec)

            user_cards = self._cards_for_categories(
                selected_cards,
                spec["preferred_categories"],
                limit=3,
            )
            for card in user_cards[:2]:
                UserOwnedCard.objects.get_or_create(user=user, card=card)
            self._seed_events(user, spec, user_cards)

            users.append(
                {
                    "user": user,
                    "spec": spec,
                    "cards": user_cards,
                }
            )
        return users

    def _upsert_report(self, user, spec):
        file_url = f"https://demo.seulpick.local/reports/{spec['username']}.jpg"
        parsed_payload = {
            "vlm_status": "success",
            "source": "demo_image_parser",
            "categories": spec["preferred_categories"],
            "spending": spec["spending"],
            "area_hint": spec["preferred_area"],
            "is_demo": True,
        }
        report = UserUploadedReport.objects.filter(
            user=user,
            file_url=file_url,
        ).first()
        if report:
            report.file_type = "image/jpeg"
            report.parse_status = ParseStatus.ACTIVE
            report.parsed_payload = parsed_payload
            report.save(
                update_fields=[
                    "file_type",
                    "parse_status",
                    "parsed_payload",
                    "updated_at",
                ]
            )
            return report
        return UserUploadedReport.objects.create(
            user=user,
            file_url=file_url,
            file_type="image/jpeg",
            parse_status=ParseStatus.ACTIVE,
            parsed_payload=parsed_payload,
        )

    def _seed_events(self, user, spec, cards):
        area_id = spec["preferred_area_id"]
        for rank, card in enumerate(cards, start=1):
            for event_type, base_count in EVENT_WEIGHTS.items():
                count = max(base_count - rank + 1, 1)
                if event_type == "applied_for" and rank > 2:
                    count = 0
                for index in range(count):
                    seed_key = (
                        f"demo:{spec['username']}:{area_id}:"
                        f"{card.pk}:{event_type}:{index}"
                    )
                    event = UserCardEvent.objects.filter(
                        user=user,
                        card=card,
                        area_id=area_id,
                        event_type=event_type,
                        metadata_json__seed_key=seed_key,
                    ).first()
                    if event:
                        continue
                    UserCardEvent.objects.create(
                        user=user,
                        card=card,
                        area_id=area_id,
                        event_type=event_type,
                        metadata_json={
                            "seed_key": seed_key,
                            "source": "demo_seed",
                            "rank_hint": rank,
                            "area_name": spec["preferred_area"],
                        },
                        is_demo=True,
                        graph_sync_status="pending",
                    )

    def _sync_graph(self, users, selected_cards, sync_cards):
        summary = {
            "skipped": False,
            "card_sync": None,
            "area_sync_count": 0,
            "user_sync_count": 0,
            "event_sync_count": 0,
            "errors": [],
        }
        repo = GraphRepository()

        try:
            if sync_cards:
                summary["card_sync"] = repo.sync_active_cards_and_benefits()
        except Exception as exc:
            summary["errors"].append(f"card graph sync failed: {exc}")

        for area_id, area in DEMO_AREAS.items():
            stores = self._build_stores(area_id, area)
            try:
                repo.sync_stores(area_id=area_id, area_name=area["name"], stores=stores)
                summary["area_sync_count"] += 1
            except Exception as exc:
                summary["errors"].append(f"area graph sync failed {area_id}: {exc}")

        for item in users:
            user = item["user"]
            spec = item["spec"]
            owned_card_keys = [
                build_card_graph_key(owned.card)
                for owned in UserOwnedCard.objects.filter(user=user).select_related("card")
            ]
            try:
                repo.sync_user_profile(
                    user_id=user.id,
                    nickname=spec["nickname"],
                    preferred_area_id=spec["preferred_area_id"],
                    preferred_area_name=spec["preferred_area"],
                    owned_card_keys=owned_card_keys,
                )
                summary["user_sync_count"] += 1
            except Exception as exc:
                summary["errors"].append(
                    f"user graph sync failed {user.username}: {exc}"
                )

        pending_events = (
            UserCardEvent.objects.filter(
                user__username__startswith="demo_",
                is_demo=True,
            )
            .exclude(graph_sync_status="synced")
            .select_related("user", "card")
            .order_by("pk")
        )
        for event in pending_events:
            try:
                repo.create_user_card_event(
                    user_id=event.user_id,
                    card_key=build_card_graph_key(event.card),
                    event_type=event.event_type,
                    area_id=event.area_id,
                    metadata=event.metadata_json,
                    is_demo=True,
                )
                event.graph_sync_status = "synced"
                event.graph_sync_error = ""
                event.save(update_fields=["graph_sync_status", "graph_sync_error"])
                summary["event_sync_count"] += 1
            except Exception as exc:
                event.graph_sync_status = "failed"
                event.graph_sync_error = str(exc)
                event.save(update_fields=["graph_sync_status", "graph_sync_error"])
                summary["errors"].append(
                    f"event graph sync failed {event.pk}: {exc}"
                )

        return summary

    def _build_stores(self, area_id, area):
        stores = []
        for category, count in area["store_counts"].items():
            for index in range(1, count + 1):
                stores.append(
                    {
                        "id": f"{area_id}:{category}:{index:03d}",
                        "name": f"{area['name']} {category} demo store {index}",
                        "category_key": category,
                    }
                )
        return stores
