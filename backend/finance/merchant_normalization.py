import re


BRAND_PATTERNS = {
    "스타벅스": (r"스타벅스", r"starbucks"),
    "투썸플레이스": (r"투썸플레이스", r"투썸", r"twosome"),
    "커피빈": (r"커피빈", r"coffee\s*bean"),
    "이디야": (r"이디야(?:커피)?", r"ediya"),
    "메가커피": (r"메가\s*(?:mgc\s*)?커피", r"mega\s*(?:mgc\s*)?coffee"),
    "컴포즈커피": (r"컴포즈(?:커피)?", r"compose\s*coffee"),
    "폴바셋": (r"폴\s*바셋", r"paul\s*bassett"),
    "빽다방": (r"빽다방", r"paik'?s\s*coffee"),
    "할리스": (r"할리스(?:커피)?", r"hollys"),
    "엔제리너스": (r"엔제리너스", r"angel[- ]?in[- ]?us"),
    "블루보틀": (r"블루\s*보틀", r"blue\s*bottle"),
    "매머드커피": (r"매머드(?:익스프레스)?(?:커피)?", r"mammoth\s*coffee"),
    "카페노티드": (r"카페\s*노티드", r"knotted"),
    "파스쿠찌": (r"파스쿠찌", r"pascucci"),
    "탐앤탐스": (r"탐앤탐스", r"tom\s*n\s*toms"),
    "CU": (r"(?<![a-z0-9])cu(?![a-z0-9])", r"씨유"),
    "GS25": (r"gs\s*25",),
    "세븐일레븐": (r"세븐일레븐", r"7[- ]?eleven"),
    "이마트24": (r"이마트\s*24", r"emart\s*24"),
    "미니스톱": (r"미니스톱", r"ministop"),
    "이마트트레이더스": (
        r"이마트\s*트레이더스",
        r"트레이더스",
        r"emart\s*traders",
    ),
    "이마트": (r"이마트(?!\s*24|\s*트레이더스)", r"(?<!traders\s)e-?mart"),
    "롯데마트": (r"롯데마트", r"롯데\s*마트", r"lotte\s*mart"),
    "홈플러스": (r"홈플러스", r"homeplus"),
    "하나로마트": (r"(?:농협)?\s*하나로(?:마트|클럽)", r"hanaro\s*mart"),
    "메가마트": (r"메가마트", r"mega\s*mart"),
    "롯데슈퍼": (r"롯데슈퍼", r"lotte\s*super"),
    "GS더프레시": (r"gs\s*(?:더\s*)?프레시", r"gs\s*수퍼마켓"),
    "배달의민족": (r"배달의민족", r"배민"),
    "요기요": (r"요기요", r"yogiyo"),
    "쿠팡이츠": (r"쿠팡이츠", r"coupang\s*eats"),
    "B마트": (r"(?<![a-z0-9])b\s*마트", r"비마트"),
    "맥도날드": (r"맥도날드", r"mcdonald"),
    "롯데리아": (r"롯데리아", r"lotteria"),
    "버거킹": (r"버거킹", r"burger\s*king"),
    "서브웨이": (r"서브웨이", r"subway"),
    "KFC": (r"(?<![a-z0-9])kfc(?![a-z0-9])",),
}


def normalize_merchant_brand(value):
    text = str(value or "").strip().casefold()
    if not text:
        return None

    for canonical_name, patterns in BRAND_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            return canonical_name
    return None


def normalize_scope_brand(value):
    canonical_name = normalize_merchant_brand(value)
    if canonical_name:
        return canonical_name
    return re.sub(r"\s+", " ", str(value or "").strip())

