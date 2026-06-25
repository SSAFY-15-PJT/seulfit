EXAMPLE_NOTICE = "실제 연동 전 화면 검증을 위한 [예제] 데이터입니다."

OVERVIEW = {
    "isExample": True,
    "notice": EXAMPLE_NOTICE,
    "area": "서울 강남구 역삼동",
    "radiusMeters": 500,
    "linkedSpend": 800000,
    "recommendedCards": 4,
    "seulScore": 86,
    "scoreLabel": "상위 12%",
    "monthlySaving": 42000,
    "activeUsers": 18320,
    "topCategories": [
        {"name": "카페", "ratio": 25, "amount": 120000},
        {"name": "음식점/외식", "ratio": 20, "amount": 200000},
        {"name": "마트/슈퍼", "ratio": 20, "amount": 150000},
        {"name": "편의점", "ratio": 15, "amount": 80000},
        {"name": "배달", "ratio": 10, "amount": 130000},
        {"name": "기타", "ratio": 10, "amount": 20000},
    ],
}

PLACES = [
    {"id": 1, "isExample": True, "name": "브루잉 사인점", "category": "카페", "distance": 120, "score": 92, "benefit": "커피 20% 청구할인", "x": 48, "y": 36},
    {"id": 2, "isExample": True, "name": "세븐역삼점", "category": "편의점", "distance": 180, "score": 88, "benefit": "간편식 1+1 쿠폰", "x": 58, "y": 45},
    {"id": 3, "isExample": True, "name": "그린마트 역삼", "category": "마트/슈퍼", "distance": 260, "score": 84, "benefit": "생활용품 5% 할인", "x": 38, "y": 55},
    {"id": 4, "isExample": True, "name": "오피스 델리", "category": "음식점/외식", "distance": 310, "score": 79, "benefit": "점심 10% 적립", "x": 66, "y": 28},
    {"id": 5, "isExample": True, "name": "라이트 배달존", "category": "배달", "distance": 340, "score": 81, "benefit": "배달 15% 할인", "x": 29, "y": 40},
]

CARDS = [
    {
        "id": "daily-plus",
        "isExample": True,
        "owned": True,
        "name": "OO카드",
        "issuer": "서울카드",
        "annualFee": 12000,
        "match": 92,
        "saving": 32400,
        "requiredSpend": 300000,
        "tags": ["카페", "편의점", "마트"],
        "benefits": ["카페 50% 할인", "편의점 10% 할인", "마트 5% 할인"],
    },
    {
        "id": "local-fit",
        "isExample": True,
        "owned": False,
        "name": "△스카드",
        "issuer": "국민은행",
        "annualFee": 0,
        "match": 86,
        "saving": 24800,
        "requiredSpend": 200000,
        "tags": ["편의점", "마트", "교통"],
        "benefits": ["편의점 10% 할인", "마트 10% 할인", "대중교통 10% 할인"],
    },
    {
        "id": "food-card",
        "isExample": True,
        "owned": True,
        "name": "□□카드",
        "issuer": "신한카드",
        "annualFee": 15000,
        "match": 81,
        "saving": 27100,
        "requiredSpend": 400000,
        "tags": ["배달", "음식점/외식"],
        "benefits": ["배달 15% 할인", "음식점 10% 할인", "주말 외식 추가 적립"],
    },
]

VIDEOS = [
    {"id": 1, "isExample": True, "title": "[예제] 2026 혜택 좋은 신용카드 TOP 5", "channel": "카드테크랩", "views": "12만", "age": "2일 전", "duration": "8:21", "category": "카드 추천", "tags": ["카드추천", "혜택비교"]},
    {"id": 2, "isExample": True, "title": "[예제] 사회초년생 카드 추천, 연회비부터 실적까지", "channel": "머니레이더", "views": "6.4만", "age": "5일 전", "duration": "10:31", "category": "카드 추천", "tags": ["체크카드", "초년생"]},
    {"id": 3, "isExample": True, "title": "[예제] 월 10만원 아끼는 카드 사용법", "channel": "절약하는시그마", "views": "5.7만", "age": "1주 전", "duration": "7:12", "category": "사용 후기", "tags": ["리뷰", "카드테크"]},
    {"id": 4, "isExample": True, "title": "[예제] 역삼동 소비 분석으로 생활비 줄이기", "channel": "SeulPick 연구소", "views": "9.1만", "age": "3일 전", "duration": "9:01", "category": "비교 분석", "tags": ["상권분석", "카드혜택"]},
]

VIDEO_CHANNELS = [
    {"name": "카드테크랩", "subscribers": "18.2만", "topic": "카드 추천"},
    {"name": "머니레이더", "subscribers": "9.7만", "topic": "초년생 재테크"},
    {"name": "카드의 정석", "subscribers": "6.1만", "topic": "혜택 비교"},
]

POSTS = [
    {"id": 1, "isExample": True, "title": "역삼역 점심 맛집 할인 카드 추천 부탁해요", "author": "직장인A", "tab": "자유게시판", "views": 12, "comments": 3, "budget": 200000, "created": "방금"},
    {"id": 2, "isExample": True, "title": "카페 자주 가면 체크카드가 더 좋나요?", "author": "커피러버", "tab": "질문답변", "views": 8, "comments": 1, "budget": 150000, "created": "방금"},
    {"id": 3, "isExample": True, "title": "삼성 vs 신한 생활권 카드 혜택 차이", "author": "분석러", "tab": "동네 정보", "views": 22, "comments": 5, "budget": 180000, "created": "15분 전"},
]

COMMUNITY_META = {
    "popularKeywords": ["카드추천", "혜택비교", "체크카드", "신용카드", "배달 할인", "AI 데이터 가이드"],
    "aiQuestions": ["사회초년생에게 맞는 카드 추천", "마트 소비가 많은 사람의 카드 조합", "배달 혜택 좋은 카드 비교", "역삼동 직장인 소비 패턴 분석"],
}

PROFILE = {
    "isExample": True,
    "name": "김슬픽",
    "email": "seulpick@example.com",
    "monthlySpend": 800000,
    "savedReports": 4,
    "savedCards": 3,
    "trend": [55, 70, 85, 60, 75, 65],
    "categories": OVERVIEW["topCategories"],
    "savedReportItems": ["역삼동 카페 소비 리포트", "점심시간 외식 할인 분석", "대중교통 절약 리포트"],
    "savedCardItems": ["OO카드", "△스카드", "□□카드"],
    "accountSettings": ["이메일 변경", "기본 위치 설정", "알림 설정", "로그아웃"],
}
