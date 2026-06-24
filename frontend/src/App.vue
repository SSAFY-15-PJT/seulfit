<script setup>
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "./api";

const reportFilters = [];
const selectedReportFilter = ref("");

const pages = [
  { id: "home", label: "대시보드" },
  { id: "map", label: "슬세권 분석" },
  { id: "cards", label: "카드 대시보드" },
  { id: "videos", label: "유튜브 검색" },
  { id: "community", label: "커뮤니티" },
  { id: "profile", label: "프로필" },
];

const spendRows = ref([
  { name: "카페", amount: 120000, ratio: 25 },
  { name: "편의점", amount: 80000, ratio: 15 },
  { name: "마트/슈퍼", amount: 150000, ratio: 20 },
  { name: "음식점/배달", amount: 200000, ratio: 20 },
  { name: "의류/소품", amount: 130000, ratio: 10 },
  { name: "교통", amount: 100000, ratio: 10 },
  { name: "기타", amount: 20000, ratio: 10 },
]);

const userProfile = ref({
  name: "김슬픽",
  email: "seulpick@example.com",
  ownedCards: ["트래블월렛 우리카드", "신한카드 Simple Plan+"],
});

const mapCategories = ["전체", "편의점", "카페", "마트", "음식점/배달"];
const reportCategoryOptions = ["전체", "편의점", "카페", "마트", "음식점/배달"];
const cardFilters = ["전체", "카페", "편의점", "의류", "배달", "마트", "교통", "기타"];
const communityTabs = ["자유게시판", "질문&답변", "동네 정보", "이벤트"];
const videoFallback = {
  source: "example",
  categories: ["전체", "카드 추천", "혜택 비교", "사용 후기", "비교 분석"],
  popularKeywords: ["카드 추천", "혜택 비교", "연회비", "카드 정리", "소비 패턴"],
  channels: [{ name: "짠돌TV" }, { name: "재테크 연구소" }, { name: "카드의 정석" }, { name: "혜택 연구소" }],
  items: [
    { id: 1, title: "[예제] 2026 혜택 좋은 신용카드 TOP 5", channel: "카드토크", views: "12만", age: "2일 전", duration: "8:21", tags: ["카드추천", "혜택비교"] },
    { id: 2, title: "[예제] 사회초년생 카드 추천 정리", channel: "머니레인", views: "6.4만", age: "5일 전", duration: "10:31", tags: ["체크카드", "초년생"] },
  ],
};

const topCards = [
  { rank: 1, name: "트래블월렛 우리카드", tags: "카페 · 편의점 · 마트", saving: 24500, score: 82.1 },
  { rank: 2, name: "토스뱅크 체크카드", tags: "편의점 · 배달", saving: 20400, score: 80.5 },
  { rank: 3, name: "신한카드 Simple Plan+", tags: "음식점 · 카페", saving: 19600, score: 78.3 },
];

const recommendationCards = ref([
  {
    id: "woori-travel",
    name: "트래블월렛 우리카드",
    issuer: "우리카드",
    type: "신용",
    score: 92,
    saving: 32400,
    number: "4821",
    specialty: "카페 특화형",
    benefits: ["카페 50% 할인 (월 15,000원 한도)", "편의점 10% 할인 (월 10,000원 한도)", "마트 5% 할인"],
  },
  {
    id: "toss-check",
    name: "토스뱅크 체크카드",
    issuer: "토스뱅크",
    type: "체크",
    score: 88,
    saving: 21300,
    number: "3142",
    specialty: "생활 밀착형",
    benefits: ["편의점 캐시백 3%", "카페 캐시백 2%", "연회비 없음"],
  },
  {
    id: "kb-check",
    name: "KB국민 노리2 체크카드",
    issuer: "KB국민카드",
    type: "체크",
    score: 81,
    saving: 18800,
    number: "9017",
    specialty: "교통/생활형",
    benefits: ["대중교통 10% 할인", "편의점 5% 할인", "카페 5% 할인"],
  },
  {
    id: "shinhan-simple",
    name: "신한카드 Simple Plan+",
    issuer: "신한카드",
    type: "신용",
    score: 78,
    saving: 19600,
    number: "7320",
    specialty: "음식점 특화형",
    benefits: ["음식점 10% 할인", "카페 5% 할인", "생활 업종 적립"],
  },
]);

const dashboardCards = [
  { rank: 1, name: "트래블월렛 우리카드", issuer: "우리카드", benefits: "카페·편의점·마트", saving: 2568, score: 69.8 },
  { rank: 2, name: "삼성카드 iD SIMPLE", issuer: "삼성카드", benefits: "마트·편의점", saving: 2430, score: 69.8 },
  { rank: 3, name: "신한카드 Simple Plan+", issuer: "신한카드", benefits: "카페·편의점", saving: 2345, score: 68.2 },
  { rank: 4, name: "DA카드의정석", issuer: "현대카드", benefits: "음식점·온라인", saving: 2384, score: 67.7 },
  { rank: 5, name: "FRESHIE M EDITION2", issuer: "우리카드", benefits: "마트·교통", saving: 3384, score: 67.7 },
];

const gorillaCards = [
  { name: "삼성 iD SELECT ALL 카드", issuer: "삼성카드", type: "신용카드", benefitBadge: "최대 49.4만원 혜택", saving: 494000, color: "#f1f2f4", perks: [["선택 옵션에 따른", "할인 혜택"], ["생활 편의 영역", "5% 할인"], ["디지털콘텐츠/멤버십", "50% 할인"]], fees: "국내전용 20,000원 / 해외겸용 20,000원", condition: "전월실적 40만원 이상", detailBenefits: ["[SELECT 1] 선택 옵션에 따른 할인 혜택 제공", "국내 가맹점 0.7% 할인", "아파트 관리비/통신 10% 할인", "교육 10% 할인", "디지털콘텐츠 멤버십 50% 할인"] },
  { name: "신한카드 Mr.Life", issuer: "신한카드", type: "신용카드", benefitBadge: "최대 57.9만원 혜택", saving: 579000, color: "#f44336", perks: [["공과금", "10% 할인"], ["마트, 편의점", "10% 할인"], ["식음료", "10% 할인"]], fees: "해외겸용 15,000원", condition: "전월실적 30만원 이상", detailBenefits: ["공과금 10% 할인", "편의점/병원/세탁소 10% 할인", "온라인 쇼핑 10% 할인", "대형마트 주말 10% 할인"] },
  { name: "굿데이카드", issuer: "KB국민카드", type: "신용카드", benefitBadge: "최대 86만원 캐시백", saving: 860000, color: "#f97316", perks: [["주유", "60원/L 할인"], ["통신요금", "10% 할인"], ["커피", "10% 할인"]], fees: "국내전용 5,000원 / 해외겸용 10,000원", condition: "전월실적 30만원 이상", detailBenefits: ["주유 리터당 60원 할인", "통신요금 10% 할인", "대중교통 10% 할인", "커피전문점 10% 할인"] },
  { name: "삼성카드 & MILEAGE PLATINUM", issuer: "삼성카드", type: "신용카드", benefitBadge: "최대 117만원 캐시백", saving: 1170000, color: "#111827", perks: [["1,000원당", "1마일 기본적립"], ["국내/해외 택1 옵션형", "1마일 특별적립"], ["인천공항", "라운지 무료이용"]], fees: "국내전용 47,000원 / 해외겸용 49,000원", condition: "전월실적 없음", detailBenefits: ["1,000원당 1마일 기본 적립", "해외/면세점 특별 적립", "인천공항 라운지 무료", "공항 발렛파킹 혜택"] },
  { name: "카드의정석2", issuer: "우리카드", type: "신용카드", benefitBadge: "최대 78만원 혜택", saving: 780000, color: "#2563eb", perks: [["국내외 가맹점", "1.2% 할인"], ["본가별 이용실적 따라", "최대 15,000원 청구할인"], ["생활 영역", "추가 할인"]], fees: "국내전용 22,000원 / 해외겸용 22,000원", condition: "전월실적 50만원 이상", detailBenefits: ["국내외 가맹점 1.2% 할인", "생활 영역 추가 할인", "월 실적별 청구할인", "온라인 결제 혜택"] },
  { name: "KB국민 My WE:SH 카드", issuer: "KB국민카드", type: "신용카드", benefitBadge: "최대 86만원 캐시백", saving: 860000, color: "#c7ead9", perks: [["KB Pay", "10% 할인"], ["음식점", "10% 할인"], ["서비스팩 3개 중", "1개 선택할인"]], fees: "국내전용 15,000원 / 해외겸용 15,000원", condition: "전월실적 40만원 이상", detailBenefits: ["KB Pay 10% 할인", "음식점 10% 할인", "선택 서비스팩 할인", "생활 업종 혜택"] },
  { name: "LOCA LIKIT 2.0", issuer: "롯데카드", type: "신용카드", benefitBadge: "최대 67만원 혜택", saving: 670000, color: "#dbeafe", perks: [["국내 가맹점", "1.2% 할인"], ["해외 가맹점", "2.0% 할인"], ["국내 가맹점", "2~3개월 무이자 할부"]], fees: "국내전용 20,000원 / 해외겸용 20,000원", condition: "전월실적 없음", detailBenefits: ["국내 가맹점 1.2% 할인", "해외 가맹점 2.0% 할인", "무이자 할부", "실적 조건 없음"] },
  { name: "토스뱅크 체크카드", issuer: "토스뱅크", type: "체크카드", benefitBadge: "최대 24만원 혜택", saving: 240000, color: "#10b981", perks: [["편의점", "3% 캐시백"], ["카페", "2% 캐시백"], ["연회비", "없음"]], fees: "연회비 없음", condition: "전월실적 없음", detailBenefits: ["편의점 캐시백", "카페 캐시백", "해외 결제 혜택", "연회비 없음"] },
];

