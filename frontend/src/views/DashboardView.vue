<template>
  <section class="dashboard-page">
    <div class="notice-banner">
      <ScanLine :size="17" />
      <span>실제 추천 결과가 저장되어 있으면 여기에서 반영됩니다.</span>
    </div>

    <div class="metric-grid">
      <MetricCard label="예상 순혜택" :value="bestCardSavings" hint="현재 1위 카드 기준" />
      <MetricCard label="Seul-Score" :value="seulScoreValue" hint="현재 1위 카드 기준" />
      <MetricCard label="위치 반영" :value="locationStatus" hint="지도 상권 요약 반영 여부" />
    </div>

    <div class="two-column">
      <div class="stack">
        <section class="panel">
          <p class="eyebrow">
            카테고리별 예상 소비
            <span class="inline-chip">추천 입력</span>
          </p>
          <div v-for="item in spending" :key="item.label" class="slider-row rich">
            <span>{{ item.label }}</span>
            <div class="bar"><i :style="{ width: item.percent + '%' }"></i></div>
            <strong>{{ item.amount.toLocaleString() }}</strong>
          </div>
          <p class="helper-text">지도 상권 데이터가 있으면 추천 점수에 함께 반영됩니다.</p>
        </section>

        <section class="panel">
          <p class="eyebrow">카드별 예상 순위</p>
          <div class="bar-chart">
            <div
              v-for="card in chartCards"
              :key="card.name"
              :class="{ highlight: card.rank === 1 }"
              :style="{ height: card.height + '%' }"
            >
              <span>{{ card.name }}</span>
            </div>
          </div>
        </section>
      </div>

      <aside class="stack">
        <section class="panel">
          <p class="eyebrow">카드 추천 랭킹</p>
          <p class="helper-text">{{ summaryHint }}</p>
          <div v-for="card in cards" :key="card.name" class="rank-row detailed">
            <b>{{ card.rank }}</b>
            <div>
              <strong>{{ card.name }}</strong>
              <span>{{ card.issuer }} · {{ card.focus }}</span>
            </div>
            <em>-{{ card.savings.toLocaleString() }}원 <small>Score {{ card.score }}</small></em>
          </div>
        </section>

        <section class="panel">
          <p class="eyebrow">Seul-Score 구성</p>
          <div v-for="factor in scoreFactors" :key="factor.label" class="score-factor">
            <div>
              <span>{{ factor.label }}</span>
              <strong>{{ factor.value }}%</strong>
            </div>
            <div class="bar"><i :style="{ width: factor.value + '%' }"></i></div>
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ScanLine } from "lucide-vue-next";
import MetricCard from "../components/MetricCard.vue";

const defaultSpending = [
  { label: "카페", amount: 102000 },
  { label: "편의점", amount: 58000 },
  { label: "음식점", amount: 183000 },
  { label: "마트", amount: 89000 },
  { label: "쇼핑", amount: 44000 },
];

const defaultCards = [
  { rank: 1, name: "신한 딥드림", issuer: "신한카드", focus: "카페 · 편의점", savings: 24500, score: 92.5, height: 78 },
  { rank: 2, name: "현대 ZERO", issuer: "현대카드", focus: "음식점 · 카페", savings: 17200, score: 78.3, height: 54 },
  { rank: 3, name: "삼성 iD ON", issuer: "삼성카드", focus: "편의점 · 마트", savings: 14800, score: 65.1, height: 46 },
  { rank: 4, name: "KB 꿀팁", issuer: "KB국민카드", focus: "마트 · 쇼핑", savings: 12300, score: 59.2, height: 38 },
  { rank: 5, name: "우리 카드", issuer: "우리카드", focus: "생활 · 음식점", savings: 9800, score: 52.6, height: 30 },
];

const categoryLabels = {
  cafe: "카페",
  convenience: "편의점",
  dining: "음식점",
  food: "음식점",
  mart: "마트",
  shopping: "쇼핑",
  delivery: "배달",
  etc: "기타",
};

const simulation = ref(null);

function loadSimulation() {
  const saved = localStorage.getItem("seulpick:last-simulation");
  if (!saved) return;
  try {
    simulation.value = JSON.parse(saved);
  } catch {
    simulation.value = null;
  }
}

onMounted(loadSimulation);

const bestCard = computed(() => simulation.value?.best_card || null);

const spending = computed(() => {
  const source = simulation.value?.spending || null;
  if (!source) {
    return defaultSpending.map((item, index, items) => ({
      ...item,
      percent: Math.round((item.amount / items.reduce((sum, row) => sum + row.amount, 0)) * 100),
    }));
  }

  const entries = Object.entries(source).map(([key, amount]) => ({
    label: categoryLabels[key] || key,
    amount: Number(amount || 0),
  }));
  const total = entries.reduce((sum, item) => sum + item.amount, 0) || 1;
  return entries.map((item) => ({
    ...item,
    percent: Math.max(6, Math.round((item.amount / total) * 100)),
  }));
});

const cards = computed(() => {
  const ranking = simulation.value?.card_ranking_list || [];
  if (!ranking.length) return defaultCards;
  const topScore = Number(ranking[0]?.seul_score || ranking[0]?.score || 100) || 100;
  return ranking.slice(0, 5).map((card, index) => ({
    rank: index + 1,
    name: card.name,
    issuer: card.issuer,
    focus: Array.isArray(card.focus) ? card.focus.join(" · ") : (card.focus || ""),
    savings: Math.round(card.estimated_savings || 0),
    score: Number(card.seul_score ?? card.score ?? 0),
    height: Math.max(24, Math.round(((Number(card.seul_score ?? card.score ?? 0) || 0) / topScore) * 78)),
  }));
});

const chartCards = computed(() =>
  cards.value.map((card) => ({
    name: card.name,
    rank: card.rank,
    height: card.height,
  }))
);

const bestCardSavings = computed(() => {
  const value = Number(bestCard.value?.estimated_savings || 0);
  return value ? `${value.toLocaleString()}원` : "24,500원";
});

const seulScoreValue = computed(() => {
  const value = Number(bestCard.value?.seul_score || 92.5);
  return value.toFixed(1);
});

const locationStatus = computed(() => (simulation.value?.infrastructure?.length ? "반영됨" : "기본값"));

const summaryHint = computed(() => {
  if (!simulation.value) return "기본 샘플 추천 결과";
  const value = Number(bestCard.value?.estimated_net_value || 0);
  return `위치 반영 순혜택 ${value.toLocaleString()}원`;
});

const scoreFactors = computed(() => {
  if (!bestCard.value) {
    return [
      { label: "카페 가맹점 적합도", value: 90 },
      { label: "편의점 가맹점 적합도", value: 82 },
      { label: "월 순혜택 반영", value: 76 },
    ];
  }

  return [
    { label: "지역 적합도", value: Math.max(0, Math.min(100, Math.round(Number(bestCard.value.local_fit_score || 0)))) },
    { label: "혜택 적합도", value: Math.max(0, Math.min(100, Math.round(Number(bestCard.value.benefit_fit_score || 78)))) },
    { label: "한도 반영", value: Math.max(0, Math.min(100, Math.round(Number(bestCard.value.limit_fit_score || 72)))) },
  ];
});
</script>
