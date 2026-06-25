from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


CRAWLER_USER_AGENT = "SeulPickCardCrawler/1.0"


class CollectionPolicyBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedImage:
    source_url: str
    alt_text: str = ""


class ProductPageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.meta = {}
        self.links = []
        self.images = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content")
            if key and content:
                self.meta[key] = content.strip()
        elif tag == "a" and attributes.get("href"):
            self.links.append(urljoin(self.base_url, attributes["href"]))
        elif tag == "img" and attributes.get("src"):
            self.images.append(
                ParsedImage(
                    source_url=urljoin(self.base_url, attributes["src"]),
                    alt_text=attributes.get("alt", "").strip(),
                )
            )

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.text_parts.append(text)

    @property
    def text(self):
        return " ".join(self.text_parts)


class BaseCardAdapter:
    source_key = ""
    base_url = ""
    robots_url = ""

    def __init__(self, opener=urlopen):
        self.opener = opener

    def request_text(self, url, timeout=15):
        request = Request(url, headers={"User-Agent": CRAWLER_USER_AGENT})
        with self.opener(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def assert_collection_allowed(self):
        robots_text = self.request_text(self.robots_url)
        parser = RobotFileParser()
        parser.set_url(self.robots_url)
        parser.parse(robots_text.splitlines())
        if not parser.can_fetch(CRAWLER_USER_AGENT, self.base_url):
            raise CollectionPolicyBlocked(
                f"{self.source_key}: robots.txt가 자동 수집을 허용하지 않음"
            )