const communityRows = ref([
  { title: "역삼역 근처 맛집 추천부탁해요", author: "직장인", time: "방금", views: 12, likes: 3, budget: "200,000원", open: false },
  { title: "역삼동 근처 카페 같이가기 좋은 곳 있나요?", author: "커피러버", time: "방금", views: 8, likes: 1, budget: "150,000원", open: false },
  { title: "역삼동 vs 신촌 어디가 더 좋을까요?", author: "분석러", time: "15분", views: 2, likes: 1, budget: "180,000원", open: false },
  { title: "이번 달 배달 할인 이벤트 모음", author: "혜택왕", time: "1시간", views: 31, likes: 6, budget: "90,000원", open: false },
  { title: "강남역 점심 할인 잘 되는 카드 있나요?", author: "점심러", time: "2시간", views: 42, likes: 9, budget: "220,000원", open: false },
  { title: "카페 많이 가는 사람 추천 카드 공유", author: "라떼좋아", time: "3시간", views: 56, likes: 14, budget: "170,000원", open: false },
  { title: "편의점 캐시백 카드 실제 체감 후기", author: "편의점러", time: "4시간", views: 73, likes: 18, budget: "130,000원", open: false },
  { title: "마트 장보기 혜택 좋은 조합 알려주세요", author: "장보기왕", time: "5시간", views: 35, likes: 7, budget: "260,000원", open: false },
  { title: "역삼동 헬스장 주변 할인 정보", author: "운동러", time: "6시간", views: 21, likes: 4, budget: "110,000원", open: false },
  { title: "배달비 줄이는 카드 조합 정리", author: "배달마스터", time: "7시간", views: 88, likes: 23, budget: "240,000원", open: false },
  { title: "교통비 할인은 체크카드가 나을까요?", author: "출퇴근러", time: "8시간", views: 48, likes: 10, budget: "95,000원", open: false },
  { title: "신용카드 신규 이벤트 모아봤어요", author: "이벤트헌터", time: "9시간", views: 120, likes: 31, budget: "300,000원", open: false },
  { title: "연회비 낮은 카드 중 괜찮은 것 추천", author: "절약러", time: "10시간", views: 67, likes: 15, budget: "160,000원", open: false },
  { title: "온라인 쇼핑 혜택 좋은 카드 후기", author: "쇼핑러", time: "11시간", views: 94, likes: 20, budget: "280,000원", open: false },
  { title: "술집 많은 동네에서 쓸 카드 추천", author: "모임러", time: "12시간", views: 39, likes: 8, budget: "210,000원", open: false },
  { title: "병원비 할인 가능한 카드 있나요?", author: "건강지킴", time: "13시간", views: 28, likes: 5, budget: "140,000원", open: false },
  { title: "교육비 결제용 카드 비교 부탁", author: "공부중", time: "14시간", views: 33, likes: 6, budget: "320,000원", open: false },
  { title: "주말 데이트 코스와 카드 혜택 공유", author: "데이트러", time: "15시간", views: 77, likes: 17, budget: "250,000원", open: false },
  { title: "카드 혜택 월 한도 계산 어렵네요", author: "초보자", time: "16시간", views: 51, likes: 11, budget: "190,000원", open: false },
  { title: "보유 카드 정리 기준 어떻게 잡나요?", author: "정리왕", time: "17시간", views: 63, likes: 13, budget: "200,000원", open: false },
  { title: "강남구 편의점 밀집 지역 분석 후기", author: "슬세권러", time: "18시간", views: 84, likes: 22, budget: "155,000원", open: false },
  { title: "카드 3장 조합으로 혜택 극대화하기", author: "조합러", time: "19시간", views: 102, likes: 27, budget: "360,000원", open: false },
  { title: "이번 달 소비 패턴이 바뀌었어요", author: "변화중", time: "20시간", views: 45, likes: 9, budget: "175,000원", open: false },
  { title: "카페/편의점 둘 다 잡는 카드 추천", author: "동네러", time: "21시간", views: 69, likes: 16, budget: "230,000원", open: false },
  { title: "현금보다 카드 혜택이 큰 구간은?", author: "계산러", time: "22시간", views: 58, likes: 12, budget: "205,000원", open: false },
  { title: "카드 추천 리포트 써본 후기", author: "사용자", time: "23시간", views: 91, likes: 25, budget: "185,000원", open: false },
]);

const active = ref("home");
const selectedCategory = ref("전체");
const selectedReportCategory = ref("전체");
const showReportPopularCards = ref(false);
const selectedCardFilter = ref("전체");
const selectedCommunityTab = ref("자유게시판");
const communityPage = ref(1);
const communityPageSize = 10;
const selectedCommunityPostId = ref(null);
const editingCommunityPost = ref(false);
const editPost = ref({ title: "", content: "", budget: "", tab: "자유게시판" });
const videos = ref(videoFallback);
const videoQuery = ref("");
const videoCategory = ref("전체");
const kakaoReady = ref(false);
const kakaoMapEl = ref(null);
const receiptUploadEl = ref(null);
const monthlyChartEl = ref(null);
const donutChartEl = ref(null);
const hoveredCardId = ref("");
const drawerCard = ref(null);
const favoriteCards = ref([]);
const FAVORITE_STORAGE_PREFIX = "seulpick.favoriteCards";
const selectedPoint = ref({ lat: 37.5007, lng: 127.0365 });
const addressSearchQuery = ref("강남구 역삼동");
const nearbyPlaceCount = ref(0);
const currentAreaId = ref("");
const recommendationMeta = ref({});
const areaPopularityRanking = ref([]);
const activeReportIndex = ref({ credit: 0, check: 0 });
const activeOwnedCardIndex = ref(0);
const radius = ref(500);
const mapRecalcTick = ref(0);
const recalculating = ref(false);
const uploadProgress = ref(0);
const uploadState = ref("대기");
const selectedPeriod = ref("6개월");
const commandOpen = ref(false);
const globalSearchQuery = ref("");
const authUser = ref(null);
const authError = ref("");
const loginOpen = ref(false);
const loginMode = ref("login");
const authForm = ref({ username: "seulpick", name: "김슬픽", email: "seulpick@example.com", password: "seulpick123" });
const profileEditing = ref(false);
const profileForm = ref({ name: "", email: "", password: "" });
const newPost = ref({ title: "", content: "", budget: "200,000원", tab: "자유게시판" });
const commentDrafts = ref({});
let kakaoMap;
let kakaoCircle;
let kakaoMarker;
let kakaoPlaceOverlays = [];
let monthlyChart;
let donutChart;

const spendTotal = computed(() => spendRows.value.reduce((sum, row) => sum + Number(row.amount || 0), 0));
const isAuthenticated = computed(() => Boolean(authUser.value));
const currentUserId = computed(() => authUser.value?.id || null);
const ownedCardSet = computed(() => new Set(userProfile.value.ownedCards || []));
const liveBoost = computed(() => Math.max(0, Math.round((Number(radius.value) - 500) / 80)) + mapRecalcTick.value);
const liveCards = computed(() =>
  recommendationCards.value.map((card) => {
    const hoverBoost = hoveredCardId.value === card.id ? 3 : 0;
    return {
      ...card,
      liveScore: Math.min(99, card.score + liveBoost.value + hoverBoost),
      liveSaving: card.saving + liveBoost.value * 450 + hoverBoost * 600,
    };
  })
);
const creditCards = computed(() => liveCards.value.filter((card) => card.type === "신용"));
const checkCards = computed(() => liveCards.value.filter((card) => card.type === "체크"));
const recommendationCreditCards = computed(() => recommendationCards.value.filter((card) => card.type === "신용"));
const recommendationCheckCards = computed(() => recommendationCards.value.filter((card) => card.type === "체크"));
const categoryKeywords = computed(() => {
  const selected = selectedReportCategory.value;
  if (selected === "전체") return [];
  if (selected === "음식점/배달") return ["음식점", "배달"];
  if (selected === "의류/소품") return ["의류", "소품"];
  return [selected];
});
const cardCategoryScore = (card) => {
  if (!categoryKeywords.value.length) return 0;
  const haystack = [card.specialty, ...(card.benefits || [])].join(" ");
  return categoryKeywords.value.reduce((score, keyword) => score + (haystack.includes(keyword) ? 1 : 0), 0);
};
const prioritizeByReportCategory = (cards) =>
  [...cards].sort((a, b) => {
    const categoryDiff = cardCategoryScore(b) - cardCategoryScore(a);
    if (categoryDiff) return categoryDiff;
    return b.score - a.score;
  });
