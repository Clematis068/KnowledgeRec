<template>
  <div class="app-layout">
    <header class="app-header">
      <AppNavbar />
    </header>

    <div class="app-body">
      <aside class="app-aside">
        <AppSidebar />
      </aside>

      <main class="app-main">
        <div class="app-main-inner">
          <router-view v-slot="{ Component, route }">
            <component :is="Component" :key="route.fullPath" />
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import AppNavbar from './AppNavbar.vue'
import AppSidebar from './AppSidebar.vue'
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  padding: 16px;
}

.app-header {
  position: sticky;
  top: 16px;
  z-index: 30;
  margin-bottom: 16px;
}

.app-body {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.app-aside {
  position: sticky;
  top: 96px;
}

.app-main {
  min-width: 0;
}

.app-main-inner {
  min-height: calc(100vh - 120px);
  padding: 28px;
  border: 1px solid rgba(124, 58, 237, 0.12);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.62);
  box-shadow: 0 18px 48px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

@media (max-width: 1100px) {
  .app-body {
    grid-template-columns: 1fr;
  }

  .app-aside,
  .app-header {
    position: static;
  }

  .app-main-inner {
    padding: 20px;
  }
}
</style>
