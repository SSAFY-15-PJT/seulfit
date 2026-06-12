<template>
  <section class="dashboard-page">
    <div class="notice-banner">
      <ScanLine :size="17" />
      <span>영수증 AI 분석 결과가 자동으로 반영되었습니다. 슬라이더를 조정해 추가 시뮬레이션할 수 있습니다.</span>
    </div>

    <div class="metric-grid">
      <MetricCard label="이번 달 예상 절감액" value="24,500원" hint="강남역 기준" />
      <MetricCard label="Seul-Score" value="92.5" hint="1위 카드 기준" />
      <MetricCard label="실제 소비 합계" value="476,000원" hint="AI 파싱 데이터 기준" />
    </div>

    <div class="two-column">
      <div class="stack">
        <section class="panel">
          <p class="eyebrow">
            카테고리별 예상 소비
            <span class="inline-chip">AI 자동 입력</span>
          </p>
          <div v-for="item in spending" :key="item.label" class="slider-row rich">
            <span>{{ item.label }}</span>
            <div class="bar"><i :style="{ width: item.percent + '%' }"></i></div>
            <strong>{{ item.amount.toLocaleString() }}</strong>
          </div>
          <p class="helper-text">슬라이더 조정 시 Seul-Score 재계산 예정</p>
        </section>

        <section class="panel">
          <p class="eyebrow">카드별 예상 실사용 할인액</p>
          <div class="bar-chart">
            <div v-for="card in chartCards" :key="card.name" :class="{ highlight: card.rank === 1 }" :style="{ height: card.height + '%' }">
              <span>{{ card.name }}</span>
            </div>
          </div>
          <p class="helper-text">Apache ECharts 연동 영역 · Seul-Score 기반 정렬</p>
        </section>

        <div class="button-row">
          <button class="primary-button"><Download :size="15" /> 분석 리포트 PNG 저장</button>
          <button class="secondary-button"><ScanLine :size="15" /> 영수증 재분석</button>
          <button class="secondary-button">조건 초기화</button>
        </div>
      </div>

      <aside class="stack">
        <section class="panel">
          <p class="eyebrow">카드 추천 랭킹</p>
          <p class="helper-text">강남역 · 실제 소비 476,000원 기준</p>
          <div v-for="card in cards" :key="card.name" class="rank-row detailed">
            <b>{{ card.rank }}</b>
            <div>
              <strong>{{ card.name }}</strong>
              <span>{{ card.issuer }} · {{ card.focus }}</span>
            </div>
            <em>-{{ card.savings.toLocaleString() }}원<small>Score {{ card.score }}</small></em>
          </div>
        </section>

        <section class="panel">
          <p class="eyebrow">Seul-Score 산출</p>
          <div v-for="factor in scoreFactors" :key="factor.label" class="score-factor">
            <div>
              <span>{{ factor.label }}</span>
              <strong>{{ factor.value }}%</strong>
            </div>
            <div class="bar"><i :style="{ width: factor.value + '%' }"></i></div>
          </div>
          <p class="helper-text">명목 할인율 × tanh(반경 내 가맹점 수 / 2)</p>
        </section>

        <section class="panel muted">
          <p class="eyebrow">날씨 AI 코멘트</p>
          <p class="weather-comment">32.5°C 맑음. 강남역 주변 카페 8곳과 편의점 12곳이 잡혀 오늘은 카페/편의점 혜택 카드의 체감 절감액이 높습니다.</p>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { Download, ScanLine } from "lucide-vue-next";
import MetricCard from "../components/MetricCard.vue";

const spending = [
  { label: "카페", amount: 102000, percent: 60 },
  { label: "편의점", amount: 58000, percent: 33 },
  { label: "외식", amount: 183000, percent: 72 },
  { label: "마트", amount: 89000, percent: 45 },
  { label: "쇼핑", amount: 44000, percent: 28 },
];

const cards = [
  { rank: 1, name: "신한 딥드림", issuer: "신한카드", focus: "카페 · 편의점", savings: 24500, score: 92.5, height: 78 },
  { rank: 2, name: "현대 ZERO", issuer: "현대카드", focus: "외식 · 카페", savings: 17200, score: 78.3, height: 54 },
  { rank: 3, name: "삼성 iD ON", issuer: "삼성카드", focus: "편의점 · 마트", savings: 14800, score: 65.1, height: 46 },
  { rank: 4, name: "KB 탄탄대로", issuer: "KB국민카드", focus: "마트 · 쇼핑", savings: 12300, score: 59.2, height: 38 },
  { rank: 5, name: "우리 카드의정석", issuer: "우리카드", focus: "생활 · 외식", savings: 9800, score: 52.6, height: 30 },
];

const chartCards = cards.map((card) => ({ name: card.name, rank: card.rank, height: card.height }));
const scoreFactors = [
  { label: "카페 가맹점 매칭률", value: 90 },
  { label: "편의점 가맹점 매칭률", value: 82 },
  { label: "소비 패턴 적합도", value: 76 },
];
</script>