const reportGroups = computed(() => [
  {
    id: "credit",
    label: "신용카드 TOP 3",
    title: `${selectedReportCategory.value}에서 가장 맞는 신용카드`,
    badge: "신용카드",
    cards: recommendationCreditCards.value,
    accent: "cream",
  },
  {
    id: "check",
    label: "체크카드 TOP 3",
    title: `${selectedReportCategory.value}에서 가장 맞는 체크카드`,
    badge: "체크카드",
    cards: recommendationCheckCards.value,
    accent: "green",
  },
]);
const rankedDashboardCards = computed(() =>
  dashboardCards
    .map((card) => ({ ...card, liveScore: Number((card.score + liveBoost.value * 0.4 + (hoveredCardId.value === card.name ? 1.8 : 0)).toFixed(1)) }))
    .sort((a, b) => b.liveScore - a.liveScore)
);
const behaviorHashtags = computed(() => {
  const tags = ["#유사소비자"];
  const categoryCounts = {};
  liveCards.value.forEach((card) => {
    const categories = card.raw?.graph_matched_categories || [];
    categories.forEach((category) => {
      categoryCounts[category] = (categoryCounts[category] || 0) + 1;
    });
  });
  const labels = {
    cafe: "#카페",
    convenience: "#편의점",
    dining: "#외식",
    delivery: "#배달",
    mart: "#마트",
    shopping: "#쇼핑",
  };
  Object.entries(categoryCounts)
    .sort(([, left], [, right]) => right - left)
    .slice(0, 3)
    .forEach(([category]) => {
      if (labels[category]) tags.push(labels[category]);
    });
  if (tags.length === 1) tags.push("#카페", "#외식");
  return tags;
});
const behaviorRecommendedCard = computed(() => liveCards.value[0] || null);
const similarUserInsight = computed(() => {
  const card = behaviorRecommendedCard.value;
  const baseSaving = Number(card?.liveSaving || card?.saving || 0);
  const baseScore = Number(card?.liveScore || card?.score || 0);
  const topPercent = Math.max(3, Math.min(18, Math.round(22 - baseScore / 6)));
  const averageSpend = Math.max(120000, Math.round((baseSaving * 8 + 180000) / 10000) * 10000);
  return { topPercent, averageSpend };
});
const favoriteCardSet = computed(() => new Set(favoriteCards.value.map((card) => card.name)));
const graphCategoryLabels = {
  cafe: "카페",
  convenience: "편의점",
  dining: "외식",
  delivery: "배달",
  mart: "마트",
  shopping: "쇼핑",
  transport: "교통",
  medical: "병원",
  education: "교육",
};
const graphCategoryLabel = (category) => graphCategoryLabels[category] || category || "지역 업종";
const areaBenefitInsights = computed(() => {
  const counts = {};
  const shares = {};
  liveCards.value.forEach((card) => {
    Object.entries(card.raw?.graph_category_store_counts || {}).forEach(([category, count]) => {
      counts[category] = Math.max(counts[category] || 0, Number(count || 0));
    });
    Object.entries(card.raw?.graph_category_shares || {}).forEach(([category, share]) => {
      shares[category] = Math.max(shares[category] || 0, Number(share || 0));
    });
    (card.graph_matched_categories || []).forEach((category) => {
      counts[category] = counts[category] || 1;
    });
  });
  return Object.entries(counts)
    .map(([category, count]) => ({
      category,
      label: graphCategoryLabel(category),
      count,
      share: shares[category] || 0,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
});
const regionalPopularCards = computed(() =>
  areaPopularityRanking.value
    .filter((item) => Number(item.local_popularity_score || 0) > 0)
    .map((item) => {
      const card = liveCards.value.find((candidate) => Number(candidate.id) === Number(item.card_id));
      return card ? { ...card, local_popularity: item } : null;
    })
    .filter(Boolean)
    .slice(0, 5)
);
const reportPopularCards = computed(() =>
  (regionalPopularCards.value.length ? regionalPopularCards.value : liveCards.value).slice(0, 3)
);
const favoriteCardsForProfile = computed(() => favoriteCards.value);
const drawerDetailInfo = computed(() => {
  const card = drawerCard.value || {};
  const raw = card.raw || {};
  const rawBenefits = raw.benefits || raw.detail_benefits || raw.detailBenefits || raw.benefit_summary || raw.summary_benefits;
  const detailBenefits = [
    ...normalizeTextList(card.detailBenefits),
    ...normalizeTextList(card.benefits),
    ...normalizeTextList(rawBenefits),
  ];
  const perkBenefits = normalizePerkList(card.perks);
  const annualFee =
    card.fees ||
    card.annual_fee ||
    card.annualFee ||
    raw.fees ||
    raw.annual_fee ||
    raw.annualFee ||
    raw.domestic_annual_fee ||
    "연회비 정보 확인 필요";
  const condition =
    card.condition ||
    card.previous_month_spending ||
    card.required_spend ||
    raw.condition ||
    raw.previous_month_spending ||
    raw.required_spend ||
    raw.minimum_spend ||
    "전월실적 조건 확인 필요";
  return {
    annualFee,
    condition,
    benefits: detailBenefits.length ? detailBenefits : perkBenefits,
    perks: perkBenefits,
  };
});
function normalizeTextList(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .flatMap((item) => normalizeTextList(item))
      .filter(Boolean);
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => [key, item].filter(Boolean).join(": "))
      .filter(Boolean);
  }
  return String(value)
    .split(/\n|·|\|/)
    .map((item) => item.trim())
    .filter(Boolean);
}
function normalizePerkList(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map((perk) => {
      if (Array.isArray(perk)) return perk.filter(Boolean).join(" ");
      if (typeof perk === "object") return Object.values(perk).filter(Boolean).join(" ");
      return String(perk || "");
    })
    .map((item) => item.trim())
    .filter(Boolean);
}
function cardMatchedCategoryText(card) {
  const categories = card.graph_matched_categories || card.raw?.graph_matched_categories || [];
  return categories.map(graphCategoryLabel).slice(0, 3).join(", ") || graphCategoryLabel(card.graph_top_category);
}
function locationReasonForCard(card) {
  const matched = cardMatchedCategoryText(card);
  const graphScore = Number(card.graph_rerank_score || 0);
  const saving = currency(card.saving || card.liveSaving || 0);
  const popularity = card.local_popularity;
  if (!currentAreaId.value) return "추천 결과를 확정하면 이 지역에서 추천된 이유가 표시됩니다.";
  if (popularity) {
    return `${matched} 업종과 맞고, 이 지역 행동점수 ${popularity.event_score}점에 카테고리 적합도 ${popularity.category_fit}를 반영해 지역 인기점수 ${popularity.local_popularity_score}점으로 산출되었습니다.`;
  }
  return `${matched} 업종과 카드 혜택이 겹치고, Graph 점수 ${graphScore || "-"}점과 월 ${saving}원 예상 혜택이 함께 반영되었습니다.`;
}
function recommendationReasonForCard(card) {
  const matched = cardMatchedCategoryText(card);
  const saving = currency(card.saving || card.liveSaving || 0);
  const score = card.score || card.ranking_score || card.liveScore || 0;
  const source = card.local_popularity
    ? `지역 행동점수 ${card.local_popularity.event_score || 0}점`
    : `Seul-Score ${score}점`;
  return `${matched} 소비/상권과 카드 혜택이 맞고, ${source} 및 월 ${saving} 예상 혜택을 기준으로 추천되었습니다.`;
}

function buildPopularityCardsPayload(cards) {
  return cards
    .filter((card) => Number.isInteger(Number(card.id)))
    .map((card) => ({
      card_id: Number(card.id),
      graph_matched_categories: card.graph_matched_categories || card.raw?.graph_matched_categories || [],
      graph_category_shares: card.raw?.graph_category_shares || {},
      graph_rerank_score: card.graph_rerank_score || 0,
      seul_score: card.score || 0,
    }));
}
const toRankingDashboardCard = (card, index) => ({
  ...card,
  type: card.type === "체크" || card.type === "체크카드" ? "체크카드" : "신용카드",
  benefitBadge: `월 ${currency(card.saving || 0)}원 예상 혜택`,
  color: card.type === "체크" || card.type === "체크카드" ? "#10b981" : "#111827",
  perks: (card.benefits || card.detailBenefits || ["소비 패턴 기반 추천"])
    .slice(0, 3)
    .map((benefit) => {
      const [label, value] = String(benefit).split(":");
      return [label || `추천 ${index + 1}`, value?.trim() || "혜택 반영"];
    }),
  fees: card.issuer || "추천 카드",
  condition: card.specialty || "현재 지역/소비 패턴 기준",
  saving: card.saving || 0,
});
const recommendationDashboardCards = computed(() => {
  if (!currentAreaId.value) return [];
  return recommendationCards.value.map(toRankingDashboardCard);
});
const filteredGorillaCards = computed(() => {
  const type = selectedCardFilter.value;
  if (recommendationDashboardCards.value.length) {
    const ranked = [...recommendationDashboardCards.value].sort((a, b) => (b.score || 0) - (a.score || 0));
    if (type === "신용카드" || type === "체크카드") {
      return ranked.filter((card) => card.type === type).slice(0, 8);
    }
    const credit = ranked.filter((card) => card.type === "신용카드").slice(0, 8);
    const check = ranked.filter((card) => card.type === "체크카드").slice(0, 8);
    return [...credit, ...check];
  }
  if (type === "신용카드" || type === "체크카드") {
    return gorillaCards.filter((card) => card.type === type);
  }
  return gorillaCards;
});
const ownedCardsForProfile = computed(() =>
  (userProfile.value.ownedCards || []).map((name) => {
    const matched = [...liveCards.value, ...dashboardCards, ...topCards].find((card) => card.name === name);
    return matched || { name, issuer: "등록 카드", type: "보유", score: 0, saving: 0, benefits: "사용자 등록 카드" };
  })
);
const activeOwnedCard = computed(() => ownedCardsForProfile.value[activeOwnedCardIndex.value] || ownedCardsForProfile.value[0]);
const communityTotalPages = computed(() => Math.max(1, Math.ceil(communityRows.value.length / communityPageSize)));
const paginatedCommunityRows = computed(() => {
  const start = (communityPage.value - 1) * communityPageSize;
  return communityRows.value.slice(start, start + communityPageSize);
});
const selectedCommunityPost = computed(() => communityRows.value.find((row) => row.id === selectedCommunityPostId.value));
const canEditSelectedPost = computed(
  () =>
    Boolean(
      selectedCommunityPost.value &&
        authUser.value &&
        (selectedCommunityPost.value.authorUsername === authUser.value.username ||
          (!selectedCommunityPost.value.authorUsername && selectedCommunityPost.value.author === authUser.value.name))
    )
);
const searchResults = computed(() => {
  const query = globalSearchQuery.value.trim().toLowerCase();
  if (!query) {
    return pages.map((page) => ({
      type: "페이지",
      title: page.label,
      description: `${page.label} 페이지로 이동`,
      page: page.id,
    }));
  }

  const pageIndex = [
    { page: "home", title: "대시보드", keywords: ["홈", "home", "대시보드", "혜택", "인기", "이벤트"] },
    { page: "map", title: "슬세권 분석", keywords: ["지도", "map", "슬세권", "상권", "지역", "소비", "분석", "ai"] },
    { page: "cards", title: "카드 대시보드", keywords: ["카드", "추천", "대시보드", "랭킹", "신용", "체크", "혜택"] },
    { page: "videos", title: "유튜브 검색", keywords: ["유튜브", "youtube", "영상", "검색", "카드 추천"] },
    { page: "community", title: "커뮤니티", keywords: ["커뮤니티", "게시글", "글쓰기", "댓글", "후기", "질문"] },
    { page: "profile", title: "프로필", keywords: ["프로필", "내 정보", "보유 카드", "차트", "소비 데이터"] },
  ];
  const results = [];

  pageIndex.forEach((item) => {
    const haystack = [item.title, ...item.keywords].join(" ").toLowerCase();
    if (haystack.includes(query)) {
      results.push({ type: "페이지", title: item.title, description: "관련 페이지로 이동", page: item.page });
    }
  });

  [...liveCards.value, ...topCards, ...dashboardCards, ...gorillaCards].forEach((card) => {
    const haystack = [card.name, card.issuer, card.type, card.specialty, card.benefits, card.benefitBadge]
      .flat()
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (haystack.includes(query)) {
      results.push({ type: "카드", title: card.name, description: "카드 대시보드에서 확인", page: "cards", card });
    }
  });

  communityRows.value.forEach((post) => {
    const haystack = [post.title, post.content, post.author, post.tab].filter(Boolean).join(" ").toLowerCase();
    if (haystack.includes(query)) {
      results.push({ type: "게시글", title: post.title, description: `${post.author} · 커뮤니티 게시글`, page: "communityPost", post });
    }
  });

  return results.slice(0, 8);
});

function currency(value) {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value || 0));
}

function isOwned(cardName) {
  return ownedCardSet.value.has(cardName);
}

