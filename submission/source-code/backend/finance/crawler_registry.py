from dataclasses import dataclass

from finance.adapters.card_gorilla import CardGorillaAdapter
from finance.adapters.kakaobank import KakaoBankAdapter
from finance.adapters.hyundaicard import HyundaiCardAdapter
from finance.adapters.shinhan import ShinhanAdapter
from finance.adapters.tossbank import TossBankAdapter
from finance.adapters.wooricard import WooriCardAdapter


@dataclass(frozen=True)
class CrawlSource:
    key: str
    label: str
    adapter: object | None = None

    @property
    def is_available(self):
        return self.adapter is not None


SOURCES = {
    "card_gorilla": CrawlSource(
        "card_gorilla",
        "카드고릴라",
        adapter=CardGorillaAdapter(),
    ),
    "shinhan": CrawlSource("shinhan", "신한카드", adapter=ShinhanAdapter()),
    "kb": CrawlSource("kb", "KB국민카드"),
    "samsung": CrawlSource("samsung", "삼성카드"),
    "hyundai": CrawlSource(
        "hyundai",
        "현대카드",
        adapter=HyundaiCardAdapter(),
    ),
    "wooricard": CrawlSource(
        "wooricard",
        "우리카드",
        adapter=WooriCardAdapter(),
    ),
    "kakaobank": CrawlSource(
        "kakaobank",
        "카카오뱅크",
        adapter=KakaoBankAdapter(),
    ),
    "tossbank": CrawlSource(
        "tossbank",
        "토스뱅크",
        adapter=TossBankAdapter(),
    ),
}


def get_source(key):
    return SOURCES.get(key)
