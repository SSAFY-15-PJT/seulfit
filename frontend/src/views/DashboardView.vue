<template>
  <section class="dashboard-page dashboard-demo">
    <header class="dashboard-hero panel">
      <div class="hero-copy">
        <p class="eyebrow">카드고릴라 · 카카오 프론트 참고</p>
        <h1>카드 추천 대시보드</h1>
        <p class="hero-lede">
          현재 계산 결과를 카드 이미지, 보유 여부, 카드 타입, 카테고리별 신용/체크
          순위로 나눠서 보여줍니다.
        </p>

        <div class="hero-actions">
          <button class="primary-button" type="button" @click="reloadSimulation">
            <RefreshCw :size="15" />
            결과 다시 불러오기
          </button>
          <button class="secondary-button" type="button" @click="goMap">
            <MapPinned :size="15" />
            지도에서 다시 계산
          </button>
        </div>

        <div class="hero-highlights">
          <div>
            <span>예상 순혜택</span>
            <strong>{{ bestCardSavings }}</strong>
          </div>
          <div>
            <span>Seul-Score</span>
            <strong>{{ seulScoreValue }}</strong>
          </div>
          <div>
            <span>보유 카드</span>
            <strong>{{ ownedCountLabel }}</strong>
          </div>
          <div>
            <span>지역 반영</span>
            <strong>{{ locationStatus }}</strong>
          </div>
        </div>
      </div>

      <div class="hero-card">
        <div class="card-art">
          <img
            v-if="heroImageUrl"
            :src="heroImageUrl"
            :alt="heroCard.name"
            loading="lazy"
          />
          <div v-else class="card-art-placeholder">
            {{ heroInitials }}
          </div>
        </div>

        <div class="card-summary">
          <div class="badge-row">
            <span class="type-pill" :class="cardTypeClass(heroCard.card_type)">
              {{ cardTypeLabel(heroCard.card_type) }}
            </span>
            <span v-if="heroCard.is_owned" class="owned-pill">보유중인 카드</span>
          </div>

          <h2>{{ heroCard.name }}</h2>
          <p class="card-issuer">{{ heroCard.issuer }}</p>

          <div class="focus-tags">
            <span v-for="focus in heroFocusTags" :key="focus">{{ focus }}</span>
          </div>

          <div class="hero-figures">
            <div>
              <span>예상 순혜택</span>
              <strong>{{ formatWon(heroCard.estimated_savings) }}</strong>
            </div>
            <div>
              <span>연회비 차감 후</span>
              <strong>{{ formatWon(heroCard.estimated_net_value) }}</strong>
            </div>
            <div>
              <span>지역 적합도</span>
              <strong>{{ formatScore(heroCard.local_fit_score) }}</strong>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="metric-grid">
      <MetricCard label="예상 순혜택" :value="bestCardSavings" hint="현재 선택 카드 기준" />
      <MetricCard label="Seul-Score" :value="seulScoreValue" hint="추천 종합 점수" />
      <MetricCard label="보유 카드" :value="ownedCountLabel" hint="보유중인 카드 표시" />
    </div>

    <section class="panel category-strip">
      <button
        v-for="item in categorySummary"
        :key="item.key"
        type="button"
        class="category-chip"
        :class="{ active: item.key === activeCategory }"
        @click="activeCategory = item.key"
      >
        <span class="category-chip-icon">{{ categoryIcon(item.key) }}</span>
        <span>{{ item.label }}</span>
      </button>
    </section>

    <div class="rank-page">
      <section class="rank-board">
        <section class="panel">
          <div class="section-head">
            <div>
              <p class="eyebrow">카테고리별 순위</p>
              <h2>{{ selectedCategoryLabel }} 추천 리스트</h2>
            </div>
            <div class="section-hint">{{ selectedCategoryHint }}</div>
          </div>

          <div class="rank-columns">
            <div class="rank-column">
              <div class="column-head">
                <div>
                  <strong>신용카드</strong>
                  <span>{{ selectedBucket.credit.length }}개</span>
                </div>
                <CreditCard :size="16" />
              </div>

              <article
                v-for="(card, index) in selectedBucket.credit.slice(0, 6)"
                :key="`${selectedCategoryKey}-credit-${card.id ?? card.external_id ?? index}`"
                class="card-rank-row"
              >
                <div class="rank-num">{{ index + 1 }}</div>
                <div class="card-thumb">
                <img
                    v-if="card.image_url"
                    :src="card.image_url"
                    :alt="card.name"
                    loading="lazy"
                  />
                  <span v-else>{{ initials(card.name) }}</span>
                </div>
                <div class="card-meta">
                  <div class="card-title-line">
                    <strong>{{ card.name }}</strong>
                    <span v-if="card.is_owned" class="owned-pill">보유중인 카드</span>
                  </div>
                  <span>{{ card.issuer }} · {{ focusLabel(card.focus) }}</span>
                  <p class="recommend-reason">
                    {{ recommendationReason(card, selectedCategoryKey) }}
                  </p>
                  <div class="badge-row">
                    <span class="type-pill credit">신용카드</span>
                    <span class="metric-pill">{{ formatWon(card.estimated_savings) }}</span>
                  </div>
                </div>
                <div class="card-stat">
                  <strong>{{ displayCategoryScore(card, selectedCategoryKey) }}</strong>
                  <small>Score</small>
                </div>
              </article>

              <p v-if="!selectedBucket.credit.length" class="empty-copy">
                이 카테고리의 신용카드 후보가 없습니다.
              </p>
            </div>

            <div class="rank-column">
              <div class="column-head">
                <div>
                  <strong>체크카드</strong>
                  <span>{{ selectedBucket.debit.length }}개</span>
                </div>
                <BadgeCheck :size="16" />
              </div>

              <article
                v-for="(card, index) in selectedBucket.debit.slice(0, 6)"
                :key="`${selectedCategoryKey}-debit-${card.id ?? card.external_id ?? index}`"
                class="card-rank-row"
              >
                <div class="rank-num">{{ index + 1 }}</div>
                <div class="card-thumb">
                  <img
                    v-if="card.image_url"
                    :src="card.image_url"
                    :alt="card.name"
                    loading="lazy"
                  />
                  <span v-else>{{ initials(card.name) }}</span>
                </div>
                <div class="card-meta">
                  <div class="card-title-line">
                    <strong>{{ card.name }}</strong>
                    <span v-if="card.is_owned" class="owned-pill">보유중인 카드</span>
                  </div>
                  <span>{{ card.issuer }} · {{ focusLabel(card.focus) }}</span>
                  <p class="recommend-reason">
                    {{ recommendationReason(card, selectedCategoryKey) }}
                  </p>
                  <div class="badge-row">
                    <span class="type-pill debit">체크카드</span>
                    <span class="metric-pill">{{ formatWon(card.estimated_savings) }}</span>
                  </div>
                </div>
                <div class="card-stat">
                  <strong>{{ displayCategoryScore(card, selectedCategoryKey) }}</strong>
                  <small>Score</small>
                </div>
              </article>

              <p v-if="!selectedBucket.debit.length" class="empty-copy">
                이 카테고리의 체크카드 후보가 없습니다.
              </p>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="section-head">
            <div>
              <p class="eyebrow">전체 순위</p>
              <h2>이번 계산의 상위 카드</h2>
            </div>
          </div>
          <p class="helper-text">{{ summaryHint }}</p>

          <div v-if="topCards.length" class="overview-list">
            <article
              v-for="card in topCards"
              :key="`overview-${card.id ?? card.external_id ?? card.rank}`"
              class="overview-row"
            >
              <div class="rank-num">{{ card.rank }}</div>
              <div class="card-thumb compact">
                <img
                  v-if="card.image_url"
                  :src="card.image_url"
                  :alt="card.name"
                  loading="lazy"
                />
                <span v-else>{{ initials(card.name) }}</span>
              </div>
              <div class="card-meta">
                <div class="card-title-line">
                  <strong>{{ card.name }}</strong>
                  <span v-if="card.is_owned" class="owned-pill">보유중인 카드</span>
                </div>
                <span>{{ card.issuer }} · {{ cardTypeLabel(card.card_type) }}</span>
              </div>
              <div class="card-stat">
                <strong>{{ formatWon(card.estimated_savings) }}</strong>
                <small>{{ formatScore(card.seul_score) }}</small>
              </div>
            </article>
          </div>
          <p v-else class="empty-copy">추천 결과가 없습니다. 지도에서 먼저 계산해 보세요.</p>
        </section>
      </section>

      <aside class="stack">
        <section class="panel">
          <p class="eyebrow">카테고리 분포</p>
          <div v-for="item in categorySummary" :key="item.key" class="side-stat">
            <span>{{ item.label }}</span>
            <strong>{{ item.totalCount }}개</strong>
          </div>
        </section>

        <section class="panel">
          <p class="eyebrow">현재 선택</p>
          <div class="selected-card-mini">
            <div class="selected-card-image">
              <img
                v-if="heroImageUrl"
                :src="heroImageUrl"
                :alt="heroCard.name"
                loading="lazy"
              />
              <span v-else>{{ heroInitials }}</span>
            </div>
            <div class="selected-card-body">
              <div class="badge-row">
                <span class="type-pill" :class="cardTypeClass(heroCard.card_type)">
                  {{ cardTypeLabel(heroCard.card_type) }}
                </span>
                <span v-if="heroCard.is_owned" class="owned-pill">보유중인 카드</span>
              </div>
              <strong>{{ heroCard.name }}</strong>
              <span>{{ heroCard.issuer }}</span>
              <small>{{ focusLabel(heroCard.focus) }}</small>
            </div>
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { BadgeCheck, CreditCard, MapPinned, RefreshCw } from "lucide-vue-next";
import MetricCard from "../components/MetricCard.vue";

