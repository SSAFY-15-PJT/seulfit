<template>
  <section class="map-page">
    <div class="map-layout">
      <div class="map-panel">
        <div class="map-hero panel">
          <div class="map-brand-row">
            <div>
              <p class="eyebrow">SeulPick</p>
              <h1>상권맵</h1>
            </div>
            <div class="map-brand-note">카드 추천과 지역 분석을 한 화면에서 확인합니다.</div>
          </div>

          <div class="search-row">
            <div class="fake-input">
              <Search :size="15" />
              지도를 클릭하면 해당 위치의 상권이 다시 분석됩니다
            </div>
            <button class="secondary-button" @click="loadMapAt(DEFAULT_CENTER)">
              <LocateFixed :size="15" />
              강남역으로 초기화
            </button>
          </div>

          <div class="kakao-map-shell">
            <div ref="mapElement" class="kakao-map"></div>
            <div v-if="loading" class="map-loading">상권 분석 중...</div>
            <div v-if="mapError" class="map-error">
              <strong>카카오맵을 불러오지 못했습니다.</strong>
              <span>{{ mapError }}</span>
            </div>
          </div>

          <div class="legend">
            <span><i class="dot convenience"></i>편의점</span>
            <span><i class="dot cafe"></i>카페</span>
            <span><i class="dot mart"></i>마트</span>
            <span><i class="dot food"></i>외식</span>
          </div>
        </div>

        <section v-if="hasRecommendationResult" ref="resultSection" class="panel map-results">
          <div class="section-head">
            <div>
              <p class="eyebrow">추천 결과</p>
              <h2>{{ selectedCategoryLabel }} 기준 카드 비교</h2>
            </div>
            <div class="section-hint">신용카드와 체크카드를 나눠서 확인할 수 있습니다.</div>
          </div>

          <div class="result-summary">
            <div>
              <span>추천 기준</span>
              <strong>{{ recommendationLocationLabel }}</strong>
            </div>
            <div>
              <span>분석 카드 수</span>
              <strong>{{ rankingCards.length }}장</strong>
            </div>
            <div>
              <span>선택 카테고리</span>
              <strong>{{ selectedCategoryLabel }}</strong>
            </div>
          </div>

          <div class="category-strip compact">
            <button
              v-for="item in visibleCategories"
              :key="item.key"
              type="button"
              class="category-chip"
              :class="{ active: item.key === selectedCategoryKey }"
              @click="activeCategory = item.key"
            >
              <span class="category-chip-icon">{{ categoryIcon(item.key) }}</span>
              <span>{{ item.label }}</span>
            </button>
          </div>

          <div class="recommendation-tabs">
            <button
              type="button"
              class="type-tab"
              :class="{ active: recommendationType === 'credit' }"
              @click="recommendationType = 'credit'"
            >
              신용카드
            </button>
            <button
              type="button"
              class="type-tab"
              :class="{ active: recommendationType === 'debit' }"
              @click="recommendationType = 'debit'"
            >
              체크카드
            </button>
          </div>

          <div class="result-stack">
            <section class="result-group">
              <div class="section-head slim">
                <div>
                  <p class="eyebrow">
                    {{ recommendationType === 'credit' ? '신용카드 Top 3' : '체크카드 Top 3' }}
                  </p>
                  <h3>
                    {{ selectedCategoryLabel }}에서 가장 맞는
                    {{ recommendationType === 'credit' ? '신용카드' : '체크카드' }}
                  </h3>
                </div>
                <div class="section-hint">카드 이미지와 혜택을 한 장씩 넘겨서 봅니다.</div>
              </div>

              <div v-if="activeSlides.length" class="featured-rail">
                <button
                  class="carousel-arrow"
                  type="button"
                  :disabled="activeSlides.length < 2"
                  @click="moveSlide(-1)"
                >
                  <ChevronLeft :size="18" />
                </button>

                <article class="featured-card">
                  <div class="featured-art">
                    <div class="featured-ring"></div>
                    <div class="featured-art-frame">
                      <img
                        v-if="currentCard.image_url"
                        :src="currentCard.image_url"
                        :alt="currentCard.name"
                        loading="lazy"
                      />
                      <div v-else class="featured-art-placeholder">
                        {{ initials(currentCard.name) }}
                      </div>
                    </div>
                  </div>

                  <div class="featured-copy">
                    <div class="featured-topline">
                      <div class="featured-counter">
                        <strong>{{ slideNumber(activeSlideIndex, activeSlides.length) }}</strong>
                        <span>/ {{ activeSlides.length }}</span>
                      </div>
                      <span class="type-pill" :class="cardTypeClass(currentCard.card_type)">
                        {{ cardTypeLabel(currentCard.card_type) }}
                      </span>
                    </div>

                    <h4>{{ currentCard.name }}</h4>
                    <p class="issuer">{{ currentCard.issuer }}</p>

                    <div class="benefit-list">
                      <div class="benefit-line">
                        <span>카테고리 혜택</span>
                        <strong>{{ benefitHeadline(currentCard, selectedCategoryKey) }}</strong>
                      </div>
                      <div class="benefit-line">
                        <span>예상 순혜택</span>
                        <strong>{{ formatWon(currentCard.estimated_net_value) }}</strong>
                      </div>
                      <div class="benefit-line">
                        <span>Seul-Score</span>
                        <strong>{{ formatScore(currentCard.seul_score) }}</strong>
                      </div>
                    </div>

                    <div class="featured-bullets">
                      <p v-for="line in benefitDetails(currentCard, selectedCategoryKey)" :key="line">
                        {{ line }}
                      </p>
                    </div>

                    <div class="condition-strip">
                      <span v-if="currentCard.previous_month_requirement">
                        전월실적 {{ formatWon(currentCard.previous_month_requirement) }} 이상
                      </span>
                      <span v-if="currentCard.annual_fee != null">
                        연회비 {{ formatWon(currentCard.annual_fee) }}
                      </span>
                      <span v-if="currentCard.monthly_discount_limit != null">
                        월 한도 {{ formatWon(currentCard.monthly_discount_limit) }}
                      </span>
                      <span v-if="currentCard.monthly_annual_fee != null">
                        월 환산 {{ formatWon(currentCard.monthly_annual_fee) }}
                      </span>
                    </div>

                    <div class="badge-row">
                      <span v-if="currentCard.is_owned" class="owned-pill">보유중인 카드</span>
                      <span v-else class="metric-pill">추천 후보</span>
                    </div>
                  </div>
                </article>

                <button
                  class="carousel-arrow"
                  type="button"
                  :disabled="activeSlides.length < 2"
                  @click="moveSlide(1)"
                >
                  <ChevronRight :size="18" />
                </button>
              </div>

              <div v-if="activeSlides.length" class="carousel-dots">
                <button
                  v-for="(_, index) in activeSlides"
                  :key="`dot-${recommendationType}-${index}`"
                  type="button"
                  class="carousel-dot"
                  :class="{ active: index === activeSlideIndex }"
                  @click="activeSlideIndex = index"
                />
              </div>
              <p v-else class="empty-copy">이 카테고리의 후보가 아직 없습니다.</p>
            </section>

            <div class="recommendation-actions">
              <button class="secondary-button" type="button" @click="goDashboard">
                추천 결과 자세히보기
              </button>
            </div>
          </div>

          <p class="helper-text">
            카드 이미지는 `image_url`이 있으면 그대로 표시하고, 없을 때는 이니셜로 대체합니다.
            카드 혜택은 선택한 카테고리에 해당하는 계산 내역을 우선 보여줍니다.
          </p>
        </section>
      </div>

      <aside class="sidebar">
        <div class="panel login-panel">
          <div class="login-panel-head">
            <div>
              <p class="eyebrow">로그인</p>
              <h2>간편번호로 시작</h2>
            </div>
            <span class="login-link">다른 로그인 방법 &gt;</span>
          </div>

          <div class="login-tabs">
            <button type="button" class="login-tab active">간편번호</button>
            <button type="button" class="login-tab">카카오</button>
            <button type="button" class="login-tab">네이버</button>
          </div>

          <div class="login-pin-box">
            <p>홈페이지 간편번호 6자리를 설정해 주세요</p>
            <div class="pin-dots">
              <span></span>
              <span></span>
              <span></span>
              <span></span>
              <span></span>
              <span></span>
            </div>
            <button class="primary-button login-cta">간편번호 등록</button>
          </div>

          <div class="login-shortcuts">
            <button class="shortcut-chip">아이디 찾기</button>
            <button class="shortcut-chip">비밀번호 재설정</button>
            <button class="shortcut-chip">회원가입</button>
          </div>
        </div>

        <div class="panel sidebar-hero">
          <p class="eyebrow">오늘의 지역 분석</p>
          <div class="weather-box">
            <Sun class="icon-lg" />
            <div>
              <strong>{{ weather.temperature_celsius }}°C · {{ weather.condition }}</strong>
              <p>{{ weather.message }}</p>
            </div>
          </div>
        </div>

        <div class="panel sidebar-card">
          <p class="eyebrow">상권 요약</p>
          <span class="zone-badge">{{ map.zone_type || "분석 대기" }}</span>
          <div v-if="map.source" class="source-badge">
            {{ map.source === "kakao" ? "Kakao Local API 반영" : "Mock 데이터 표시" }}
          </div>
          <p class="selected-point">
            선택 좌표: {{ selectedPoint.lat.toFixed(5) }}, {{ selectedPoint.lng.toFixed(5) }}
          </p>
          <div v-for="item in map.infrastructure" :key="item.code" class="info-row">
            <span>{{ item.category }} ({{ item.code }})</span>
            <strong>
              {{ item.count }}곳
              <small v-if="item.walk_minutes">· 도보 {{ item.walk_minutes }}분</small>
            </strong>
          </div>
          <button class="primary-button" :disabled="recommending" @click="runRecommendation">
            {{ recommending ? "추천 계산 중..." : "카드 추천 결과보기" }}
          </button>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ChevronLeft, ChevronRight, LocateFixed, Search, Sun } from "lucide-vue-next";
