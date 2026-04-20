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
  background: transparent;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background: var(--cds-background);
  border-bottom: 1px solid var(--cds-border-subtle);
}

.app-body {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
  max-width: var(--cds-layout-max-width);
  margin: 0 auto;
  padding: 32px;
}

.app-aside {
  position: sticky;
  top: 96px;
  min-height: calc(100vh - 96px);
  padding: 8px 24px 0 0;
  border-right: 1px solid var(--cds-border-subtle);
}

.app-main {
  min-width: 0;
}

.app-main-inner {
  min-height: calc(100vh - 96px);
  padding: 0 0 48px;
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
    padding: 0 0 20px;
    border-right: none;
    border-bottom: 1px solid var(--cds-border-subtle);
  }

  .app-main-inner {
    padding: 0 0 24px;
  }
}

@media (max-width: 768px) {
  .app-body {
    padding: 20px 16px 24px;
  }
}
</style>
