import base64
import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from django.conf import settings

from .models import CardProduct, ParseStatus


CARD_QUERY = """
UNWIND $cards AS card
MERGE (c:Card {key: card.key})
SET c.name = card.name,
    c.issuer = card.issuer,
    c.provider = card.provider,
    c.card_type = card.card_type,
    c.annual_fee = card.annual_fee,
    c.previous_month_requirement = card.previous_month_requirement,
    c.source_url = card.source_url,
    c.image_url = card.image_url,
    c.updated_at = datetime()
"""

BENEFIT_QUERY = """
UNWIND $benefits AS benefit
MATCH (c:Card {key: benefit.card_key})
MERGE (b:Benefit {key: benefit.key})
SET b.discount_type = benefit.discount_type,
    b.discount_rate = benefit.discount_rate,
    b.discount_amount = benefit.discount_amount,
    b.minimum_transaction_amount = benefit.minimum_transaction_amount,
    b.maximum_transaction_amount = benefit.maximum_transaction_amount,
    b.daily_benefit_limit = benefit.daily_benefit_limit,
    b.monthly_usage_limit = benefit.monthly_usage_limit,
    b.category_monthly_limit = benefit.category_monthly_limit,
    b.merchant_scope = benefit.merchant_scope,
    b.channel = benefit.channel,
    b.start_hour = benefit.start_hour,
    b.end_hour = benefit.end_hour,
    b.updated_at = datetime()
MERGE (category:Category {key: benefit.category})
MERGE (c)-[:HAS_BENEFIT]->(b)
MERGE (b)-[:APPLIES_TO]->(category)
"""

PRUNE_BENEFITS_QUERY = """
MATCH (b:Benefit)
WHERE b.key STARTS WITH 'seulpick:'
  AND NOT b.key IN $benefit_keys
DETACH DELETE b
"""

PRUNE_CARDS_QUERY = """
MATCH (c:Card)
WHERE c.key STARTS WITH 'seulpick:'
  AND NOT c.key IN $card_keys
DETACH DELETE c
"""


@dataclass(frozen=True)
class GraphSyncPayload:
    cards: list[dict]
    benefits: list[dict]


def build_graph_sync_payload():
    cards = []
    benefits = []
    queryset = (
        CardProduct.objects.filter(parse_status=ParseStatus.ACTIVE)
        .prefetch_related("benefits", "images")
        .order_by("pk")
    )
    for card in queryset:
        active_benefits = list(
            card.benefits.filter(parse_status=ParseStatus.ACTIVE)
        )
        if card.annual_fee is None or not active_benefits:
            continue
        card_key = f"seulpick:{card.source_channel}:{card.external_id}"
        primary_image = card.images.filter(is_primary=True).first()
        cards.append(
            {
                "key": card_key,
                "name": card.name,
                "issuer": card.issuer,
                "provider": card.provider,
                "card_type": card.card_type,
                "annual_fee": card.annual_fee,
                "previous_month_requirement": card.previous_month_requirement,
                "source_url": card.source_url,
                "image_url": (
                    primary_image.source_url if primary_image else ""
                ),
            }
        )
        for benefit in active_benefits:
            benefits.append(
                {
                    "key": f"{card_key}:benefit:{benefit.pk}",
                    "card_key": card_key,
                    "category": benefit.category,
                    "discount_type": benefit.discount_type,
                    "discount_rate": (
                        float(benefit.discount_rate)
                        if benefit.discount_rate is not None
                        else None
                    ),
                    "discount_amount": benefit.discount_amount,
                    "minimum_transaction_amount": (
                        benefit.minimum_transaction_amount
                    ),
                    "maximum_transaction_amount": (
                        benefit.maximum_transaction_amount
                    ),
                    "daily_benefit_limit": benefit.daily_benefit_limit,
                    "monthly_usage_limit": benefit.monthly_usage_limit,
                    "category_monthly_limit": benefit.category_monthly_limit,
                    "merchant_scope": benefit.merchant_scope,
                    "channel": benefit.channel,
                    "start_hour": benefit.start_hour,
                    "end_hour": benefit.end_hour,
                }
            )
    return GraphSyncPayload(cards=cards, benefits=benefits)


def build_graph_statements(payload):
    card_keys = [card["key"] for card in payload.cards]
    benefit_keys = [benefit["key"] for benefit in payload.benefits]
    return [
        {"statement": CARD_QUERY, "parameters": {"cards": payload.cards}},
        {
            "statement": BENEFIT_QUERY,
            "parameters": {"benefits": payload.benefits},
        },
        {
            "statement": PRUNE_BENEFITS_QUERY,
            "parameters": {"benefit_keys": benefit_keys},
        },
        {
            "statement": PRUNE_CARDS_QUERY,
            "parameters": {"card_keys": card_keys},
        },
    ]


def sync_active_cards_to_neo4j(opener=urlopen):
    if not settings.NEO4J_PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD가 설정되지 않았습니다.")
    payload = build_graph_sync_payload()
    statements = build_graph_statements(payload)
    endpoint = (
        f"{settings.NEO4J_HTTP_URI.rstrip('/')}/db/"
        f"{settings.NEO4J_DATABASE}/tx/commit"
    )
    credentials = base64.b64encode(
        f"{settings.NEO4J_USER}:{settings.NEO4J_PASSWORD}".encode("utf-8")
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
            "; ".join(error.get("message", "") for error in result["errors"])
        )
    return {
        "card_count": len(payload.cards),
        "benefit_count": len(payload.benefits),
        "endpoint": endpoint,
    }
