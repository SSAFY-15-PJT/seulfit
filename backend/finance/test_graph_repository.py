import json
from io import BytesIO
from django.test import TestCase, override_settings
from finance.graph_repository import GraphRepository
from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class GraphRepositoryTests(TestCase):
    def setUp(self):
        # Setup sample SQLite Card to test active sync
        self.card = CardProduct.objects.create(
            external_id="repo-sync-card",
            issuer="신한카드",
            provider="신한카드",
            source_channel="shinhan",
            card_type=CardType.CREDIT,
            name="신한 딥오일",
            source_url="https://example.com/shinhan-deep-oil",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="원문",
        )
        BenefitRule.objects.create(
            card=self.card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            raw_text="카페 5% 할인",
            parse_status=ParseStatus.ACTIVE,
        )

        self.repo = GraphRepository(
            http_uri="http://neo4j.test:7474",
            database="neo4j",
            user="neo4j",
            password="secret",
        )

    def test_execute_statements_success(self):
        statements = [{"statement": "MATCH (n) RETURN count(n)"}]
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = request.headers
            return FakeResponse(b'{"results":[{"columns":["count"],"data":[{"row":[0]}]}],"errors":[]}')

        result = self.repo.execute_statements(statements, opener=opener)
        self.assertEqual(captured["url"], "http://neo4j.test:7474/db/neo4j/tx/commit")
        self.assertIn("Authorization", captured["headers"])
        self.assertEqual(result["results"][0]["data"][0]["row"][0], 0)

    def test_execute_statements_error(self):
        statements = [{"statement": "INVALID SYNTAX"}]

        def opener(request, timeout):
            return FakeResponse(
                b'{"results":[],"errors":[{"code":"Neo.ClientError.Statement.SyntaxError","message":"Syntax error..."}]}'
            )

        with self.assertRaises(RuntimeError) as ctx:
            self.repo.execute_statements(statements, opener=opener)
        self.assertIn("Syntax error...", str(ctx.exception))

    def test_sync_active_cards_and_benefits(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(b'{"results":[],"errors":[]}')

        stats = self.repo.sync_active_cards_and_benefits(opener=opener)
        self.assertEqual(stats["card_count"], 1)
        self.assertEqual(stats["benefit_count"], 1)
        self.assertEqual(len(captured["body"]["statements"]), 4)

    def test_sync_user_profile_full(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(b'{"results":[],"errors":[]}')

        self.repo.sync_user_profile(
            user_id=42,
            nickname="세울핏러",
            preferred_area_id="gangnam_station",
            preferred_area_name="강남역",
            owned_card_keys=["seulpick:shinhan:repo-sync-card"],
            opener=opener,
        )

        statements = captured["body"]["statements"]
        self.assertEqual(len(statements), 4)
        # 1. User MERGE
        self.assertIn("MERGE (u:User", statements[0]["statement"])
        self.assertEqual(statements[0]["parameters"]["nickname"], "세울핏러")
        # 2. Area Lives_in MERGE
        self.assertIn("MERGE (a:Area", statements[1]["statement"])
        self.assertEqual(statements[1]["parameters"]["area_name"], "강남역")
        # 3. Clear existing OWNS relationships
        self.assertIn("DELETE r", statements[2]["statement"])
        # 4. Create new OWNS relationships
        self.assertIn("MERGE (u)-[r:OWNS]->(c)", statements[3]["statement"])
        self.assertEqual(statements[3]["parameters"]["card_keys"], ["seulpick:shinhan:repo-sync-card"])

    def test_create_user_card_event_creates_event_relationship(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(b'{"results":[],"errors":[]}')

        self.repo.create_user_card_event(
            user_id=1,
            card_key="seulpick:shinhan:repo-sync-card",
            event_type="clicked",
            area_id="geo_37_497_127_027",
            metadata={"rank": 1},
            opener=opener,
        )

        statement = captured["body"]["statements"][0]
        self.assertIn("CREATE (u)-[r:CLICKED]->(c)", statement["statement"])
        self.assertEqual(statement["parameters"]["user_id"], "1")
        self.assertEqual(
            statement["parameters"]["card_key"],
            "seulpick:shinhan:repo-sync-card",
        )
        self.assertEqual(statement["parameters"]["metadata"], '{"rank": 1}')

    def test_sync_stores(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(b'{"results":[],"errors":[]}')

        stores = [
            {"id": "store1", "name": "스타벅스 강남점", "category_key": "cafe"},
            {"id": "store2", "name": "CU 역삼점", "category_key": "convenience"},
        ]
        self.repo.sync_stores(
            area_id="gangnam_station",
            area_name="강남역",
            stores=stores,
            opener=opener,
        )

        statements = captured["body"]["statements"]
        self.assertEqual(len(statements), 2)
        # Area merge
        self.assertIn("MERGE (a:Area", statements[0]["statement"])
        # Stores unwind merge
        self.assertIn("UNWIND $stores", statements[1]["statement"])
        self.assertEqual(statements[1]["parameters"]["stores"][0]["id"], "store1")
        self.assertEqual(statements[1]["parameters"]["stores"][1]["category_key"], "convenience")

    def test_find_card_candidates_by_area(self):
        def opener(request, timeout):
            return FakeResponse(
                b'{"results":[{"columns":["card_key","category_key","store_count","area_store_count","category_share"],"data":['
                b'{"row":["seulpick:shinhan:repo-sync-card","cafe",5,25,0.2]}'
                b']}],"errors":[]}'
            )

        candidates = self.repo.find_card_candidates_by_area(
            area_id="gangnam_station",
            opener=opener,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["card_key"], "seulpick:shinhan:repo-sync-card")
        self.assertEqual(candidates[0]["category_key"], "cafe")
        self.assertEqual(candidates[0]["store_count"], 5)
        self.assertEqual(candidates[0]["area_store_count"], 25)
        self.assertEqual(candidates[0]["category_share"], 0.2)
