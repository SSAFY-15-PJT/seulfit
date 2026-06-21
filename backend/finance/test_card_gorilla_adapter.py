import json
from email.message import Message
from io import BytesIO

from django.test import TestCase

from finance.adapters.card_gorilla import CardGorillaAdapter
from finance.models import CardProduct, CrawlJob, CrawlStatus


class FakeResponse(BytesIO):
    def __init__(self, payload, content_type="application/json; charset=utf-8"):
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        super().__init__(payload.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class CardGorillaAdapterTests(TestCase):
    def test_discovery_collects_limit_for_each_card_type(self):
        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse(
                    "User-agent: *\nAllow: /\n",
                    "text/plain; charset=utf-8",
                )
            card_gb = "CHK" if "card_gb=CHK" in request.full_url else "CRD"
            start = 200 if card_gb == "CHK" else 100
            return FakeResponse(
                [
                    {
                        "ranking": index,
                        "card_idx": start + index,
                        "name": f"{card_gb} Card {index}",
                        "corp": json.dumps({"name": f"{card_gb} Issuer"}),
                        "annual_fee_basic": "없음",
                        "card_img": f"/{start + index}.png",
                        "score": str(1000 - index),
                    }
                    for index in range(1, 4)
                ]
            )

        items = CardGorillaAdapter(opener=opener).discover_items(limit=2)

        self.assertEqual(len(items), 4)
        self.assertEqual(
            [item["card_gb"] for item in items],
            ["CRD", "CRD", "CHK", "CHK"],
        )
        self.assertEqual(items[0]["external_id"], "101")
        self.assertEqual(items[2]["external_id"], "201")
        self.assertEqual(
            items[2]["ranking_summary"]["issuer"],
            "CHK Issuer",
        )

    def test_run_stores_raw_detail_without_creating_card_products(self):
        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse(
                    "User-agent: *\nAllow: /\n",
                    "text/plain; charset=utf-8",
                )
            if "/charts/ranking" in request.full_url:
                card_gb = "CHK" if "card_gb=CHK" in request.full_url else "CRD"
                card_id = 2 if card_gb == "CHK" else 1
                return FakeResponse(
                    [
                        {
                            "ranking": 1,
                            "card_idx": card_id,
                            "name": f"{card_gb} Card",
                            "corp": json.dumps({"name": "Test Issuer"}),
                        }
                    ]
                )
            card_id = int(request.full_url.rsplit("/", 1)[-1])
            return FakeResponse(
                {
                    "idx": card_id,
                    "name": f"Card {card_id}",
                    "cate": "CHK" if card_id == 2 else "CRD",
                    "pre_month_money": 200000,
                    "key_benefit": [{"title": "카페", "info": "5% 할인"}],
                }
            )

        job = CrawlJob.objects.create(source_channel="card_gorilla")
        CardGorillaAdapter(opener=opener).run(job=job, limit=1)

        job.refresh_from_db()
        self.assertEqual(job.status, CrawlStatus.SUCCESS)
        self.assertEqual(job.items.count(), 2)
        self.assertEqual(CardProduct.objects.count(), 0)

        payloads = {
            item.raw_payload["card_type"]: item.raw_payload
            for item in job.items.all()
        }
        self.assertEqual(payloads["credit"]["detail"]["name"], "Card 1")
        self.assertEqual(payloads["debit"]["detail"]["name"], "Card 2")
        self.assertEqual(
            payloads["debit"]["detail"]["key_benefit"][0]["title"],
            "카페",
        )
