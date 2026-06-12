<template>
  <div class="app-shell">
    <AppNav />
    <main class="page">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import AppNav from "./components/AppNav.vue";
</script>

