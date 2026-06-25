import base64
import json
from urllib.request import Request, urlopen

from django.conf import settings

from .graph_sync import build_graph_sync_payload, build_graph_statements


class GraphRepository:
    """
    Neo4j Graph Database Repository Layer.
    Responsible for executing Cypher queries and managing graph sync for:
    - User profiles & owned cards
    - Areas & Stores
    - Card candidate exploration
    """

    def __init__(self, http_uri=None, database=None, user=None, password=None):
        self.http_uri = http_uri or settings.NEO4J_HTTP_URI
        self.database = database or settings.NEO4J_DATABASE
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD

    def execute_statements(self, statements, opener=urlopen):
        """
        Executes a list of Cypher statements in a single transaction via Neo4j HTTP REST endpoint.
        """
        if not self.password:
            raise RuntimeError("NEO4J_PASSWORD가 설정되지 않았습니다.")

        endpoint = f"{self.http_uri.rstrip('/')}/db/{self.database}/tx/commit"
        credentials = base64.b64encode(
            f"{self.user}:{self.password}".encode("utf-8")
        ).decode("ascii")

        request = Request(
            endpoint,
            data=json.dumps({"statements": statements}).encode("utf-8"),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        with opener(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        if result.get("errors"):
            raise RuntimeError(
                "; ".join(
                    error.get("message", "") for error in result["errors"]
                )
            )

        return result

    def sync_active_cards_and_benefits(self, opener=urlopen):
        """
        Synchronizes all active CardProduct and BenefitRule instances from SQLite to Neo4j.
        """
        payload = build_graph_sync_payload()
        statements = build_graph_statements(payload)
        self.execute_statements(statements, opener=opener)
        return {
            "card_count": len(payload.cards),
            "benefit_count": len(payload.benefits),
        }

    def sync_user_profile(
        self,
        user_id,
        nickname=None,
        preferred_area_id=None,
        preferred_area_name=None,
        owned_card_keys=None,
        opener=urlopen,
    ):
        """
        Synchronizes a user profile, lives_in area relationship, and owned cards relationships to Neo4j.
        """
        statements = []

        # 1. Merge User
        user_params = {"user_id": str(user_id)}
        user_set_clause = ""
        if nickname is not None:
            user_params["nickname"] = nickname
            user_set_clause = "SET u.nickname = $nickname"

        statements.append(
            {
                "statement": f"MERGE (u:User {{id: $user_id}}) {user_set_clause} SET u.updated_at = datetime()",
                "parameters": user_params,
            }
        )

        # 2. Merge preferred Area & lives_in relationship
        if preferred_area_id:
            statements.append(
                {
                    "statement": """
                    MERGE (a:Area {id: $area_id})
                    SET a.name = $area_name, a.updated_at = datetime()
                    WITH a
                    MATCH (u:User {id: $user_id})
                    MERGE (u)-[r:LIVES_IN]->(a)
                    SET r.updated_at = datetime()
                    """,
                    "parameters": {
                        "user_id": str(user_id),
                        "area_id": str(preferred_area_id),
                        "area_name": str(preferred_area_name or preferred_area_id),
                    },
                }
            )

        # 3. Synchronize owned cards (OWNS relation)
        if owned_card_keys is not None:
            # Clear existing relationships
            statements.append(
                {
                    "statement": """
                    MATCH (u:User {id: $user_id})-[r:OWNS]->(:Card)
                    DELETE r
                    """,
                    "parameters": {"user_id": str(user_id)},
                }
            )
            # Create new relationships
            if owned_card_keys:
                statements.append(
                    {
                        "statement": """
                        MATCH (u:User {id: $user_id})
                        MATCH (c:Card)
                        WHERE c.key IN $card_keys
                        MERGE (u)-[r:OWNS]->(c)
                        SET r.updated_at = datetime()
                        """,
                        "parameters": {
                            "user_id": str(user_id),
                            "card_keys": list(owned_card_keys),
                        },
                    }
                )

        self.execute_statements(statements, opener=opener)

    def create_user_card_event(
        self,
        user_id,
        card_key,
        event_type,
        area_id="",
        metadata=None,
        is_demo=False,
        opener=urlopen,
    ):
        relationship_type = str(event_type or "").upper()
        allowed_types = {
            "VIEWED",
            "CLICKED",
            "LIKED",
            "DISMISSED",
            "APPLIED_FOR",
        }
        if relationship_type not in allowed_types:
            raise ValueError(f"Unsupported card event type: {event_type}")

        statement = f"""
        MATCH (u:User {{id: $user_id}})
        MATCH (c:Card {{key: $card_key}})
        CREATE (u)-[r:{relationship_type}]->(c)
        SET r.area_id = $area_id,
            r.metadata = $metadata,
            r.is_demo = $is_demo,
            r.created_at = datetime()
        """
        self.execute_statements(
            [
                {
                    "statement": statement,
                    "parameters": {
                        "user_id": str(user_id),
                        "card_key": str(card_key),
                        "area_id": str(area_id or ""),
                        "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                        "is_demo": bool(is_demo),
                    },
                }
            ],
            opener=opener,
        )

    def sync_stores(self, area_id, area_name, stores, opener=urlopen):
        """
        Synchronizes an Area and its nearby stores with LOCATED_IN and BELONGS_TO relationships.
        `stores` is a list of dicts: [{'id': str, 'name': str, 'category_key': str}]
        """
        statements = []

        # 1. Merge Area
        statements.append(
            {
                "statement": "MERGE (a:Area {id: $area_id}) SET a.name = $area_name, a.updated_at = datetime()",
                "parameters": {
                    "area_id": str(area_id),
                    "area_name": str(area_name),
                },
            }
        )

        # 2. Merge Stores & Relations
        if stores:
            statements.append(
                {
                    "statement": """
                    UNWIND $stores AS store
                    MERGE (s:Store {id: store.id})
                    SET s.name = store.name, s.updated_at = datetime()
                    WITH s, store
                    MATCH (a:Area {id: $area_id})
                    MERGE (s)-[r_loc:LOCATED_IN]->(a)
                    SET r_loc.updated_at = datetime()
                    WITH s, store
                    MERGE (cat:Category {key: store.category_key})
                    SET cat.updated_at = datetime()
                    MERGE (s)-[r_bel:BELONGS_TO]->(cat)
                    SET r_bel.updated_at = datetime()
                    """,
                    "parameters": {
                        "area_id": str(area_id),
                        "stores": [
                            {
                                "id": str(item["id"]),
                                "name": str(item["name"]),
                                "category_key": str(item["category_key"]),
                            }
                            for item in stores
                        ],
                    },
                }
            )

        self.execute_statements(statements, opener=opener)

    def find_card_candidates_by_area(self, area_id, opener=urlopen):
        """
        Executes Cypher match query to find Cards that have benefits applying to the Store Categories
        located in the selected Area.
        Returns a dictionary mapping Card key -> list of Category keys, and list of candidates.
        """
        query = """
        MATCH (a:Area {id: $area_id})<-[:LOCATED_IN]-(area_store:Store)
        WITH a, count(area_store) AS area_store_count
        MATCH (a)<-[:LOCATED_IN]-(s:Store)-[:BELONGS_TO]->(cat:Category)
        WITH a, area_store_count, cat, count(s) AS nearby_store_count
        MATCH (card:Card)-[:HAS_BENEFIT]->(b:Benefit)-[:APPLIES_TO]->(cat)
        RETURN
            card.key AS card_key,
            cat.key AS category_key,
            nearby_store_count,
            area_store_count,
            CASE
                WHEN area_store_count = 0 THEN 0.0
                ELSE toFloat(nearby_store_count) / area_store_count
            END AS category_share,
            collect(b.key) AS benefits
        ORDER BY nearby_store_count DESC
        """
        statements = [
            {"statement": query, "parameters": {"area_id": str(area_id)}}
        ]

        try:
            result = self.execute_statements(statements, opener=opener)
        except Exception:
            # Under standard runtime rules, if Neo4j is unavailable, return empty results
            return []

        candidates = []
        results_list = result.get("results")
        if results_list and results_list[0].get("data"):
            for item in results_list[0]["data"]:
                row = item.get("row")
                if row and len(row) >= 3:
                    card_key = row[0]
                    category_key = row[1]
                    count = row[2]
                    area_store_count = row[3] if len(row) > 3 else None
                    category_share = row[4] if len(row) > 4 else None
                    candidates.append(
                        {
                            "card_key": card_key,
                            "category_key": category_key,
                            "store_count": count,
                            "area_store_count": area_store_count,
                            "category_share": category_share,
                        }
                    )

        return candidates