const router = useRouter();
const simulation = ref(null);
const activeCategory = ref("all");
const BACKEND_ORIGIN = import.meta.env.VITE_BACKEND_ORIGIN || "http://127.0.0.1:8001";

const categoryOrder = [
  { key: "all", label: "전체" },
  { key: "cafe", label: "카페" },
  { key: "convenience", label: "편의점" },
  { key: "dining", label: "외식" },
  { key: "delivery", label: "배달" },
  { key: "mart", label: "마트" },
  { key: "shopping", label: "쇼핑" },
];

const categoryLabels = Object.fromEntries(
  categoryOrder.map((item) => [item.key, item.label]),
);

const categoryIcons = {
  all: "◎",
  cafe: "☕",
  convenience: "🏪",
  dining: "🍽️",
  delivery: "🛵",
  mart: "🛒",
  shopping: "🛍️",
};

const cardTypeLabels = {
  credit: "신용카드",
  debit: "체크카드",
};

const focusKeyAliases = {
  카페: "cafe",
  cafe: "cafe",
  "카페": "cafe",
  convenience: "convenience",
  "편의점": "convenience",
  dining: "dining",
  food: "dining",
  "외식": "dining",
  delivery: "delivery",
  "배달": "delivery",
  mart: "mart",
  "마트": "mart",
  shopping: "shopping",
  "쇼핑": "shopping",
  etc: "etc",
  "기타": "etc",
};