import { getMapSummary, getWeatherCuration, simulateCards } from "../api/client";

const router = useRouter();
const KAKAO_JAVASCRIPT_KEY = import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY;
const DEFAULT_CENTER = { lat: 37.4979, lng: 127.0276, label: "강남역" };
const BACKEND_ORIGIN = import.meta.env.VITE_BACKEND_ORIGIN || "http://127.0.0.1:8001";

const categoryOrder = [
  { key: "cafe", label: "카페" },
  { key: "convenience", label: "편의점" },
  { key: "dining", label: "외식" },
  { key: "delivery", label: "배달" },
  { key: "mart", label: "마트" },
  { key: "shopping", label: "쇼핑" },
  { key: "etc", label: "기타" },
];

const categoryLabels = Object.fromEntries(categoryOrder.map((item) => [item.key, item.label]));
const categoryIcons = {
  cafe: "☕",
  convenience: "🏪",
  dining: "🍽️",
  delivery: "🛵",
  mart: "🛒",
  shopping: "🛍️",
  etc: "✨",
};
const focusKeyAliases = {
  cafe: "cafe",
  편의점: "convenience",
  convenience: "convenience",
  외식: "dining",
  dining: "dining",
  food: "dining",
  배달: "delivery",
  delivery: "delivery",
  마트: "mart",
  mart: "mart",
  쇼핑: "shopping",
  shopping: "shopping",
  기타: "etc",
  etc: "etc",
};

