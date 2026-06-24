import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class VlmSpendingProfileTests(SimpleTestCase):
    def test_dummy_profiles_cover_primary_and_edge_cases(self):
        path = (
            Path(settings.BASE_DIR)
            / "finance"
            / "testdata"
            / "vlm_spending_profiles.json"
        )
        profiles = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(profiles), 9)
        self.assertEqual(
            {item["profile"] for item in profiles},
            {
                "cafe_focused",
                "delivery_focused",
                "dining_focused",
                "mart_focused",
                "shopping_focused",
                "balanced",
                "zero_spending",
                "partial_categories",
                "vlm_report_payload",
            },
        )
        for item in profiles:
            self.assertIn("user", item)
            self.assertIn("spending", item)
            self.assertTrue(
                all(amount >= 0 for amount in item["spending"].values())
            )
        self.assertTrue(
            any(item["owned_card_ids"] for item in profiles)
        )
        report_profile = next(
            item for item in profiles if item["profile"] == "vlm_report_payload"
        )
        self.assertEqual(
            report_profile["parsed_payload"]["spending"],
            report_profile["spending"],
        )
