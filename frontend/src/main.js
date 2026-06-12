import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./styles.css";

import MapView from "./views/MapView.vue";
import ReceiptAnalyzerView from "./views/ReceiptAnalyzerView.vue";
import DashboardView from "./views/DashboardView.vue";
import CommunityView from "./views/CommunityView.vue";
import ProfileView from "./views/ProfileView.vue";

const routes = [
  { path: "/", redirect: "/map" },
  { path: "/map", component: MapView },
  { path: "/receipt", component: ReceiptAnalyzerView },
  { path: "/dashboard", component: DashboardView },
  { path: "/community", component: CommunityView },
  { path: "/profile", component: ProfileView },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

createApp(App).use(router).mount("#app");

