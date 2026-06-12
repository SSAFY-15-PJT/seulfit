<template>
  <section class="receipt-page">
    <div class="stepper">
      <div v-for="(step, index) in steps" :key="step" class="stepper-item">
        <span :class="{ active: index < 3 }">{{ index + 1 }}</span>
        <p>{{ step }}</p>
      </div>
    </div>

    <div class="two-column">
      <div class="stack">
        <section class="panel">
          <p class="eyebrow">소비 내역 이미지 업로드</p>
          <label class="upload-zone">
            <ScanLine :size="38" />
            <strong>입력 없이 3초 만에 끝내기</strong>
            <span>가계부, 종이 영수증, 카드 리포트 캡처를 올려주세요.</span>
            <em>GPT-4o Vision / Gemini Vision 연동 영역</em>
            <input type="file" accept="image/*" @change="onFileChange" />
          </label>
          <div class="button-row">
            <button class="primary-button" :disabled="loading" @click="parseImage">
              <ScanLine :size="15" />
              {{ loading ? "AI가 소비 내역 분석 중..." : "AI로 소비 내역 분석" }}
            </button>
            <button class="secondary-button" @click="useMock">
              <Sparkles :size="15" />
              샘플 적용
            </button>
          </div>
        </section>

        <section class="panel">
          <p class="eyebrow">이미지 미리보기와 파싱 흐름</p>
          <div class="receipt-preview">
            <div class="receipt-paper">
              <span></span>
              <span></span>
              <span class="short"></span>
              <span></span>
              <span class="short"></span>
            </div>
            <small>{{ file?.name || "card-report-capture.png" }}</small>
          </div>
          <div class="parse-arrow">
            <i></i>
            <strong>Image-to-Data OCR</strong>
            <i></i>
          </div>
          <div class="confirm-banner">
            <CheckCircle2 :size="20" />
            <div>
              <strong>분석 결과를 자동 입력했습니다.</strong>
              <p>필요하면 카테고리 금액을 수정한 뒤 카드 추천으로 이동하세요.</p>
            </div>
          </div>
        </section>

        <section class="panel">
          <p class="eyebrow">AI 파싱 결과</p>
          <div v-for="row in parsedRows" :key="row.key" class="parsed-row">
            <span>
              <i :style="{ background: row.color }"></i>
              {{ row.label }}
            </span>
            <strong>{{ row.value.toLocaleString() }}원</strong>
            <small>{{ row.confidence }}%</small>
            <button class="mini-button">수정</button>
          </div>
          <div class="button-row">
            <button class="primary-button wide" @click="recommend">
              <Rocket :size="15" />
              이 데이터로 카드 추천 받기
            </button>
            <button class="secondary-button" @click="useMock">
              <RefreshCw :size="15" />
              재업로드
            </button>
          </div>
          <p class="helper-text">대시보드 슬라이더에 자동 입력되고 Seul-Score가 즉시 계산됩니다.</p>
        </section>
      </div>

      <aside class="stack">
        <section class="panel">
          <p class="eyebrow">지원 이미지 유형</p>
          <div v-for="item in supportedImages" :key="item.title" class="support-card">
            <component :is="item.icon" :size="21" />
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
            </div>
          </div>
        </section>

        <section class="panel muted">
          <p class="eyebrow purple">AI 처리 흐름</p>
          <ol class="flow-list boxed">
            <li>Vue 3에서 이미지 업로드 후 Django로 전송</li>
            <li>GPT-4o Vision API 호출 및 카테고리 추출 프롬프트 주입</li>
            <li>JSON 반환 후 슬라이더 자동 채움</li>
            <li>Seul-Score와 예상 절감액 즉시 계산</li>
          </ol>
          <p class="helper-text">response_format: json_object 강제</p>
        </section>

        <section class="panel">
          <p class="eyebrow">수동 입력과 비교</p>
          <div class="compare-grid">
            <div>
              <FileText :size="22" />
              <strong>수동 입력</strong>
              <span>슬라이더 4개 직접 조작</span>
            </div>
            <div class="active">
              <ScanLine :size="22" />
              <strong>AI 자동 분석</strong>
              <span>이미지 1장으로 즉시 완료</span>
            </div>
          </div>
        </section>

        <section v-if="bestCard" class="result-callout">
          <strong>{{ bestCard.name }}</strong>
          <span>예상 절감 {{ bestCard.estimated_savings.toLocaleString() }}원 · Score {{ bestCard.seul_score }}</span>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import {
  BookOpen,
  CheckCircle2,
  FileText,
  Receipt,
  RefreshCw,
  Rocket,
  ScanLine,
  Smartphone,
  Sparkles,
} from "lucide-vue-next";
import { parseReceiptImage, simulateCards } from "../api/client";

const router = useRouter();
const file = ref(null);
const loading = ref(false);
const spending = ref({ cafe: 102000, convenience: 58000, food: 183000, mart: 89000, shopping: 44000 });
const bestCard = ref(null);

const steps = ["이미지 업로드", "AI 소비 파싱", "결과 확인 · 수정", "카드 추천 바로가기"];
const labels = {
  cafe: { label: "카페", color: "#1d9e75", confidence: 96 },
  convenience: { label: "편의점", color: "#185fa5", confidence: 94 },
  food: { label: "외식", color: "#7a4dd8", confidence: 92 },
  mart: { label: "마트", color: "#b66a14", confidence: 91 },
  shopping: { label: "쇼핑", color: "#d14f7b", confidence: 88 },
};
const supportedImages = [
  { icon: Smartphone, title: "카드 앱 리포트", description: "삼성, 신한, KB, 현대 등 월간 소비 화면" },
  { icon: BookOpen, title: "가계부 앱 화면", description: "뱅크샐러드, 토스, 머니매니저 캡처" },
  { icon: Receipt, title: "종이 영수증 사진", description: "여러 장을 한 번에 촬영한 이미지도 가능" },
];

const parsedRows = computed(() =>
  Object.entries(spending.value).map(([key, value]) => ({
    key,
    value,
    ...labels[key],
  }))
);

function onFileChange(event) {
  file.value = event.target.files?.[0] || null;
}

async function parseImage() {
  loading.value = true;
  try {
    const result = await parseReceiptImage(file.value);
    spending.value = result.spending;
  } finally {
    loading.value = false;
  }
}

function useMock() {
  spending.value = { cafe: 102000, convenience: 58000, food: 183000, mart: 89000, shopping: 44000 };
}

async function recommend() {
  const result = await simulateCards({ spending: spending.value });
  bestCard.value = result.best_card;
  router.push("/dashboard");
}
</script>