const mapElement = ref(null);
const resultSection = ref(null);
const map = ref({ infrastructure: [], markers: [], center: DEFAULT_CENTER });
const weather = ref({ temperature_celsius: 0, condition: "", message: "" });
const mapError = ref("");
const loading = ref(false);
const recommending = ref(false);
const selectedPoint = reactive({ lat: DEFAULT_CENTER.lat, lng: DEFAULT_CENTER.lng });
const recommendationResult = ref(null);
const activeCategory = ref("cafe");
const recommendationType = ref("credit");
const activeSlideIndex = ref(0);

let kakaoMap = null;
let kakaoApi = null;
let circleOverlay = null;
let centerOverlay = null;
let markerOverlays = [];

const markerColors = {
  convenience: "#0f8b6d",
  cafe: "#2a5bd7",
  mart: "#e68600",
  food: "#7a4dd8",
};

function loadKakaoSdk() {
  if (!KAKAO_JAVASCRIPT_KEY) {
    return Promise.reject(new Error("VITE_KAKAO_JAVASCRIPT_KEY가 필요합니다."));
  }

  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao);
  }

  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector("script[data-kakao-map-sdk]");
    if (existingScript) {
      existingScript.addEventListener(
        "load",
        () => window.kakao.maps.load(() => resolve(window.kakao)),
        { once: true },
      );
      existingScript.addEventListener(
        "error",
        () => reject(new Error("Kakao Maps SDK를 불러오지 못했습니다.")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.dataset.kakaoMapSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_JAVASCRIPT_KEY}&autoload=false`;
    script.async = true;
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao));
    script.onerror = () =>
      reject(new Error("Kakao Maps JavaScript SDK 등록에 실패했습니다."));
    document.head.appendChild(script);
  });
}

function clearOverlays() {
  circleOverlay?.setMap(null);
  centerOverlay?.setMap(null);
  markerOverlays.forEach((overlay) => overlay.setMap(null));
  circleOverlay = null;
  centerOverlay = null;
  markerOverlays = [];
}

function createMarkerOverlay(marker) {
  const position = new kakaoApi.maps.LatLng(marker.lat, marker.lng);
  const content = document.createElement("button");
  content.type = "button";
  content.className = "kakao-marker";
  content.style.background = markerColors[marker.category] || "#0f8b6d";
  content.title = marker.name || marker.category;

  return new kakaoApi.maps.CustomOverlay({
    position,
    content,
    yAnchor: 0.5,
    xAnchor: 0.5,
  });
}

function drawAnalysisOnMap() {
  const center = map.value.center || DEFAULT_CENTER;
  const centerLatLng = new kakaoApi.maps.LatLng(center.lat, center.lng);

  if (!kakaoMap) {
    kakaoMap = new kakaoApi.maps.Map(mapElement.value, {
      center: centerLatLng,
      level: 4,
    });

    kakaoApi.maps.event.addListener(kakaoMap, "click", (event) => {
      const latLng = event.latLng;
      loadMapAt({
        lat: latLng.getLat(),
        lng: latLng.getLng(),
        label: "선택 위치",
      });
    });
  } else {
    kakaoMap.setCenter(centerLatLng);
  }

  clearOverlays();

  circleOverlay = new kakaoApi.maps.Circle({
    center: centerLatLng,
    radius: map.value.radius || 500,
    strokeWeight: 2,
    strokeColor: "#0f8b6d",
    strokeOpacity: 0.85,
    strokeStyle: "dashed",
    fillColor: "#0f8b6d",
    fillOpacity: 0.08,
  });
  circleOverlay.setMap(kakaoMap);

  centerOverlay = new kakaoApi.maps.CustomOverlay({
    position: centerLatLng,
    content: `<div class="kakao-center-label">${center.label || "선택 위치"} 중심</div>`,
    yAnchor: 1.4,
  });
  centerOverlay.setMap(kakaoMap);

  markerOverlays = (map.value.markers || []).map(createMarkerOverlay);
  markerOverlays.forEach((overlay) => overlay.setMap(kakaoMap));
}

async function loadMapAt(point = DEFAULT_CENTER) {
  mapError.value = "";
  loading.value = true;
  selectedPoint.lat = Number(point.lat);
  selectedPoint.lng = Number(point.lng);

  try {
    const nextMap = await getMapSummary({
      lat: selectedPoint.lat,
      lng: selectedPoint.lng,
      radius: 500,
    });

    map.value = {
      ...nextMap,
      center: {
        ...(nextMap.center || {}),
        lat: selectedPoint.lat,
        lng: selectedPoint.lng,
        label: point.label || "선택 위치",
      },
    };

    localStorage.setItem("seulpick:last-map-summary", JSON.stringify(map.value));

    await nextTick();
    kakaoApi = await loadKakaoSdk();
    drawAnalysisOnMap();
  } catch (error) {
    mapError.value = error.message || "지도 초기화 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
}

function safeParse(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function resolveImageUrl(value) {
  const src = String(value || "").trim();
  if (!src) return "";
  if (/^https?:\/\//i.test(src)) return src;
  if (src.startsWith("/media/")) return `${BACKEND_ORIGIN}${src}`;
  if (src.startsWith("media/")) return `${BACKEND_ORIGIN}/${src}`;
  return src;
}

function formatWon(value) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString()}원`;
}

function formatScore(value) {
  const score = Number(value || 0);
  return score ? score.toFixed(1) : "0.0";
}

function initials(value) {
  const text = String(value || "").trim();
  if (!text) return "SP";
  const parts = text.split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function normalizeFocus(focus) {
  if (Array.isArray(focus)) {
    return focus
      .map((item) => {
        const key = String(item || "").trim();
        if (!key) return "";
        return focusKeyAliases[key] || focusKeyAliases[key.toLowerCase()] || key;
      })
      .filter(Boolean);
  }
  if (typeof focus === "string" && focus.trim()) {
    return focus
      .split(/[,\s/·]+/)
      .map((item) => {
        const key = item.trim();
        if (!key) return "";
        return focusKeyAliases[key] || focusKeyAliases[key.toLowerCase()] || key;
      })
      .filter(Boolean);
  }
  return [];
}

function cardTypeClass(cardType) {
  return cardType === "debit" ? "debit" : "credit";
}

function cardTypeLabel(cardType) {
  return cardType === "debit" ? "체크카드" : "신용카드";
}

function categoryIcon(key) {
  return categoryIcons[key] || "•";
}

function sortCards(list) {
  return [...list].sort((left, right) => {
    const scoreDiff = Number(right.seul_score || 0) - Number(left.seul_score || 0);
    if (scoreDiff) return scoreDiff;
    const valueDiff =
      Number(right.estimated_net_value || 0) - Number(left.estimated_net_value || 0);
    if (valueDiff) return valueDiff;
    const savingsDiff =
      Number(right.estimated_savings || 0) - Number(left.estimated_savings || 0);
    if (savingsDiff) return savingsDiff;
    return Number(left.rank || 0) - Number(right.rank || 0);
  });
}

function benefitEntry(card, categoryKey) {
  const breakdown = Array.isArray(card.calculation_breakdown) ? card.calculation_breakdown : [];
  return breakdown.find((item) => item.category === categoryKey) || breakdown[0] || null;
}

function benefitHeadline(card, categoryKey) {
  const target = benefitEntry(card, categoryKey);
  if (!target) {
    return "혜택 정보가 없습니다.";
  }

  const categoryLabel = target.category_label || categoryLabels[categoryKey] || categoryKey;
  if (target.discount_type === "amount") {
    const cap = target.category_monthly_limit != null ? ` · 월 한도 ${formatWon(target.category_monthly_limit)}` : "";
    return `${categoryLabel} ${formatWon(target.discount_amount)} 정액 할인${cap}`;
  }

  const rate = Number(target.discount_rate || 0) * 100;
  const rateLabel = rate > 0 ? `${rate.toFixed(rate % 1 ? 1 : 0)}% 할인` : "할인";
  const limitLabel =
    target.category_monthly_limit != null ? ` · 월 한도 ${formatWon(target.category_monthly_limit)}` : "";
  return `${categoryLabel} ${rateLabel}${limitLabel}`;
}

function benefitDetails(card, categoryKey) {
  const target = benefitEntry(card, categoryKey);
  if (!target) return ["카테고리 혜택 정보가 없습니다."];

  const lines = [];
  lines.push(`${target.category_label || categoryLabels[categoryKey] || categoryKey} 혜택`);
  if (target.benefit_group) {
    lines.push(`혜택 그룹 ${target.benefit_group}`);
  }
  if (target.final_benefit != null) {
    lines.push(`예상 혜택 ${formatWon(target.final_benefit)}`);
  }
  if (target.expected_spend != null) {
    lines.push(`예상 사용액 ${formatWon(target.expected_spend)}`);
  }
  if (target.category_monthly_limit != null) {
    lines.push(`월 한도 ${formatWon(target.category_monthly_limit)}`);
  }
  if (target.minimum_transaction_amount) {
    lines.push("전월 실적 및 결제 조건 반영");
  }
  if (card.previous_month_requirement != null) {
    lines.push(`전월 실적 ${formatWon(card.previous_month_requirement)} 이상`);
  }
  if (card.annual_fee != null) {
    lines.push(`연회비 ${formatWon(card.annual_fee)}`);
  }
  if (target.channel && target.channel !== "all") {
    lines.push(target.channel === "offline" ? "오프라인 사용" : `${target.channel} 사용`);
  }
  if (Array.isArray(target.merchant_scope) && target.merchant_scope.length) {
    lines.push(`가맹점 범위 ${target.merchant_scope.slice(0, 2).join(" · ")}`);
  }
  return lines.slice(0, 7);
}

function slideNumber(index, length) {
  return String(Math.min(Number(index) + 1, length)).padStart(2, "0");
}

function moveSlide(step) {
  const slides = activeSlides.value;
  if (!slides.length) return;
  activeSlideIndex.value = (activeSlideIndex.value + step + slides.length) % slides.length;
}

const rankingCards = computed(() => {
  const ranking = recommendationResult.value?.card_ranking_list || [];
  return ranking.map((card, index) => ({
    ...card,
    rank: index + 1,
    focus: normalizeFocus(card.focus),
    card_type: card.card_type || "credit",
    estimated_savings: Number(card.estimated_savings || 0),
    estimated_net_value: Number(card.estimated_net_value || 0),
    seul_score: Number(card.seul_score || 0),
    local_fit_score: Number(card.local_fit_score || 0),
    image_url: resolveImageUrl(card.image_url || ""),
    is_owned: Boolean(card.is_owned),
    calculation_breakdown: Array.isArray(card.calculation_breakdown) ? card.calculation_breakdown : [],
  }));
});

const categoryBuckets = computed(() => {
  const buckets = Object.fromEntries(
    categoryOrder.map((item) => [
      item.key,
      { key: item.key, label: item.label, credit: [], debit: [], all: [] },
    ]),
  );

  for (const card of rankingCards.value) {
    const focusList = card.focus.length ? card.focus : ["etc"];
    for (const focus of focusList) {
      if (!buckets[focus]) continue;
      buckets[focus].all.push(card);
      buckets[focus][card.card_type === "debit" ? "debit" : "credit"].push(card);
    }
  }

  for (const bucket of Object.values(buckets)) {
    bucket.credit = sortCards(bucket.credit);
    bucket.debit = sortCards(bucket.debit);
    bucket.all = sortCards(bucket.all);
  }

  return buckets;
});

const categorySummary = computed(() =>
  categoryOrder.map((item) => {
    const bucket = categoryBuckets.value[item.key] || {
      credit: [],
      debit: [],
      all: [],
    };
    return {
      key: item.key,
      label: item.label,
      creditCount: bucket.credit.length,
      debitCount: bucket.debit.length,
      totalCount: bucket.all.length,
    };
  }),
);

const visibleCategories = computed(() => categorySummary.value.filter((item) => item.totalCount > 0));

watch(
  categorySummary,
  (items) => {
    const nextActive =
      items.find((item) => item.key === activeCategory.value && item.totalCount > 0)?.key ||
      items.find((item) => item.totalCount > 0)?.key ||
      items[0]?.key ||
      "cafe";
    activeCategory.value = nextActive;
  },
  { immediate: true },
);

const selectedCategoryKey = computed(() => activeCategory.value || "cafe");
const selectedCategoryLabel = computed(() => categoryLabels[selectedCategoryKey.value] || "카테고리");
const selectedBucket = computed(
  () =>
    categoryBuckets.value[selectedCategoryKey.value] || {
      credit: [],
      debit: [],
      all: [],
    },
);

const activeSlides = computed(() =>
  recommendationType.value === "credit" ? selectedBucket.value.credit.slice(0, 3) : selectedBucket.value.debit.slice(0, 3),
);
const currentCard = computed(() => activeSlides.value[activeSlideIndex.value] || activeSlides.value[0] || {});
const hasRecommendationResult = computed(() => rankingCards.value.length > 0);
const recommendationLocationLabel = computed(
  () => recommendationResult.value?.center?.label || map.value.center?.label || DEFAULT_CENTER.label,
);

watch(
  selectedCategoryKey,
  () => {
    activeSlideIndex.value = 0;
  },
);

watch(
  recommendationType,
  () => {
    activeSlideIndex.value = 0;
  },
);

watch(
  recommendationResult,
  async (value) => {
    if (!value) return;
    const nextCategory = categorySummary.value.find((item) => item.totalCount > 0)?.key || "cafe";
    activeCategory.value = nextCategory;
    recommendationType.value = "credit";
    await nextTick();
    resultSection.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  },
);

function goDashboard() {
  router.push("/dashboard");
}

async function runRecommendation() {
  recommending.value = true;
  mapError.value = "";
  try {
    const result = await simulateCards({
      infrastructure: map.value.infrastructure || [],
      owned_card_ids: [],
    });
    recommendationResult.value = {
      ...result,
      infrastructure: map.value.infrastructure || [],
      center: map.value.center || DEFAULT_CENTER,
    };
    localStorage.setItem("seulpick:last-simulation", JSON.stringify(recommendationResult.value));
  } catch (error) {
    mapError.value = error.message || "추천 계산에 실패했습니다.";
  } finally {
    recommending.value = false;
  }
}

onMounted(async () => {
  weather.value = await getWeatherCuration();
  const savedSimulation = localStorage.getItem("seulpick:last-simulation");
  if (savedSimulation) {
    recommendationResult.value = safeParse(savedSimulation);
  }
  await loadMapAt(DEFAULT_CENTER);
});
</script>
