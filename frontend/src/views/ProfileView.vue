<template>
  <section class="two-column">
    <div class="stack">
      <section class="panel">
        <p class="eyebrow">프로필</p>
        <div class="profile-head large">
          <div class="avatar">김</div>
          <div>
            <strong>{{ profile.nickname || "김커피" }}</strong>
            <span>가입일 2025.01.07</span>
            <em><MapPin :size="13" /> {{ profile.home_address || "서울 강남구 역삼동" }}</em>
          </div>
        </div>

        <div class="profile-form">
          <label>
            닉네임
            <div class="fake-input">{{ profile.nickname || "김커피" }}</div>
          </label>
          <label>
            주 생활 주소지
            <div class="fake-input"><MapPin :size="14" /> {{ profile.home_address || "서울 강남구 역삼동" }}</div>
          </label>
          <label>
            프로필 이미지
            <div class="profile-image-row">
              <div class="avatar small">김</div>
              <button class="secondary-button"><Upload :size="15" /> 변경</button>
            </div>
          </label>
        </div>

        <div class="button-row">
          <button class="primary-button">저장</button>
          <button class="secondary-button">비밀번호 변경</button>
        </div>
      </section>
    </div>

    <aside class="stack">
      <section class="panel">
        <p class="eyebrow">관심 카드 설정</p>
        <div v-for="card in interestCards" :key="card.name" class="card-setting">
          <div>
            <strong>{{ card.name }}</strong>
            <span>{{ card.issuer }} · {{ card.focus }}</span>
          </div>
          <span :class="['check-box', { off: !card.enabled }]">
            <Check v-if="card.enabled" :size="12" />
          </span>
        </div>
      </section>

      <section class="panel">
        <p class="eyebrow">내가 쓴 글</p>
        <article v-for="post in myPosts" :key="post.title" class="my-post">
          <h3>{{ post.title }}</h3>
          <div>
            <span>{{ post.card }}</span>
            <small>{{ post.created_at }}</small>
            <button class="secondary-button compact">수정</button>
            <button class="danger-button compact">삭제</button>
          </div>
        </article>
      </section>
    </aside>
  </section>
</template>

<script setup>
import { Check, MapPin, Upload } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { getProfile } from "../api/client";

const profile = ref({
  username: "",
  nickname: "김커피",
  home_address: "서울 강남구 역삼동",
  favorite_cards: [],
  uploaded_report: null,
});

const interestCards = [
  { name: "신한 딥드림", issuer: "신한카드", focus: "카페 · 편의점", enabled: true },
  { name: "현대 ZERO", issuer: "현대카드", focus: "외식", enabled: true },
  { name: "삼성 iD ON", issuer: "삼성카드", focus: "편의점 · 마트", enabled: false },
];

const myPosts = [
  { title: "강남 6번출구 GS25 가맹점 분류 오류 제보", card: "신한 딥드림", created_at: "2분 전" },
  { title: "강남역 신한카드 카페 혜택 총정리", card: "신한 딥드림", created_at: "3일 전" },
];

onMounted(async () => {
  profile.value = { ...profile.value, ...(await getProfile()) };
});
</script>
