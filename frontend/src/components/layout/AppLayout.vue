<template>
  <el-container class="app-layout">
    <el-header :height="'56px'" class="app-header">
      <AppNavbar />
    </el-header>
    <el-container>
      <el-aside width="180px" class="app-aside">
        <AppSidebar />
      </el-aside>
      <el-main class="app-main">
        <router-view v-slot="{ Component, route }">
          <component :is="Component" :key="route.fullPath" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import AppNavbar from './AppNavbar.vue'
import AppSidebar from './AppSidebar.vue'
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-header {
  padding: 0;
}

.app-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
}

.app-main {
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
