import json
from urllib.parse import urlencode

from .base import BaseCardAdapter


class CardGorillaAdapter(BaseCardAdapter):
    source_key = "card_gorilla"
    base_url = "https://www.card-gorilla.com/card"
    robots_url = "https://www.card-gorilla.com/robots.txt"
    api_base_url = "https://api.card-gorilla.com:8080/v1"
    default_limit_per_type = 20
    ranking_configs = (
        ("CRD", "top100"),
        ("CHK", "check100"),
    )

    def discover_items(self, limit=None):
        self.assert_collection_allowed()
        limit_per_type = limit or self.default_limit_per_type
        items = []

        for card_gb, chart in self.ranking_configs:
            query = urlencode(
                {
                    "term": "weekly",
                    "card_gb": card_gb,
                    "limit": limit_per_type,
                    "chart": chart,
                }
            )
            ranking_url = f"{self.api_base_url}/charts/ranking?{query}"
            ranking = json.loads(self.request_text(ranking_url))
            for row in ranking[:limit_per_type]:
                external_id = str(row.get("card_idx") or row.get("idx") or "")
                if not external_id:
                    continue
                items.append(
                    {
                        "external_id": external_id,
                        "source_url": f"{self.api_base_url}/cards/{external_id}",
                        "detail_page_url": (
                            f"https://www.card-gorilla.com/card/detail/{external_id}"
                        ),
                        "card_gb": card_gb,
                        "ranking": row.get("ranking"),
                        "ranking_source_url": ranking_url,
                        "ranking_summary": self._ranking_summary(row),
                    }
                )

        return items

    def run(self, job, retry_failed=False, limit=None, stdout=None):
        from finance.crawling import enqueue_items, run_crawl_job

        discovered_items = self.discover_items(limit=limit)
        enqueue_items(job, discovered_items)
        discovered_by_url = {
            item["source_url"]: item for item in discovered_items
        }

        def fetch_item(item):
            discovered = discovered_by_url.get(item.source_url, {})
            detail = json.loads(self.request_text(item.source_url))
            payload = {
                "source_channel": self.source_key,
                "external_id": item.external_id,
                "card_type": self._card_type(
                    detail.get("cate") or discovered.get("card_gb")
                ),
                "detail_page_url": discovered.get("detail_page_url", ""),
                "api_source_url": item.source_url,
                "ranking_source_url": discovered.get("ranking_source_url", ""),
                "ranking": discovered.get("ranking"),
                "ranking_summary": discovered.get("ranking_summary", {}),
                "detail": detail,
            }
            if stdout:
                stdout.write(
                    f"{payload['card_type']} #{payload['ranking']} "
                    f"{detail.get('name', item.external_id)}: raw collected"
                )
            return payload, {
                "card_type": payload["card_type"],
                "ranking": payload["ranking"],
                "external_id": item.external_id,
            }

        return run_crawl_job(
            job,
            fetch_item,
            retry_failed=retry_failed,
        )

    @staticmethod
    def _card_type(card_gb):
        return {
            "CRD": "credit",
            "CHK": "debit",
        }.get(card_gb, "")

    @staticmethod
    def _ranking_summary(row):
        corp = row.get("corp") or {}
        if isinstance(corp, str):
            try:
                corp = json.loads(corp)
            except json.JSONDecodeError:
                corp = {}
        return {
            "name": row.get("name", ""),
            "issuer": corp.get("name", ""),
            "annual_fee_basic": row.get("annual_fee_basic", ""),
            "card_image_path": row.get("card_img", ""),
            "score": row.get("score"),
        }
