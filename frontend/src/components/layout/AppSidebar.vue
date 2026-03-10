<template>
  <div class="sidebar-shell">
    <div class="sidebar-heading">
      <span class="sidebar-kicker">Browse</span>
      <h2>社区导航</h2>
      <p>推荐、热门、广场、创作。</p>
    </div>

    <el-menu :default-active="activeMenu" :router="true" class="sidebar-menu">
      <el-menu-item index="/recommend">
        <el-icon><Star /></el-icon>
        <span>智能推荐</span>
      </el-menu-item>
      <el-menu-item index="/hot">
        <el-icon><TrendCharts /></el-icon>
        <span>热门趋势</span>
      </el-menu-item>
      <el-menu-item index="/posts">
        <el-icon><Document /></el-icon>
        <span>帖子广场</span>
      </el-menu-item>
      <el-menu-item index="/create-post">
        <el-icon><EditPen /></el-icon>
        <span>发布内容</span>
      </el-menu-item>
      <el-menu-item index="/my-posts">
        <el-icon><Files /></el-icon>
        <span>我的发帖</span>
      </el-menu-item>
    </el-menu>

    <div class="sidebar-note">
      <span class="note-label">Tip</span>
      <h3>先推荐，后热门。</h3>
      <p>想定点找内容时，再用搜索。</p>
      <button type="button" class="note-link" @click="focusSearch">去搜索</button>
    </div>
  </div>
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
  if (path.startsWith('/my-posts')) return '/my-posts'
  return path
})

function focusSearch() {
  window.dispatchEvent(new CustomEvent('app:focus-search'))
}
</script>

<style scoped>
.sidebar-shell {
  padding: 24px;
  border: 1px solid rgba(124, 58, 237, 0.12);
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 18px 44px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

.sidebar-heading {
  margin-bottom: 20px;
}

.sidebar-kicker,
.note-label {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.sidebar-heading h2,
.sidebar-note h3 {
  margin-bottom: 8px;
  font-size: 24px;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.sidebar-heading p,
.sidebar-note p {
  color: var(--kr-text-soft);
  line-height: 1.7;
}

.sidebar-menu {
  margin-bottom: 18px;
}

.sidebar-note {
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(124, 58, 237, 0.1), rgba(124, 58, 237, 0.02));
}

.note-link {
  display: inline-flex;
  margin-top: 14px;
  border: none;
  padding: 0;
  background: transparent;
  font-weight: 600;
  color: var(--kr-primary-strong);
}
</style>