function navigate(pageId) {
  active.value = pageId;
  commandOpen.value = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openSearchResult(result) {
  if (!result) return;
  if (result.post) {
    selectedCommunityPostId.value = result.post.id;
    navigate("communityPost");
  } else {
    navigate(result.page);
    if (result.card) openDrawer(result.card);
  }
  globalSearchQuery.value = "";
}

function normalizeCardType(cardType) {
  const value = String(cardType || "").toLowerCase();
  if (["debit", "check", "check_card", "체크", "체크카드"].includes(value)) return "체크";
  return "신용";
}

function backendReportCategory(category) {
  const mapping = {
    전체: null,
    편의점: "convenience",
    카페: "cafe",
    마트: "mart",
    "음식점/배달": "dining",
  };
  return mapping[category] ?? null;
}

function normalizeRecommendationCard(card, index) {
  return {
    id: card.id,
    name: card.name,
    issuer: card.issuer,
    type: normalizeCardType(card.card_type || card.type),
    score: Number(card.seul_score || card.ranking_score || 0),
    saving: Number(card.estimated_net_value || card.estimated_savings || 0),
    liveScore: Number(card.seul_score || card.ranking_score || 0),
    liveSaving: Number(card.estimated_net_value || card.estimated_savings || 0),
    number: String(card.id || index + 1).padStart(4, "0").slice(-4),
    specialty: (card.focus || []).join(" · ") || card.graph_top_category || "추천 카드",
    benefits: (card.calculation_breakdown || [])
      .slice(0, 3)
      .map((item) => `${item.category_label || item.category}: ${currency(item.final_benefit || 0)}원`),
    detailBenefits: (card.calculation_breakdown || [])
      .slice(0, 5)
      .map((item) => `${item.category_label || item.category} 예상 혜택 ${currency(item.final_benefit || 0)}원`),
    graph_rerank_score: card.graph_rerank_score,
    graph_top_category: card.graph_top_category,
    graph_matched_categories: card.graph_matched_categories || [],
    ranking_mode: card.ranking_mode,
    ranking_score: Number(card.ranking_score || card.seul_score || 0),
    ranking_components: card.ranking_components || {},
    estimated_gross_benefit: card.estimated_gross_benefit,
    estimated_net_value: card.estimated_net_value,
    application_url: card.application_url || card.apply_url || card.source_url,
    raw: card,
  };
}

function mapBackendSpending(spending = {}) {
  const labels = {
    cafe: "카페",
    convenience: "편의점",
    dining: "외식",
    delivery: "배달",
    mart: "마트",
    shopping: "쇼핑",
    etc: "기타",
  };
  const rows = Object.entries(spending)
    .filter(([key]) => key !== "food")
    .map(([key, amount]) => ({
      name: labels[key] || key,
      amount: Number(amount || 0),
      ratio: 0,
    }));
  const total = rows.reduce((sum, row) => sum + row.amount, 0);
  return rows.map((row) => ({
    ...row,
    ratio: total ? Math.round((row.amount / total) * 100) : 0,
  }));
}

async function recordCardEvent(card, eventType, metadata = {}) {
  const cardId = card?.raw?.id || card?.id;
  if (!Number.isInteger(Number(cardId)) || !currentUserId.value) return;
  try {
    const result = await api.cardEvent({
      user_id: currentUserId.value,
      card_id: cardId,
      area_id: currentAreaId.value,
      event_type: eventType,
      metadata,
    });
    console.log("[CardEvent sync]", {
      event_type: eventType,
      card_id: cardId,
      event_status: result.event_status,
      graph_sync_status: result.graph_sync_status,
    });
  } catch (error) {
    console.warn("[CardEvent sync failed]", error.message);
  }
}

async function triggerRecalculation(category = selectedReportCategory.value) {
  const requestedCategory = typeof category === "string" ? category : selectedReportCategory.value;
  if (!requireLogin()) return;
  recalculating.value = true;
  mapRecalcTick.value += 1;
  try {
    const mapSummary = await api.mapSummary({
      lat: selectedPoint.value.lat,
      lng: selectedPoint.value.lng,
      radius: Number(radius.value),
    });
    currentAreaId.value = mapSummary.area_id || currentAreaId.value;
    const selectedBackendCategory = backendReportCategory(requestedCategory);
    const result = await api.simulateCards({
      user_id: currentUserId.value,
      area_id: currentAreaId.value,
      lat: selectedPoint.value.lat,
      lng: selectedPoint.value.lng,
      radius: Number(radius.value),
      sync_area: true,
      selected_category: selectedBackendCategory,
      infrastructure: mapSummary.infrastructure || [],
    });
    recommendationMeta.value = result;
    if (Array.isArray(result.card_ranking_list) && result.card_ranking_list.length) {
      recommendationCards.value = result.card_ranking_list.map(normalizeRecommendationCard);
    }
    const popularityCards = buildPopularityCardsPayload(recommendationCards.value);
    if (currentAreaId.value && popularityCards.length) {
      const popularity = await api.areaCardPopularity({
        area_id: currentAreaId.value,
        cards: popularityCards,
      });
      areaPopularityRanking.value = popularity.ranking || [];
    } else {
      areaPopularityRanking.value = [];
    }
    if (result.spending) {
      spendRows.value = mapBackendSpending(result.spending);
    }
    console.log("[GraphDB recommendation check]", {
      area_id: result.area_id,
      area_sync_status: result.area_sync_status,
      recommendation_source: result.recommendation_source,
      graph_status: result.graph_status,
      selected_category: result.selected_category,
      ranking_mode: result.best_card?.ranking_mode,
      graph_rerank_score: result.best_card?.graph_rerank_score,
      user_graph_status: result.user_graph_status,
    });
  } catch (error) {
    console.warn("[Recommendation sync failed]", error.message);
  } finally {
    recalculating.value = false;
  }
}

function syncSelectedMapPoint(position, options = {}) {
  if (!position) return;
  const lat = typeof position.getLat === "function" ? position.getLat() : position.lat;
  const lng = typeof position.getLng === "function" ? position.getLng() : position.lng;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
  selectedPoint.value = { lat, lng };
  if (!window.kakao?.maps) return;
  const kakaoPosition = position.getLat ? position : new window.kakao.maps.LatLng(lat, lng);
  kakaoMarker?.setPosition(kakaoPosition);
  kakaoCircle?.setOptions({ center: kakaoPosition, radius: Number(radius.value) });
  if (options.pan) kakaoMap?.panTo(kakaoPosition);
  updateNearbyPlaces();
  console.log("[Map selection changed]", {
    lat: Number(lat.toFixed(6)),
    lng: Number(lng.toFixed(6)),
    radius: Number(radius.value),
  });
}

function selectMapCategory(category) {
  selectedCategory.value = category;
  updateNearbyPlaces();
}

function clearNearbyPlaces() {
  kakaoPlaceOverlays.forEach((overlay) => overlay.setMap(null));
  kakaoPlaceOverlays = [];
  nearbyPlaceCount.value = 0;
}

function mapCategoryKeyword(category) {
  const keywords = {
    편의점: ["편의점"],
    카페: ["카페"],
    마트: ["마트"],
    "음식점/배달": ["음식점", "배달"],
  };
  return keywords[category] || [category];
}

function mapPlaceCategoryClass(category) {
  const classes = {
    편의점: "convenience",
    카페: "cafe",
    마트: "mart",
    "음식점/배달": "dining",
  };
  return classes[category] || "all";
}

function renderNearbyPlaces(places = []) {
  clearNearbyPlaces();
  if (!kakaoMap || !window.kakao?.maps) return;
  const limitedPlaces = places.slice(0, 18);
  nearbyPlaceCount.value = limitedPlaces.length;
  kakaoPlaceOverlays = limitedPlaces.map((place, index) => {
    const position = new window.kakao.maps.LatLng(Number(place.y), Number(place.x));
    const markerCategory = place.markerCategory || selectedCategory.value;
    const label = markerCategory === "음식점/배달" ? "식" : markerCategory.slice(0, 1);
    const markerClass = mapPlaceCategoryClass(markerCategory);
    return new window.kakao.maps.CustomOverlay({
      map: kakaoMap,
      position,
      yAnchor: 1,
      content: `<button class="place-overlay ${markerClass}" type="button">${label}</button>`,
      zIndex: 20 + index,
    });
  });
}

function uniquePlaces(places = []) {
  return Array.from(new Map(places.map((place) => [place.id || `${place.x}-${place.y}-${place.place_name}`, place])).values());
}

function allocatePlacesByCategory(resultsByCategory, limit = 18) {
  const buckets = resultsByCategory
    .map(({ category, places }) => ({ category, places: uniquePlaces(places) }))
    .filter((bucket) => bucket.places.length > 0);
  const total = buckets.reduce((sum, bucket) => sum + bucket.places.length, 0);
  if (!total) return [];

  const allocations = buckets.map((bucket) => {
    const exact = (bucket.places.length / total) * limit;
    return {
      ...bucket,
      exact,
      count: Math.min(bucket.places.length, Math.max(1, Math.floor(exact))),
    };
  });

  let assigned = allocations.reduce((sum, bucket) => sum + bucket.count, 0);
  while (assigned > limit) {
    const target = allocations
      .filter((bucket) => bucket.count > 1)
      .sort((a, b) => (a.count - a.exact) - (b.count - b.exact))[0];
    if (!target) break;
    target.count -= 1;
    assigned -= 1;
  }

  while (assigned < limit) {
    const target = allocations
      .filter((bucket) => bucket.count < bucket.places.length)
      .sort((a, b) => (b.exact - b.count) - (a.exact - a.count))[0];
    if (!target) break;
    target.count += 1;
    assigned += 1;
  }

  return uniquePlaces(allocations.flatMap((bucket) => bucket.places.slice(0, bucket.count))).slice(0, limit);
}

function updateNearbyPlaces() {
  if (!kakaoMap || !window.kakao?.maps?.services) return;
  const places = new window.kakao.maps.services.Places(kakaoMap);
  const center = new window.kakao.maps.LatLng(selectedPoint.value.lat, selectedPoint.value.lng);
  const categories = selectedCategory.value === "전체" ? ["편의점", "카페", "마트", "음식점/배달"] : [selectedCategory.value];
  const options = {
    location: center,
    radius: Number(radius.value),
    sort: window.kakao.maps.services.SortBy.DISTANCE,
  };
  Promise.all(
    categories.map(
      (category) =>
        Promise.all(
          mapCategoryKeyword(category).map(
            (keyword) =>
              new Promise((resolve) => {
                places.keywordSearch(
                  keyword,
                  (data, status) => {
                    if (status !== window.kakao.maps.services.Status.OK) {
                      resolve([]);
                      return;
                    }
                    resolve(data.map((place) => ({ ...place, markerCategory: category })));
                  },
                  options
                );
              })
          )
        ).then((keywordResults) => keywordResults.flat())
    )
  ).then((results) => {
    const resultsByCategory = categories.map((category, index) => ({
      category,
      places: results[index] || [],
    }));
    const visiblePlaces =
      selectedCategory.value === "전체"
        ? allocatePlacesByCategory(resultsByCategory, 18)
        : uniquePlaces(results.flat()).slice(0, 18);
    renderNearbyPlaces(visiblePlaces);
  });
}

function searchAddress() {
  const query = addressSearchQuery.value.trim();
  if (!query || !window.kakao?.maps?.services) return;
  const geocoder = new window.kakao.maps.services.Geocoder();
  geocoder.addressSearch(query, (addressResults, addressStatus) => {
    if (addressStatus === window.kakao.maps.services.Status.OK && addressResults[0]) {
      syncSelectedMapPoint({ lat: Number(addressResults[0].y), lng: Number(addressResults[0].x) }, { pan: true });
      return;
    }
    const places = new window.kakao.maps.services.Places(kakaoMap);
    places.keywordSearch(query, (placeResults, placeStatus) => {
      if (placeStatus === window.kakao.maps.services.Status.OK && placeResults[0]) {
        syncSelectedMapPoint({ lat: Number(placeResults[0].y), lng: Number(placeResults[0].x) }, { pan: true });
      }
    });
  });
}

function openDrawer(card) {
  drawerCard.value = card;
  recordCardEvent(card, "clicked", {
    source: "card_drawer",
    area_id: currentAreaId.value,
  });
}

function getCardApplicationUrl(card) {
  return card?.application_url || card?.apply_url || card?.source_url || card?.url || card?.raw?.application_url || card?.raw?.apply_url || card?.raw?.source_url || "";
}

async function applyForCard(card) {
  await recordCardEvent(card, "applied_for", {
    source: "card_drawer_apply",
    area_id: currentAreaId.value,
  });
  const url = getCardApplicationUrl(card);
  if (url) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  console.warn("[Card apply] application URL is missing", {
    card_id: card?.raw?.id || card?.id,
    name: card?.name,
  });
}

function toggleFavorite(card) {
  const index = favoriteCards.value.findIndex((item) => item.name === card.name);
  if (index >= 0) {
    favoriteCards.value.splice(index, 1);
    return;
  }
  favoriteCards.value.push(toFavoriteCard(card));
}

function isFavorite(card) {
  return favoriteCardSet.value.has(card?.name);
}

function favoriteStorageKey() {
  return `${FAVORITE_STORAGE_PREFIX}:${currentUserId.value || "guest"}`;
}

function toFavoriteCard(card) {
  return {
    id: card.id,
    name: card.name,
    issuer: card.issuer,
    type: card.type,
    score: card.score,
    liveScore: card.liveScore,
    saving: card.saving,
    liveSaving: card.liveSaving,
    specialty: card.specialty,
    benefitBadge: card.benefitBadge,
    benefits: card.benefits,
    detailBenefits: card.detailBenefits,
    perks: card.perks,
    fees: card.fees,
    condition: card.condition,
    color: card.color,
    graph_matched_categories: card.graph_matched_categories,
    graph_rerank_score: card.graph_rerank_score,
    graph_top_category: card.graph_top_category,
    local_popularity: card.local_popularity,
  };
}

function loadFavoriteCards() {
  try {
    const stored = window.localStorage.getItem(favoriteStorageKey());
    favoriteCards.value = stored ? JSON.parse(stored) : [];
  } catch {
    favoriteCards.value = [];
  }
}

function saveFavoriteCards() {
  try {
    window.localStorage.setItem(
      favoriteStorageKey(),
      JSON.stringify(favoriteCards.value.map(toFavoriteCard))
    );
  } catch (error) {
    console.warn("[Favorites] failed to persist", error);
  }
}

function visibleReportCards(group) {
  if (!group.cards.length) return [];
  const cards = reportCarouselCards(group);
  const index = reportCarouselIndex(group);
  return cards[index] ? [cards[index]] : [];
}

function reportCarouselCards(group) {
  return group.cards.slice(0, 3);
}

function reportCarouselIndex(group) {
  const count = reportCarouselCards(group).length;
  if (!count) return 0;
  return activeReportIndex.value[group.id] % count;
}

function moveReportCard(group, direction) {
  if (!group.cards.length) return;
  const topCount = reportCarouselCards(group).length;
  if (!topCount) return;
  const nextIndex = activeReportIndex.value[group.id] + direction + topCount;
  activeReportIndex.value[group.id] = nextIndex % topCount;
}

function selectReportCard(group, index) {
  activeReportIndex.value[group.id] = index;
}

function moveOwnedCard(direction) {
  const count = ownedCardsForProfile.value.length;
  if (count <= 1) return;
  activeOwnedCardIndex.value = (activeOwnedCardIndex.value + direction + count) % count;
}

function moveCommunityPage(page) {
  communityPage.value = Math.min(Math.max(page, 1), communityTotalPages.value);
}

function openCommunityPost(row) {
  selectedCommunityPostId.value = row.id;
  editingCommunityPost.value = false;
  navigate("communityPost");
}

function startEditPost() {
  if (!selectedCommunityPost.value) return;
  editPost.value = {
    title: selectedCommunityPost.value.title || "",
    content: selectedCommunityPost.value.content || "",
    budget: selectedCommunityPost.value.budget || "",
    tab: selectedCommunityPost.value.tab || selectedCommunityTab.value,
  };
  editingCommunityPost.value = true;
}

function cancelEditPost() {
  editingCommunityPost.value = false;
}

async function selectReportCategory(category) {
  selectedReportCategory.value = category;
  showReportPopularCards.value = false;
  activeReportIndex.value = { credit: 0, check: 0 };
  await triggerRecalculation(category);
}

function selectReportPopularCards() {
  showReportPopularCards.value = true;
}

async function runUploadFlow() {
  if (!requireLogin()) return;
  await nextTick();
  receiptUploadEl.value?.click();
}

async function handleReceiptUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadState.value = "분석 중";
  uploadProgress.value = 20;
  try {
    const parsed = await api.parseImage(file);
    uploadProgress.value = 65;
    await api.saveUploadedReport({
      user_id: currentUserId.value,
      file_url: `local-vlm-upload://user-${currentUserId.value}/${encodeURIComponent(file.name)}`,
      file_type: file.type || "application/octet-stream",
      parse_status: "normalized",
      parsed_payload: parsed,
    });
    uploadProgress.value = 90;
    if (parsed.spending) {
      spendRows.value = mapBackendSpending(parsed.spending);
    }
    uploadState.value = "자동 입력 완료";
    await triggerRecalculation();
    uploadProgress.value = 100;
    console.log("[VLM upload saved]", {
      user_id: currentUserId.value,
      source: parsed.source,
      vlm_status: parsed.vlm_status,
      vlm_error_type: parsed.vlm_error_type,
      vlm_error: parsed.vlm_error || parsed.fallback_reason,
      vlm_request_debug: parsed.vlm_request_debug,
      categories: Object.keys(parsed.spending || {}),
    });
  } catch (error) {
    uploadState.value = "분석 실패";
    console.warn("[VLM upload failed]", error.message);
  } finally {
    event.target.value = "";
  }
}

