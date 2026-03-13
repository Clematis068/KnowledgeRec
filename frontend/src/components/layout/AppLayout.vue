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
  padding: 0 24px 32px;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(253, 251, 247, 0.94);
  backdrop-filter: blur(12px);
}

.app-body {
  display: grid;
  grid-template-columns: 208px minmax(0, 1fr);
  gap: 0;
  align-items: start;
  max-width: 1440px;
  margin: 0 auto;
}

.app-aside {
  position: sticky;
  top: 84px;
  min-height: calc(100vh - 84px);
  padding: 28px 28px 0 0;
  border-right: 1px solid var(--kr-border);
}

.app-main {
  min-width: 0;
}

.app-main-inner {
  min-height: calc(100vh - 84px);
  padding: 0 0 40px 40px;
}

@media (max-width: 1180px) {
  .app-body {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .app-aside,
  .app-header {
    position: static;
  }

  .app-aside {
    min-height: auto;
    padding: 12px 0 0;
    border-right: none;
    border-bottom: 1px solid var(--kr-border);
  }

  .app-main-inner {
    padding: 0 0 24px;
  }
}

@media (max-width: 768px) {
  .app-layout {
    padding: 0 16px 24px;
  }
}
</style>
