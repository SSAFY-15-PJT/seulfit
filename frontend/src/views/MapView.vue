<template>
  <section class="map-layout">
    <div class="sidebar">
      <div class="panel">
        <p class="eyebrow">날씨 AI 큐레이션</p>
        <div class="weather-box">
          <Sun class="icon-lg" />
          <div>
            <strong>{{ weather.temperature_celsius }}°C · {{ weather.condition }}</strong>
            <p>{{ weather.message }}</p>
          </div>
        </div>
      </div>

      <div class="panel">
        <p class="eyebrow">상권 분석 요약</p>
        <span class="zone-badge">{{ map.zone_type || "분석 대기" }}</span>
        <div v-if="map.source" class="source-badge">
          {{ map.source === "kakao" ? "Kakao Local API 연동" : "Mock 데이터 표시" }}
        </div>
        <p class="selected-point">
          선택 좌표: {{ selectedPoint.lat.toFixed(5) }}, {{ selectedPoint.lng.toFixed(5) }}
        </p>
        <div v-for="item in map.infrastructure" :key="item.code" class="info-row">
          <span>{{ item.category }} ({{ item.code }})</span>
          <strong>
            {{ item.count }}곳
            <small v-if="item.walk_minutes">도보 {{ item.walk_minutes }}분</small>
          </strong>
        </div>
        <button class="primary-button" @click="goDashboard">카드 시뮬레이션 시작</button>
      </div>
    </div>

    <div class="map-panel">
      <div class="search-row">
        <div class="fake-input"><Search :size="15" /> 지도를 클릭하면 해당 위치의 상권을 다시 분석합니다.</div>
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
        <span><i class="dot food"></i>음식점</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { LocateFixed, Search, Sun } from "lucide-vue-next";
import { getMapSummary, getWeatherCuration } from "../api/client";

const KAKAO_JAVASCRIPT_KEY = import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY;
const DEFAULT_CENTER = { lat: 37.4979, lng: 127.0276, label: "강남역" };

const router = useRouter();
const mapElement = ref(null);
const map = ref({ infrastructure: [], markers: [], center: DEFAULT_CENTER });
const weather = ref({ temperature_celsius: 0, condition: "", message: "" });
const mapError = ref("");
const loading = ref(false);
const selectedPoint = reactive({ lat: DEFAULT_CENTER.lat, lng: DEFAULT_CENTER.lng });

let kakaoMap = null;
let kakaoApi = null;
let circleOverlay = null;
let centerOverlay = null;
let markerOverlays = [];

const markerColors = {
  convenience: "#1d9e75",
  cafe: "#185fa5",
  mart: "#b66a14",
  food: "#7a4dd8",
};

function goDashboard() {
  router.push("/dashboard");
}

function loadKakaoSdk() {
  if (!KAKAO_JAVASCRIPT_KEY) {
    return Promise.reject(new Error("frontend/.env.local에 VITE_KAKAO_JAVASCRIPT_KEY가 필요합니다."));
  }

  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao);
  }

  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector("script[data-kakao-map-sdk]");
    if (existingScript) {
      existingScript.addEventListener("load", () => window.kakao.maps.load(() => resolve(window.kakao)), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Kakao Maps SDK 스크립트 로드 실패")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.dataset.kakaoMapSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_JAVASCRIPT_KEY}&autoload=false`;
    script.async = true;
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao));
    script.onerror = () => reject(new Error("Kakao Maps JavaScript 키 또는 등록 도메인을 확인해주세요."));
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
  content.style.background = markerColors[marker.category] || "#1d9e75";
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
    strokeColor: "#1d9e75",
    strokeOpacity: 0.8,
    strokeStyle: "dashed",
    fillColor: "#1d9e75",
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

    await nextTick();
    kakaoApi = await loadKakaoSdk();
    drawAnalysisOnMap();
  } catch (error) {
    mapError.value = error.message || "지도 초기화 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  weather.value = await getWeatherCuration();
  await loadMapAt(DEFAULT_CENTER);
});
</script>
