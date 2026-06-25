<template>
  <section class="two-column">
    <div class="stack">
      <div class="search-row">
        <div class="fake-input"><Search :size="15" /> 게시글 검색</div>
        <button class="secondary-button">카드 전체 <ChevronDown :size="14" /></button>
        <button class="primary-button"><Pencil :size="15" /> 글쓰기</button>
      </div>

      <section class="panel">
        <div class="section-head">
          <p class="eyebrow">최신 게시글</p>
          <span class="inline-chip">AI 가이드라인 필터 적용</span>
        </div>
        <article v-for="post in posts" :key="post.id" class="post-card rich">
          <div class="post-title-line">
            <span>{{ post.card }}</span>
            <h3>{{ post.title }}</h3>
          </div>
          <p>{{ post.body }}</p>
          <small>
            {{ post.author }} · {{ post.neighborhood }} · {{ post.created_at }} · 조회 {{ post.views }}
          </small>
        </article>
      </section>

      <section class="panel muted">
        <p class="eyebrow">글쓰기</p>
        <div class="form-grid">
          <label>
            연관 카드
            <div class="fake-input">신한 딥드림 <ChevronDown :size="14" /></div>
          </label>
          <label>
            제목
            <div class="fake-input">강남역 카드 혜택 경험을 공유합니다</div>
          </label>
          <label class="full">
            본문
            <div class="textarea-box">직접 사용해본 경험을 바탕으로...</div>
          </label>
        </div>
        <div class="guardrail-banner">
          <ShieldCheck :size="16" />
          <span>AI 가이드라인 준수 확인 · FastAPI Guardrail 자동 감지</span>
        </div>
        <div class="button-row">
          <button class="primary-button">등록</button>
          <button class="secondary-button">취소</button>
        </div>
      </section>
    </div>

    <aside class="stack">
      <section class="panel">
        <p class="eyebrow">인기 동네</p>
        <div v-for="item in neighborhoods" :key="item.name" class="side-stat">
          <span>{{ item.name }}</span>
          <strong>{{ item.count }}</strong>
        </div>
      </section>

      <section class="panel">
        <p class="eyebrow">인기 카드</p>
        <div v-for="item in popularCards" :key="item.name" class="side-stat">
          <span>{{ item.name }}</span>
          <strong>{{ item.count }}</strong>
        </div>
      </section>
    </aside>
  </section>
</template>

<script setup>
import { ChevronDown, Pencil, Search, ShieldCheck } from "lucide-vue-next";
import { ref } from "vue";

const posts = ref([
  {
    id: 1,
    card: "신한 딥드림",
    title: "강남 6번출구 GS25 가맹점 분류 오류 제보",
    body: "스타벅스 분류가 CE7이 아닌 FD6으로 잡혀 할인 추정치가 어긋나는 것 같아요. 카드사 문의 전 공유합니다.",
    author: "김커피",
    neighborhood: "강남역",
    created_at: "2분 전",
    views: 142,
  },
  {
    id: 2,
    card: "현대 ZERO",
    title: "이태원 경리단길 카페 혜택 잘 먹히는 곳 목록",
    body: "직접 방문해서 확인한 가맹점 목록입니다. 앤트러사이트, 커피베이 일부 지점은 제외되는 듯합니다.",
    author: "이절약",
    neighborhood: "이태원동",
    created_at: "1시간 전",
    views: 89,
  },
  {
    id: 3,
    card: "삼성 iD ON",
    title: "압구정 CU 편의점 할인 꿀팁",
    body: "삼성 iD ON 기준 월 최대 5천원 한도를 모아서 쓰는 방식이 체감 절감액이 좋았습니다.",
    author: "박실험",
    neighborhood: "압구정",
    created_at: "3시간 전",
    views: 213,
  },
]);

const neighborhoods = [
  { name: "강남역", count: 48 },
  { name: "압구정", count: 31 },
  { name: "이태원동", count: 27 },
];

const popularCards = [
  { name: "신한 딥드림", count: 36 },
  { name: "현대 ZERO", count: 24 },
  { name: "삼성 iD ON", count: 18 },
];
</script>
