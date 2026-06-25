from django.core.management.base import BaseCommand, CommandError

from finance.graph_repository import GraphRepository
from hyperlocal.services import DEFAULT_CENTER, collect_area_graph_stores


class Command(BaseCommand):
    help = "선택 지역의 주변 매장 데이터를 Neo4j Area-Store-Category 그래프로 동기화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--area-id", required=True)
        parser.add_argument("--area-name", default="")
        parser.add_argument("--lat", type=float, default=DEFAULT_CENTER["lat"])
        parser.add_argument("--lng", type=float, default=DEFAULT_CENTER["lng"])
        parser.add_argument("--radius", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--use-mock",
            action="store_true",
            help="Kakao API 없이 로컬 개발용 mock 매장 데이터를 동기화합니다.",
        )

    def handle(self, *args, **options):
        area_id = options["area_id"]
        area_name = options["area_name"] or area_id
        try:
            stores = collect_area_graph_stores(
                area_id=area_id,
                lat=options["lat"],
                lng=options["lng"],
                radius=options["radius"],
                use_mock=options["use_mock"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if options["dry_run"]:
            self.stdout.write(
                f"dry-run\tarea={area_id}\tstores={len(stores)}"
            )
            return

        repo = GraphRepository()
        repo.sync_stores(area_id=area_id, area_name=area_name, stores=stores)
        self.stdout.write(
            self.style.SUCCESS(
                f"synced\tarea={area_id}\tstores={len(stores)}"
            )
        )