function stars(score) {
  const filled = Math.max(1, Math.round(score / 20));
  return "★★★★★".slice(0, filled) + "☆☆☆☆☆".slice(0, 5 - filled);
}

async function loadConfigAndProfile() {
  const config = await api.config();
  if (config.kakaoMapApiKey) {
    await loadKakaoMap(config.kakaoMapApiKey);
  }
}

async function loadAuth() {
  const data = await api.authStatus();
  authUser.value = data.authenticated ? data.profile : null;
  if (data.profile) {
    userProfile.value = { ...userProfile.value, ...data.profile };
  }
  loadFavoriteCards();
  profileForm.value = { name: userProfile.value.name, email: userProfile.value.email, password: "" };
}

async function submitAuth() {
  authError.value = "";
  try {
    const payload = { ...authForm.value };
    const data = loginMode.value === "login" ? await api.login(payload) : await api.register(payload);
    authUser.value = data.profile;
    userProfile.value = { ...userProfile.value, ...data.profile };
    profileForm.value = { name: userProfile.value.name, email: userProfile.value.email, password: "" };
    loginOpen.value = false;
  } catch (error) {
    authError.value = error.message;
  }
}

async function logout() {
  await api.logout();
  authUser.value = null;
  await loadAuth();
}

function requireLogin() {
  if (isAuthenticated.value) return true;
  loginOpen.value = true;
  authError.value = "로그인이 필요한 기능입니다.";
  return false;
}

async function saveProfile() {
  if (!requireLogin()) return;
  const data = await api.updateProfile(profileForm.value);
  userProfile.value = { ...userProfile.value, ...data.profile };
  authUser.value = data.profile;
  profileForm.value.password = "";
  profileEditing.value = false;
}

async function loadCommunityPosts() {
  const data = await api.communityPosts();
  communityRows.value = data.items;
  if (communityPage.value > communityTotalPages.value) {
    communityPage.value = communityTotalPages.value;
  }
}

async function createPost() {
  if (!requireLogin()) return;
  const data = await api.createPost(newPost.value);
  communityRows.value = data.items;
  communityPage.value = 1;
  navigate("community");
  newPost.value = { title: "", content: "", budget: "200,000원", tab: selectedCommunityTab.value };
}

async function createComment(row) {
  if (!requireLogin()) return;
  const text = (commentDrafts.value[row.id] || "").trim();
  if (!text) return;
  const data = await api.createComment(row.id, { text });
  communityRows.value = data.items;
  commentDrafts.value[row.id] = "";
  const updated = communityRows.value.find((item) => item.id === row.id);
  if (updated) updated.open = true;
}

async function savePostEdit() {
  if (!selectedCommunityPost.value || !canEditSelectedPost.value) return;
  const data = await api.updatePost(selectedCommunityPost.value.id, editPost.value);
  communityRows.value = data.items;
  selectedCommunityPostId.value = data.post.id;
  editingCommunityPost.value = false;
}

async function deleteSelectedPost() {
  if (!selectedCommunityPost.value || !canEditSelectedPost.value) return;
  if (!window.confirm("게시글을 삭제할까요?")) return;
  const data = await api.deletePost(selectedCommunityPost.value.id);
  communityRows.value = data.items;
  selectedCommunityPostId.value = null;
  editingCommunityPost.value = false;
  navigate("community");
}

