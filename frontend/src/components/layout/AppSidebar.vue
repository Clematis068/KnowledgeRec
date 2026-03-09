<template>
  <el-menu
    :default-active="activeMenu"
    :router="true"
    class="sidebar-menu"
  >
    <el-menu-item index="/recommend">
      <el-icon><Star /></el-icon>
      <span>智能推荐</span>
    </el-menu-item>
    <el-menu-item index="/hot">
      <el-icon><TrendCharts /></el-icon>
      <span>热门</span>
    </el-menu-item>
    <el-menu-item index="/posts">
      <el-icon><Document /></el-icon>
      <span>帖子广场</span>
    </el-menu-item>
    <el-menu-item index="/create-post">
      <el-icon><EditPen /></el-icon>
      <span>发帖</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/recommend')) return '/recommend'
  if (path.startsWith('/hot')) return '/hot'
  if (path.startsWith('/posts')) return '/posts'
  if (path.startsWith('/create-post')) return '/create-post'
  return path
})
</script>

<style scoped>
.sidebar-menu {
  height: 100%;
  border-right: none;
}
</style>