function safeParse(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function loadSimulation() {
  const saved = localStorage.getItem("seulpick:last-simulation");
  simulation.value = saved ? safeParse(saved) : null;
}

function reloadSimulation() {
  loadSimulation();
}

function goMap() {
  router.push("/map");
}

function formatWon(value) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString()}원`;
}

function formatScore(value) {
  const score = Number(value || 0);
  return score ? score.toFixed(1) : "0.0";
}

function resolveImageUrl(value) {
  const src = String(value || "").trim();
  if (!src) return "";
  if (/^https?:\/\//i.test(src)) return src;
  if (src.startsWith("/media/")) return `${BACKEND_ORIGIN}${src}`;
  if (src.startsWith("media/")) return `${BACKEND_ORIGIN}/${src}`;
  return src;
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

function focusLabel(focus) {
  const labels = normalizeFocus(focus).map((item) => categoryLabels[item] || item);
  return labels.length ? labels.join(" · ") : "카테고리 정보 없음";
}

function cardTypeClass(cardType) {
  return cardType === "debit" ? "debit" : "credit";
}

function cardTypeLabel(cardType) {
  return cardTypeLabels[cardType] || "신용카드";
}

function categoryIcon(key) {
  return categoryIcons[key] || "•";
}

function sortCards(list, categoryKey) {
  return [...list].sort((left, right) => {
    const readinessDiff =
      Number(Boolean(right.is_recommendation_ready)) -
      Number(Boolean(left.is_recommendation_ready));
    if (readinessDiff) return readinessDiff;
    const eligibilityDiff =
      Number(Boolean(right.is_eligible)) - Number(Boolean(left.is_eligible));
    if (eligibilityDiff) return eligibilityDiff;
    if (categoryKey !== "all") {
      const categoryScoreDiff =
        Number(right.category_scores?.[categoryKey]?.category_fit_score || 0) -
        Number(left.category_scores?.[categoryKey]?.category_fit_score || 0);
      if (categoryScoreDiff) return categoryScoreDiff;
    }
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

function displayCategoryScore(card, categoryKey) {
  if (categoryKey === "all") {
    return formatScore(card?.seul_score);
  }
  const categoryScore = card?.category_scores?.[categoryKey]?.category_fit_score;
  return formatScore(categoryScore ?? card?.seul_score);
}

function topBenefitCategory(card) {
  const entries = Object.entries(card?.category_scores || {});
  if (!entries.length) return null;
  return entries.sort(
    ([, left], [, right]) =>
      Number(right?.benefit_potential || 0) - Number(left?.benefit_potential || 0),
  )[0]?.[0];
}

function recommendationReason(card, categoryKey) {
  if (!card) return "추천 근거를 계산 중입니다.";
  if (categoryKey === "all") {
    const topCategory = topBenefitCategory(card);
    const categoryLabel = categoryLabels[topCategory] || "주요 카테고리";
    return `${categoryLabel} 소비와 혜택 구성이 맞고, 월 예상 순혜택 ${formatWon(card.estimated_net_value)} 기준으로 상위에 올랐습니다.`;
  }
  const score = card.category_scores?.[categoryKey]?.category_fit_score;
  return `${categoryLabels[categoryKey] || categoryKey} 혜택 점수 ${formatScore(score)}점과 예상 순혜택 ${formatWon(card.estimated_net_value)}를 함께 반영했습니다.`;
}

const rankingCards = computed(() => {
  const ranking = simulation.value?.card_ranking_list || [];
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
    category_scores:
      card.category_scores && typeof card.category_scores === "object"
        ? card.category_scores
        : {},
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
    buckets.all.all.push(card);
    buckets.all[card.card_type === "debit" ? "debit" : "credit"].push(card);
    const focusList = card.focus.length ? card.focus : [];
    for (const focus of focusList) {
      if (!buckets[focus]) continue;
      buckets[focus].all.push(card);
      buckets[focus][card.card_type === "debit" ? "debit" : "credit"].push(card);
    }
  }

  for (const bucket of Object.values(buckets)) {
    bucket.credit = sortCards(bucket.credit, bucket.key);
    bucket.debit = sortCards(bucket.debit, bucket.key);
    bucket.all = sortCards(bucket.all, bucket.key);
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

watch(
  categorySummary,
  (items) => {
    const nextActive = items.find((item) => item.key === activeCategory.value)
      ? activeCategory.value
      : items.find((item) => item.totalCount > 0)?.key || items[0]?.key || "cafe";
    activeCategory.value = nextActive;
  },
  { immediate: true },
);

const selectedCategoryKey = computed(() => activeCategory.value || "all");
const selectedCategoryLabel = computed(
  () => categoryLabels[selectedCategoryKey.value] || "카테고리",
);
const selectedBucket = computed(
  () =>
    categoryBuckets.value[selectedCategoryKey.value] || {
      credit: [],
      debit: [],
      all: [],
    },
);

const topCards = computed(() => rankingCards.value.slice(0, 5));
const heroCard = computed(
  () =>
    topCards.value.find((card) => card.image_url) ||
    topCards.value[0] ||
    { name: "", issuer: "", focus: [] },
);
const heroFocusTags = computed(() =>
  normalizeFocus(heroCard.value.focus).slice(0, 3).map((item) => categoryLabels[item] || item),
);

const heroInitials = computed(() => initials(heroCard.value.name));
const heroImageUrl = computed(() => resolveImageUrl(heroCard.value.image_url));
const heroDescription = computed(() => {
  if (!rankingCards.value.length) {
    return "지도에서 위치를 계산한 뒤 카드고릴라 스타일의 카드 비교 화면을 여기서 확인할 수 있습니다.";
  }
  return `${selectedCategoryLabel.value} 기준으로 신용카드와 체크카드 순위를 함께 비교합니다.`;
});

const bestCardSavings = computed(() =>
  heroCard.value?.estimated_savings ? formatWon(heroCard.value.estimated_savings) : "0원",
);
const seulScoreValue = computed(() => formatScore(heroCard.value?.seul_score));
const ownedCountLabel = computed(() => `${rankingCards.value.filter((card) => card.is_owned).length}장`);
const selectedCategoryHint = computed(
  () =>
    selectedCategoryKey.value === "all"
      ? "전체 추천 산식으로 신용카드와 체크카드를 나눠 봅니다."
      : `${selectedCategoryLabel.value} 카테고리에서 신용카드와 체크카드를 나눠 봅니다.`,
);

const locationStatus = computed(() =>
  simulation.value?.infrastructure?.length ? "반영됨" : "기본값",
);

const summaryHint = computed(() => {
  if (!rankingCards.value.length) {
    return "추천 데이터가 없으면 기본 예시를 보여줍니다.";
  }
  return `현재 ${selectedCategoryLabel.value}에서 ${selectedBucket.value.credit.length + selectedBucket.value.debit.length}개 카드가 비교됩니다.`;
});

onMounted(loadSimulation);
</script>