function loadKakaoMap(appKey) {
  return new Promise((resolve) => {
    if (window.kakao?.maps) {
      window.kakao.maps.load(() => {
        kakaoReady.value = true;
        renderKakaoMap();
        resolve();
      });
      return;
    }
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false&libraries=services`;
    script.onload = () => {
      window.kakao.maps.load(() => {
        kakaoReady.value = true;
        renderKakaoMap();
        resolve();
      });
    };
    script.onerror = () => resolve();
    document.head.appendChild(script);
  });
}

function renderKakaoMap() {
  if (!kakaoReady.value || !kakaoMapEl.value || !window.kakao?.maps) return;
  const center = new window.kakao.maps.LatLng(selectedPoint.value.lat, selectedPoint.value.lng);
  if (kakaoMap && kakaoMapEl.value.childElementCount > 0) {
    centerKakaoMap();
    return;
  }
  kakaoMap = null;
  kakaoMarker = null;
  kakaoCircle = null;
  kakaoMap = new window.kakao.maps.Map(kakaoMapEl.value, { center, level: 4 });
  kakaoMarker = new window.kakao.maps.Marker({ map: kakaoMap, position: center });
  kakaoCircle = new window.kakao.maps.Circle({
    map: kakaoMap,
    center,
    radius: Number(radius.value),
    strokeWeight: 1,
    strokeColor: "#0f172a",
    strokeOpacity: 0.75,
    strokeStyle: "dash",
    fillColor: "#10b981",
    fillOpacity: 0.08,
  });
  window.kakao.maps.event.addListener(kakaoMap, "click", (event) => syncSelectedMapPoint(event.latLng));
  window.kakao.maps.event.addListener(kakaoMap, "dragend", () => syncSelectedMapPoint(kakaoMap.getCenter()));
  centerKakaoMap();
  updateNearbyPlaces();
}

function centerKakaoMap() {
  if (!kakaoMap || !window.kakao?.maps) return;
  const center = new window.kakao.maps.LatLng(selectedPoint.value.lat, selectedPoint.value.lng);
  const applyCenter = () => {
    kakaoMap.relayout();
    kakaoMap.setCenter(center);
    kakaoMarker?.setPosition(center);
    kakaoCircle?.setOptions({ center, radius: Number(radius.value) });
    updateNearbyPlaces();
  };
  requestAnimationFrame(applyCenter);
  setTimeout(applyCenter, 150);
}

async function loadVideos() {
  try {
    videos.value = await api.videos(videoQuery.value, videoCategory.value);
  } catch {
    videos.value = videoFallback;
  }
}

function renderCharts() {
  if (active.value !== "profile") return;
  if (monthlyChartEl.value) {
    monthlyChart?.dispose();
    monthlyChart = echarts.init(monthlyChartEl.value);
    const categoryData = spendRows.value.slice(0, 7).map((row) => ({
      name: row.name,
      spend: Number(row.amount || 0),
      saving: Math.round(Number(row.amount || 0) * 0.12),
    }));
    monthlyChart.setOption({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params) =>
          `${params[0].name}<br/>${params.map((item) => `${item.marker}${item.seriesName}: ${currency(item.value)}원`).join("<br/>")}`,
      },
      toolbox: { show: true, right: 0, feature: { saveAsImage: {} } },
      legend: { top: 0, left: 74, itemWidth: 11, itemHeight: 11, textStyle: { color: "#334155", fontWeight: 800 } },
      grid: { left: 8, right: 8, top: 54, bottom: 24, containLabel: true },
      xAxis: {
        type: "category",
        data: categoryData.map((row) => row.name),
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: "#334155", fontWeight: 900, interval: 0 },
      },
      yAxis: {
        type: "value",
        name: "만원",
        axisLabel: { formatter: (value) => `${Math.round(value / 10000)}만` },
        splitLine: { lineStyle: { color: "#edf1f4" } },
      },
      series: [
        {
          name: "이번 달 예상 소비",
          type: "bar",
          data: categoryData.map((row) => row.spend),
          barWidth: 26,
          barMinHeight: 18,
          itemStyle: { color: "#d9dde2", borderRadius: [6, 6, 0, 0] },
          label: {
            show: true,
            position: "top",
            formatter: (p) => (p.value / 10000).toFixed(1),
            color: "#111827",
            fontWeight: 900,
          },
          emphasis: { itemStyle: { opacity: 0.86 } },
          animationDuration: 420,
        },
        {
          name: "예상 절감 혜택",
          type: "bar",
          data: categoryData.map((row) => row.saving),
          barWidth: 26,
          barMinHeight: 8,
          itemStyle: { color: "#7b7f86", borderRadius: [6, 6, 0, 0] },
          label: {
            show: true,
            position: "top",
            formatter: (p) => (p.value / 10000).toFixed(1),
            color: "#111827",
            fontWeight: 900,
          },
          emphasis: { itemStyle: { opacity: 0.86 } },
          animationDuration: 420,
        },
      ],
    });
  }
  if (donutChartEl.value) {
    donutChart?.dispose();
    donutChart = echarts.init(donutChartEl.value);
    donutChart.setOption({
      tooltip: { trigger: "item", formatter: "{b}: {d}% ({c})" },
      legend: { orient: "vertical", right: 10, top: "center" },
      series: [
        {
          type: "pie",
          radius: ["48%", "76%"],
          center: ["28%", "50%"],
          data: spendRows.value.slice(0, 6).map((row) => ({ name: row.name, value: row.ratio })),
          color: ["#0f172a", "#10b981", "#7dd3fc", "#f59e0b", "#a78bfa", "#cbd5e1"],
          label: { show: false },
          emphasis: { scale: true, scaleSize: 10 },
          animationDuration: 420,
        },
      ],
    });
  }
}

watch([videoQuery, videoCategory], loadVideos);
watch(radius, () => {
  kakaoCircle?.setRadius(Number(radius.value));
  syncSelectedMapPoint(selectedPoint.value);
});
watch(spendRows, renderCharts, { deep: true });
watch(selectedPeriod, renderCharts);
watch(favoriteCards, saveFavoriteCards, { deep: true });
watch(currentUserId, loadFavoriteCards);
watch(ownedCardsForProfile, (cards) => {
  if (activeOwnedCardIndex.value >= cards.length) activeOwnedCardIndex.value = 0;
});
watch(active, async () => {
  await nextTick();
  if (active.value === "map") {
    renderKakaoMap();
    centerKakaoMap();
  }
  renderCharts();
});

onMounted(async () => {
  await Promise.all([loadVideos(), loadConfigAndProfile(), loadAuth(), loadCommunityPosts()]);
  await nextTick();
  renderKakaoMap();
  renderCharts();
  window.addEventListener("resize", renderCharts);
  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      commandOpen.value = !commandOpen.value;
    }
  });
});

onBeforeUnmount(() => {
  monthlyChart?.dispose();
  donutChart?.dispose();
  window.removeEventListener("resize", renderCharts);
});
</script>

<template>
  <div class="site-shell">
    <header class="site-header">
      <div class="header-inner">
        <button class="brand" @click="navigate('home')"><span class="brand-dot" aria-hidden="true"></span><strong>SeulPick</strong></button>
        <nav class="global-nav">
          <button v-for="page in pages" :key="page.id" :class="{ active: active === page.id }" @click="navigate(page.id)">{{ page.label }}</button>
        </nav>
        <div class="header-actions">
          <form class="global-search" @submit.prevent="openSearchResult(searchResults[0])">
            <span>⌕</span>
            <input
              v-model="globalSearchQuery"
              placeholder="페이지, 카드, 게시글 검색"
              @focus="commandOpen = true"
              @input="commandOpen = true"
            />
          </form>
          <button class="icon-button cart-button">⌁<span>0</span></button>
          <button v-if="!isAuthenticated" class="outline-button" @click="loginOpen = true">로그인</button>
          <button v-else class="outline-button" @click="logout">로그아웃</button>
        </div>
      </div>
      <div v-if="commandOpen" class="command-palette">
        <button v-for="result in searchResults" :key="`${result.type}-${result.title}`" @click="openSearchResult(result)">
          <span>{{ result.type }}</span>
          <strong>{{ result.title }}</strong>
          <small>{{ result.description }}</small>
        </button>
        <p v-if="!searchResults.length" class="empty-search">검색 결과가 없습니다.</p>
      </div>
    </header>

    <main class="page-main">
      <section v-if="active === 'home'" class="home-page reveal-section">
        <article class="home-hero">
          <button class="home-arrow" @click="triggerRecalculation">‹</button>
          <div>
            <span>지금 신규 카드 만들면</span>
            <h1>최대 7만원 혜택</h1>
            <p>혜택 좋은 카드를 지금 만나보세요</p>
            <button class="outline-button" @click="navigate('map')">자세히 보기</button>
          </div>
          <div class="hero-illustration" aria-hidden="true">
            <div class="hero-card-shape"></div>
            <div class="hero-card-shape back"></div>
            <div class="gift-box"></div>
            <div class="coin-mark">₩</div>
          </div>
          <button class="home-arrow right" @click="triggerRecalculation">›</button>
          <div class="hero-dots"><i></i><i></i><i></i><i></i></div>
        </article>

        <div class="home-action-grid">
          <article class="home-action-card">
            <div>
              <h2>지도에서 분석하기</h2>
              <p>지도에서 지역을 선택하고<br />혜택과 소비 데이터를 분석해요</p>
            </div>
            <div class="action-illustration map-art"></div>
            <button class="outline-button full" @click="navigate('map')">지도 분석하기</button>
          </article>
          <article class="home-action-card">
            <div>
              <h2>소비 내역 업로드</h2>
              <p>카드 사용 내역을<br />업로드하면 혜택을 분석해드려요</p>
            </div>
            <div class="action-illustration upload-art"></div>
            <button class="outline-button full" @click="navigate('map'); runUploadFlow()">업로드하기</button>
          </article>
        </div>

        <section class="home-section">
          <div class="home-section-head">
            <h2>6월! 최대 117만원 받기</h2>
            <button @click="navigate('cards')">전체보기 ›</button>
          </div>
          <div class="popular-card-row">
            <button v-for="card in liveCards.slice(0, 4)" :key="card.id" class="popular-card" @click="openDrawer(card)">
              <span class="round-card-art"></span>
              <strong>{{ card.name }}</strong>
            </button>
            <button v-for="card in topCards.slice(0, 2)" :key="card.name" class="popular-card" @click="openDrawer(card)">
              <span class="round-card-art muted"></span>
              <strong>{{ card.name }}</strong>
            </button>
          </div>
        </section>

        <section class="home-section">
          <div class="home-section-head">
            <h2>지금 가장 인기 있는 이벤트 카드</h2>
          </div>
          <div class="event-card-row">
            <article v-for="card in liveCards.slice(0, 4)" :key="card.id" class="event-card interactive" @mouseenter="hoveredCardId = card.id" @mouseleave="hoveredCardId = ''" @click="openDrawer(card)">
              <div class="event-thumb"></div>
              <b>{{ card.name }}</b>
              <span>최대 {{ currency(card.liveSaving) }}원 혜택</span>
            </article>
            <article v-for="card in topCards.slice(0, 1)" :key="card.name" class="event-card interactive" @click="openDrawer(card)">
              <div class="event-thumb pale"></div>
              <b>{{ card.name }}</b>
              <span>최대 {{ currency(card.saving) }}원 혜택</span>
            </article>
          </div>
        </section>

      </section>

      <section v-if="active === 'map'" class="page-section reveal-section">
        <div class="page-title">
          <span>Location Analysis</span>
          <h1>슬세권 분석</h1>
          <p>카카오 지도에서 생활권을 확인하고, 캡처 이미지 기반 소비 데이터를 추천에 반영합니다.</p>
        </div>
        <div class="map-page-grid">
          <article class="section-panel map-panel-large">
            <div class="panel-head"><h2>지역 선택</h2><p>{{ recalculating ? "추천 재계산 중" : "지도 이동과 반경 변경을 감지합니다" }}</p></div>
            <div class="toolbar-row">
              <div class="segmented"><button class="active">지도에서 선택</button><button>주소로 검색</button></div>
              <form class="field-input" @submit.prevent="searchAddress">
                <input v-model="addressSearchQuery" placeholder="주소 또는 장소명을 입력하세요" />
                <button type="submit">검색</button>
              </form>
            </div>
            <div class="map-layout">
              <div class="category-list">
                <button v-for="category in mapCategories" :key="category" :class="{ active: selectedCategory === category }" @click="selectMapCategory(category)">{{ category }}</button>
              </div>
              <div class="map-canvas">
                <div ref="kakaoMapEl" class="kakao-map"></div>
                <template v-if="!kakaoReady">
                  <div class="map-marker marker-a">편</div>
                  <div class="map-marker marker-b">카</div>
                  <div class="map-marker marker-c">마</div>
                  <div class="radius" :style="{ width: `${radius / 2.8}px`, height: `${radius / 2.8}px` }"><span>반경 {{ radius }}m</span></div>
                  <div class="center-pin">중심</div>
                </template>
              </div>
            </div>
            <div class="range-row">
              <span>100m</span>
              <input v-model.number="radius" type="range" min="300" max="900" step="100" />
              <span>{{ radius }}m</span>
            </div>
            <p class="map-status-copy">{{ selectedCategory }} 기준 반경 {{ radius }}m 안의 장소 {{ nearbyPlaceCount }}개를 표시 중입니다.</p>
            <button class="outline-button full" @click="triggerRecalculation">이 데이터로 확정</button>
          </article>

          <article class="section-panel">
            <div class="panel-head"><h2>소비 내역 자동 분석</h2><p>선택 사항</p></div>
            <p>가계부 또는 카드 캡처 이미지를 업로드하면 AI가 카테고리별 소비액을 자동으로 채워드립니다.</p>
            <button class="upload-zone" @click="runUploadFlow">
              <b>{{ uploadState }}</b>
              <strong>이미지를 드래그하거나 클릭하여 업로드</strong>
              <small>JPG, PNG, HEIC 파일 지원</small>
              <span class="progress"><i :style="{ width: `${uploadProgress}%` }"></i></span>
            </button>
            <input
              ref="receiptUploadEl"
              class="visually-hidden-input"
              type="file"
              accept="image/jpeg,image/png,image/heic,image/heif"
              @change="handleReceiptUpload"
            />
            <div class="ai-table">
              <small>AI 분석 예시 [예제]</small>
              <div v-for="row in spendRows" :key="row.name"><span>{{ row.name }}</span><b>{{ currency(row.amount) }}원</b></div>
            </div>
            <button class="primary-button full" @click="triggerRecalculation">이 데이터로 적용하기</button>
          </article>
        </div>

        <section v-if="false" class="graph-insight-grid reveal-section">
          <article class="section-panel benefit-map-panel">
            <div class="panel-head">
              <div>
                <h2>지역별 혜택 지도</h2>
                <p>선택 반경 안에서 카드 혜택과 연결된 업종 신호입니다.</p>
              </div>
            </div>
            <div v-if="areaBenefitInsights.length" class="benefit-density-list">
              <div v-for="item in areaBenefitInsights" :key="item.category">
                <div>
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.count }}개 지점</span>
                </div>
                <i :style="{ width: `${Math.max(12, Math.min(100, item.share ? item.share * 100 : item.count))}%` }"></i>
              </div>
            </div>
            <p v-else class="empty-insight">추천 결과를 확정하면 지역 혜택 밀도가 표시됩니다.</p>
          </article>

          <article class="section-panel regional-card-panel">
            <div class="panel-head">
              <div>
                <h2>이 지역 업종에서 반응이 좋은 카드</h2>
                <p>현재 지역의 주요 업종과 사용자 클릭/좋아요/신청 행동을 함께 반영한 순위입니다.</p>
              </div>
            </div>
            <div class="regional-card-list">
              <button v-for="card in regionalPopularCards" :key="card.id || card.name" @click="openDrawer(card)">
                <b>{{ card.name }}</b>
                <span>인기 {{ card.local_popularity?.local_popularity_score ?? 0 }}점 · 행동 {{ card.local_popularity?.event_score ?? 0 }}점</span>
              </button>
            </div>
            <p v-if="!regionalPopularCards.length" class="empty-insight">이 지역의 카드 행동 로그가 쌓이면 인기 카드가 표시됩니다.</p>
          </article>
        </section>

        <article class="section-panel report-panel reveal-section">
          <div class="panel-head">
            <div><h2>맞춤형 카드 추천 리포트</h2><p>선택한 지역의 상권 데이터와 소비 패턴을 분석한 맞춤 추천 결과예요.</p></div>
            <button class="outline-button" @click="navigate('cards')">전체 카드 랭킹 대시보드 보기</button>
          </div>
          <div v-if="false" class="filter-row">
            <button v-for="filter in reportFilters" :key="filter" :class="{ active: selectedReportFilter === filter }" @click="selectedReportFilter = filter">{{ filter }}</button>
          </div>
          <div class="report-category-row">
            <button
              v-for="category in reportCategoryOptions"
              :key="category"
              :class="{ active: !showReportPopularCards && selectedReportCategory === category }"
              @click="selectReportCategory(category)"
            >
              {{ category }}
            </button>
            <button :class="{ active: showReportPopularCards }" @click="selectReportPopularCards">지역 인기카드</button>
          </div>
          <div v-if="showReportPopularCards" class="report-popular-section">
            <p class="report-popular-copy">해당 지역에서 많이 조회된 카드</p>
            <button
              v-for="(card, index) in reportPopularCards"
              :key="card.id || card.name"
              class="report-popular-rank-card"
              @click="openDrawer(card)"
            >
              <span class="report-popular-rank">{{ index + 1 }}</span>
              <span class="report-popular-thumb" :style="{ '--card-color': card.color || '#e7f1ef' }"></span>
              <b>{{ card.name }}</b>
              <span class="report-popular-arrow">▾</span>
            </button>
          </div>
          <div v-if="!showReportPopularCards" class="report-columns">
            <section v-for="group in reportGroups" :key="group.id" class="report-column">
              <h3>{{ group.badge }}</h3>
              <button class="report-arrow report-arrow-left" @click="moveReportCard(group, -1)">‹</button>
              <article
                v-for="card in visibleReportCards(group)"
                :key="card.id"
                class="report-card-frame interactive"
                @mouseenter="hoveredCardId = card.id"
                @mouseleave="hoveredCardId = ''"
                @click="openDrawer(card)"
              >
                <div class="report-score-row">
                  <strong>{{ card.score }}<small>점</small></strong>
                </div>
                <div class="report-card-visual" :class="{ green: group.id === 'check' }">
                  <small>SeulPick</small>
                  <b>{{ card.name }}</b>
                  <em>{{ card.type }}</em>
                  <i></i>
                  <span>•••• {{ card.number }}</span>
                </div>
                <p class="score-line">Seul-Score <b>{{ stars(card.score) }}</b></p>
                <p class="graph-score-line">Graph rerank <b>{{ card.graph_rerank_score || "-" }}점</b></p>
                <p class="saving-line">예상 월 절약/혜택 금액 <strong>{{ currency(card.saving) }}원</strong></p>
                <small class="detail-label">상세 혜택</small>
                <ul>
                  <li v-for="benefit in card.benefits" :key="benefit">{{ benefit }}</li>
                </ul>
                <button class="ghost-button" @click.stop="toggleFavorite(card)">{{ isFavorite(card) ? "♥ 찜됨" : "♡ 찜" }}</button>
              </article>
              <button class="report-arrow report-arrow-right" @click="moveReportCard(group, 1)">›</button>
              <div class="dots report-dots">
                <button
                  v-for="(_, dotIndex) in reportCarouselCards(group)"
                  :key="dotIndex"
                  :class="{ active: reportCarouselIndex(group) === dotIndex }"
                  @click="selectReportCard(group, dotIndex)"
                ></button>
              </div>
            </section>
          </div>
        </article>
      </section>

      <section v-if="active === 'cards'" class="page-section reveal-section">
        <div class="page-title">
          <span>Cards</span>
          <h1>카드 추천 대시보드</h1>
          <p>카드별 절약액, 혜택, 보유 여부를 한눈에 비교합니다.</p>
        </div>
        <div class="gorilla-tabs">
          <button :class="{ active: selectedCardFilter === '신용카드' }" @click="selectedCardFilter = '신용카드'">신용카드</button>
          <button :class="{ active: selectedCardFilter === '체크카드' }" @click="selectedCardFilter = '체크카드'">체크카드</button>
          <button :class="{ active: selectedCardFilter === '전체' }" @click="selectedCardFilter = '전체'">전체</button>
        </div>
        <div class="gorilla-card-list">
          <article v-for="card in filteredGorillaCards" :key="card.name" class="gorilla-card-item interactive" @click="openDrawer(card)">
            <div class="gorilla-card-art" :style="{ '--card-color': card.color }">
              <span></span>
            </div>
            <div class="gorilla-card-body">
              <div class="gorilla-title-row">
                <h2>{{ card.name }}</h2>
                <small>{{ card.issuer }}</small>
              </div>
              <b class="benefit-badge">{{ card.benefitBadge }}</b>
              <div class="perk-grid">
                <div v-for="perk in card.perks" :key="perk[0] + perk[1]">
                  <span>{{ perk[0] }}</span>
                  <strong>{{ perk[1] }}</strong>
                </div>
              </div>
              <p>{{ card.fees }} <span>{{ card.condition }}</span></p>
            </div>
            <button class="detail-button" @click.stop="openDrawer(card)">자세히 보기</button>
          </article>
        </div>
      </section>

      <section v-if="active === 'videos'" class="page-section reveal-section">
        <div class="page-title">
          <span>YouTube</span>
          <h1>유튜브 검색</h1>
          <p>카드 추천, 혜택 비교, 소비 팁 영상을 YouTube에 검색합니다.</p>
        </div>
        <div class="youtube-toolbar">
          <input v-model="videoQuery" class="search-input" placeholder="검색어를 입력해주세요 (예: 카드 추천)" />
          <div class="filter-row"><button v-for="category in videos.categories" :key="category" :class="{ active: videoCategory === category }" @click="videoCategory = category">{{ category }}</button></div>
        </div>
        <div class="youtube-grid">
          <article v-for="video in videos.items" :key="video.id" class="youtube-card interactive">
            <a v-if="video.url" :href="video.url" target="_blank" rel="noreferrer" class="youtube-thumb">
              <img v-if="video.thumbnail" :src="video.thumbnail" :alt="video.title" />
              <span v-else>영상</span>
              <b>{{ video.duration }}</b>
            </a>
            <div v-else class="youtube-thumb">
              <span>영상</span>
              <b>{{ video.duration }}</b>
            </div>
            <div class="youtube-info">
              <div class="channel-avatar">{{ video.channel?.slice(0, 1) || "S" }}</div>
              <div>
                <h3><a v-if="video.url" :href="video.url" target="_blank" rel="noreferrer">{{ video.title }}</a><template v-else>{{ video.title }}</template></h3>
                <p>{{ video.channel }}</p>
                <small>조회수 {{ video.views }} · {{ video.age }}</small>
              </div>
              <button>⋮</button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="active === 'community'" class="page-section reveal-section">
        <div class="page-title">
          <span>Community</span>
          <h1>커뮤니티</h1>
          <p>카드 사용 후기와 지역 혜택 정보를 공유하는 게시판입니다.</p>
        </div>
        <div class="filter-row"><button v-for="tab in communityTabs" :key="tab" :class="{ active: selectedCommunityTab === tab }" @click="selectedCommunityTab = tab">{{ tab }}</button></div>
        <article class="section-panel table-panel">
          <table>
            <thead><tr><th>제목</th><th>작성자</th><th>작성일</th><th>조회</th><th>공감</th><th>예산</th></tr></thead>
            <tbody>
              <template v-for="row in paginatedCommunityRows" :key="row.title">
                <tr class="interactive-row" @click="openCommunityPost(row)">
                  <td>{{ row.title }}</td><td>{{ row.author }}</td><td>{{ row.time }}</td><td>{{ row.views }}</td><td><button class="ghost-button" @click.stop="row.likes += 1">{{ row.likes }}</button></td><td>{{ row.budget }}</td>
                </tr>
              </template>
            </tbody>
          </table>
          <div class="community-bottom-bar">
            <div class="community-pages">
              <button :disabled="communityPage === 1" @click="moveCommunityPage(communityPage - 1)">‹</button>
              <button v-for="page in communityTotalPages" :key="page" :class="{ active: communityPage === page }" @click="moveCommunityPage(page)">{{ page }}</button>
              <button :disabled="communityPage === communityTotalPages" @click="moveCommunityPage(communityPage + 1)">›</button>
            </div>
            <button class="primary-button" @click="requireLogin() && navigate('communityWrite')">글쓰기</button>
          </div>
        </article>
      </section>

      <section v-if="active === 'communityPost'" class="page-section reveal-section">
        <div class="page-title">
          <span>Community</span>
          <h1>게시글 보기</h1>
          <p>게시글 내용과 댓글을 확인하고 의견을 남겨보세요.</p>
        </div>
        <article v-if="selectedCommunityPost" class="section-panel post-detail-page">
          <div class="post-detail-head">
            <button class="outline-button" @click="navigate('community')">목록으로</button>
            <span>{{ selectedCommunityPost.tab }}</span>
            <div v-if="canEditSelectedPost" class="post-owner-actions">
              <button v-if="!editingCommunityPost" class="outline-button" @click="startEditPost">수정</button>
              <button v-if="!editingCommunityPost" class="danger-button" @click="deleteSelectedPost">삭제</button>
            </div>
          </div>
          <h2 v-if="!editingCommunityPost">{{ selectedCommunityPost.title }}</h2>
          <div v-else class="post-edit-form">
            <label>
              게시판
              <select v-model="editPost.tab">
                <option v-for="tab in communityTabs" :key="tab" :value="tab">{{ tab }}</option>
              </select>
            </label>
            <label>
              제목
              <input v-model="editPost.title" placeholder="게시글 제목을 입력하세요" />
            </label>
          </div>
          <div class="post-detail-meta">
            <b>{{ selectedCommunityPost.author }}</b>
            <span>{{ selectedCommunityPost.time }}</span>
            <span>조회 {{ selectedCommunityPost.views }}</span>
            <span>공감 {{ selectedCommunityPost.likes }}</span>
            <span>예산 {{ selectedCommunityPost.budget }}</span>
          </div>
          <div v-if="!editingCommunityPost" class="post-detail-content">
            {{ selectedCommunityPost.content || "선택한 소비 패턴과 지역 데이터를 기준으로 댓글과 추천 정보를 확장해서 확인할 수 있습니다." }}
          </div>
          <div v-else class="post-edit-form">
            <label>
              게시글
              <textarea v-model="editPost.content" placeholder="게시글 내용을 입력하세요"></textarea>
            </label>
            <label>
              예산
              <input v-model="editPost.budget" placeholder="200,000원" @keyup.enter="savePostEdit" />
            </label>
            <div class="post-write-actions">
              <button class="outline-button" @click="cancelEditPost">취소</button>
              <button class="primary-button" @click="savePostEdit">수정 완료</button>
            </div>
          </div>
          <div class="comment-panel post-detail-comments">
            <h3>댓글 {{ (selectedCommunityPost.comments || []).length }}</h3>
            <div v-for="comment in selectedCommunityPost.comments || []" :key="comment.id" class="comment-item">
              <b>{{ comment.author }}</b><span>{{ comment.text }}</span><small>{{ comment.time }}</small>
            </div>
            <div class="comment-form">
              <input v-model="commentDrafts[selectedCommunityPost.id]" placeholder="댓글을 입력하세요" @keyup.enter="createComment(selectedCommunityPost)" />
              <button class="outline-button" @click="createComment(selectedCommunityPost)">댓글 쓰기</button>
            </div>
          </div>
        </article>
        <article v-else class="section-panel post-detail-page">
          <h2>게시글을 찾을 수 없습니다.</h2>
          <button class="primary-button" @click="navigate('community')">목록으로 돌아가기</button>
        </article>
      </section>

      <section v-if="active === 'communityWrite'" class="page-section reveal-section">
        <div class="page-title">
          <span>Community</span>
          <h1>커뮤니티 글쓰기</h1>
          <p>카드 사용 후기와 지역 혜택 정보를 새 게시글로 공유해보세요.</p>
        </div>
        <article class="section-panel post-write-page">
          <div class="post-write-head">
            <div>
              <h2>새 게시글 작성</h2>
              <p>작성한 글은 커뮤니티 목록의 첫 페이지에 바로 반영됩니다.</p>
            </div>
            <button class="outline-button" @click="navigate('community')">목록으로</button>
          </div>
          <div class="post-write-form">
            <label>
              게시판
              <select v-model="newPost.tab">
                <option v-for="tab in communityTabs" :key="tab" :value="tab">{{ tab }}</option>
              </select>
            </label>
            <label>
              제목
              <input v-model="newPost.title" placeholder="게시글 제목을 입력하세요" />
            </label>
            <label>
              게시글
              <textarea v-model="newPost.content" placeholder="게시글 내용을 입력하세요"></textarea>
            </label>
            <label>
              예산
              <input v-model="newPost.budget" placeholder="200,000원" @keyup.enter="createPost" />
            </label>
            <div class="post-write-actions">
              <button class="outline-button" @click="navigate('community')">취소</button>
              <button class="primary-button" @click="createPost">게시글 등록</button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="active === 'profile'" class="page-section reveal-section">
        <div class="page-title">
          <span>Profile</span>
          <h1>{{ userProfile.name }}님의 소비 데이터</h1>
          <p>내 정보와 소비 데이터를 한눈에 확인하세요.</p>
        </div>
        <div class="profile-grid">
          <article class="section-panel profile-card">
            <div class="profile-image">{{ userProfile.name?.slice(0, 1) || "김" }}</div>
            <div v-if="!profileEditing" class="profile-basic-info">
              <span>프로필 기본 정보</span>
              <h2>{{ userProfile.name }} 님</h2>
              <p>{{ userProfile.email }}</p>
              <dl>
                <dt>현재 관심 지역</dt>
                <dd>서울 강남구 역삼동, 반경 {{ radius }}m</dd>
              </dl>
              <div class="profile-actions">
                <button class="outline-button" @click="requireLogin() && (profileEditing = true)">프로필 수정</button>
                <button class="primary-button" @click="navigate('map')">관심 지역 변경</button>
              </div>
            </div>
            <div v-else class="profile-edit-form">
              <input v-model="profileForm.name" placeholder="이름" />
              <input v-model="profileForm.email" placeholder="이메일" />
              <input v-model="profileForm.password" type="password" placeholder="새 비밀번호 (선택)" />
              <div>
                <button class="primary-button" @click="saveProfile">저장</button>
                <button class="outline-button" @click="profileEditing = false">취소</button>
              </div>
            </div>
          </article>
          <article class="section-panel owned-card-panel">
            <div class="panel-head"><h2>내 보유 카드</h2><p>{{ ownedCardsForProfile.length }}개 등록</p></div>
            <div class="owned-card-carousel" v-if="activeOwnedCard">
              <button class="owned-card-arrow" :disabled="ownedCardsForProfile.length <= 1" @click="moveOwnedCard(-1)">‹</button>
              <article class="owned-card active-owned-card interactive" @click="openDrawer(activeOwnedCard)">
                <div class="owned-card-visual">
                  <small>SeulPick</small>
                  <b>{{ activeOwnedCard.name }}</b>
                  <span>{{ activeOwnedCard.issuer || "등록 카드" }}</span>
                </div>
                <div>
                  <strong>{{ activeOwnedCard.name }}</strong>
                  <p>{{ activeOwnedCard.issuer || "등록 카드" }} · {{ activeOwnedCard.type || "보유" }}</p>
                  <em>보유 카드</em>
                  <small>{{ activeOwnedCardIndex + 1 }} / {{ ownedCardsForProfile.length }}</small>
                </div>
              </article>
              <button class="owned-card-arrow" :disabled="ownedCardsForProfile.length <= 1" @click="moveOwnedCard(1)">›</button>
            </div>
            <div class="owned-card-dots" v-if="ownedCardsForProfile.length > 1">
              <button v-for="(_, index) in ownedCardsForProfile" :key="index" :class="{ active: activeOwnedCardIndex === index }" @click="activeOwnedCardIndex = index"></button>
            </div>
          </article>
        </div>
        <div class="content-grid two">
          <article class="section-panel"><div class="panel-head"><h2>혜택/소비 시각화</h2><p>카테고리별 이번 달 예상 소비와 예상 절감 혜택</p></div><div ref="monthlyChartEl" class="chart-box"></div></article>
          <article class="section-panel"><h2>카드/혜택 월간 소비 비율</h2><div ref="donutChartEl" class="chart-box"></div></article>
        </div>
        <div class="content-grid two">
          <article class="section-panel behavior-recommend-panel">
            <div class="panel-head">
              <div>
                <h2>유사 사용자 추천</h2>
                <p>나와 비슷한 소비 패턴의 사용자들이 많이 선택한 카드입니다.</p>
                <div class="behavior-tags">
                  <span v-for="tag in behaviorHashtags" :key="tag">{{ tag }}</span>
                </div>
              </div>
            </div>
            <div v-if="behaviorRecommendedCard" class="similar-user-card interactive" @click="openDrawer(behaviorRecommendedCard)">
              <div class="similar-card-art">
                <span></span>
              </div>
              <div class="similar-card-copy">
                <small>유사 사용자 선택 1위</small>
                <b>{{ behaviorRecommendedCard.name }}</b>
                <p>유사 사용자들 중 카드값 사용금액이 상위 {{ similarUserInsight.topPercent }}%입니다.</p>
                <strong>평균: {{ currency(similarUserInsight.averageSpend) }}원 사용</strong>
              </div>
            </div>
          </article>
          <article class="section-panel">
            <div class="panel-head">
              <div>
                <h2>찜 목록</h2>
                <p>{{ favoriteCardsForProfile.length }}개 카드 저장</p>
              </div>
            </div>
            <div v-if="favoriteCardsForProfile.length" class="regional-card-list">
              <button v-for="card in favoriteCardsForProfile" :key="card.name" @click="openDrawer(card)">
                <b>{{ card.name }}</b>
                <span>{{ card.issuer || "추천 카드" }} · {{ currency(card.liveSaving || card.saving || 0) }}원 예상 혜택</span>
              </button>
            </div>
            <p v-else class="empty-insight">카드 상세에서 하트를 누르면 찜 목록에 저장됩니다.</p>
          </article>
        </div>
      </section>
    </main>

    <div v-if="loginOpen" class="modal-backdrop" @click.self="loginOpen = false">
      <section class="modal-card auth-modal">
        <div class="panel-head">
          <h2>{{ loginMode === "login" ? "로그인" : "회원가입" }}</h2>
          <button class="drawer-close" @click="loginOpen = false">닫기</button>
        </div>
        <p class="form-error" v-if="authError">{{ authError }}</p>
        <label>아이디<input v-model="authForm.username" placeholder="seulpick" /></label>
        <label v-if="loginMode === 'register'">이름<input v-model="authForm.name" placeholder="김슬픽" /></label>
        <label v-if="loginMode === 'register'">이메일<input v-model="authForm.email" placeholder="seulpick@example.com" /></label>
        <label>비밀번호<input v-model="authForm.password" type="password" placeholder="seulpick123" @keyup.enter="submitAuth" /></label>
        <button class="primary-button full" @click="submitAuth">{{ loginMode === "login" ? "로그인" : "가입하고 로그인" }}</button>
        <button class="outline-button full" @click="loginMode = loginMode === 'login' ? 'register' : 'login'; authError = ''">
          {{ loginMode === "login" ? "회원가입으로 전환" : "로그인으로 전환" }}
        </button>
      </section>
    </div>

    <aside v-if="drawerCard" class="side-drawer">
      <button class="drawer-close" @click="drawerCard = null">닫기</button>
      <span class="drawer-kicker">카드 상세 혜택</span>
      <div class="drawer-title-row">
        <h2>{{ drawerCard.name }}</h2>
        <button
          class="drawer-favorite-button"
          :class="{ active: isFavorite(drawerCard) }"
          :aria-label="isFavorite(drawerCard) ? '찜 해제' : '찜하기'"
          @click="toggleFavorite(drawerCard)"
        >
          <span></span>
          찜
        </button>
      </div>
      <em v-if="isOwned(drawerCard.name)">보유 카드</em>
      <p>{{ drawerCard.issuer || "SeulPick" }} · {{ drawerCard.type || drawerCard.specialty || "추천 카드" }}</p>
      <div v-if="drawerCard.benefitBadge" class="drawer-card-hero">
        <div class="gorilla-card-art" :style="{ '--card-color': drawerCard.color || '#111827' }"><span></span></div>
        <div>
          <b class="benefit-badge">{{ drawerCard.benefitBadge }}</b>
          <p>{{ drawerDetailInfo.annualFee }}</p>
          <p>{{ drawerDetailInfo.condition }}</p>
        </div>
      </div>
      <section class="drawer-info-card">
        <div>
          <span>연회비</span>
          <strong>{{ drawerDetailInfo.annualFee }}</strong>
        </div>
        <div>
          <span>전월실적</span>
          <strong>{{ drawerDetailInfo.condition }}</strong>
        </div>
      </section>
      <div v-if="drawerDetailInfo.perks.length" class="drawer-perks">
        <div v-for="perk in drawerDetailInfo.perks" :key="perk">
          <span>{{ perk }}</span>
          <strong>혜택 적용</strong>
        </div>
      </div>
      <div class="drawer-score"><strong>{{ drawerCard.liveScore || drawerCard.score || Math.round((drawerCard.saving || 0) / 10000) }}점</strong><span>{{ recalculating ? "재계산 중" : "혜택 조건과 소비 패턴 반영" }}</span></div>
      <section class="drawer-region-reason">
        <h3>왜 이 카드가 추천되었나요?</h3>
        <p>{{ recommendationReasonForCard(drawerCard) }}</p>
      </section>
      <section v-if="drawerDetailInfo.benefits.length" class="drawer-benefit-list">
        <h3>카드 상세 혜택</h3>
        <details v-for="benefit in drawerDetailInfo.benefits" :key="benefit" open>
          <summary>{{ benefit }}</summary>
          <p>선택한 카드의 핵심 혜택 조건과 월 예상 혜택에 반영되는 항목입니다.</p>
        </details>
      </section>
      <div class="drawer-action-grid">
        <button class="primary-button full" @click="applyForCard(drawerCard)">발급 신청</button>
      </div>
    </aside>

  </div>
</template>
