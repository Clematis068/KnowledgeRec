<template>
  <div class="sidebar-shell">
    <nav class="nav-group">
      <button
        v-for="item in primaryLinks"
        :key="item.key"
        type="button"
        :class="['nav-item', { 'is-active': isActive(item) }]"
        @click="navigate(item)"
      >
        <span class="nav-icon">
          <el-icon><component :is="item.icon" /></el-icon>
        </span>
        <span class="nav-copy">
          <span class="nav-label">{{ item.label }}</span>
        </span>
      </button>
    </nav>

    <div class="sidebar-divider"></div>

    <section class="sidebar-section">
      <span class="section-title">快捷操作</span>
      <button
        v-for="item in secondaryLinks"
        :key="item.key"
        type="button"
        class="nav-item nav-item--secondary"
        @click="navigate(item)"
      >
        <span class="nav-icon">
          <el-icon><component :is="item.icon" /></el-icon>
        </span>
        <span class="nav-copy">
          <span class="nav-label">{{ item.label }}</span>
        </span>
      </button>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, EditPen, House, Search, TrendCharts, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const primaryLinks = computed(() => [
  {
    key: 'recommend',
    label: '首页',
    subtext: '',
    route: '/recommend',
    icon: House,
  },
  {
    key: 'profile',
    label: '个人资料',
    subtext: '',
    route: authStore.isLoggedIn ? `/users/${authStore.userId}` : '/login',
    icon: User,
  },
  {
    key: 'my-posts',
    label: '我的发帖',
    subtext: '',
    route: authStore.isLoggedIn ? '/my-posts' : '/login',
    icon: Document,
  },
  {
    key: 'hot',
    label: '热门趋势',
    subtext: '',
    route: '/hot',
    icon: TrendCharts,
  },
])

const secondaryLinks = computed(() => [
  {
    key: 'write',
    label: '发布内容',
    subtext: '',
    route: authStore.isLoggedIn ? '/create-post' : '/login',
    icon: EditPen,
  },
  {
    key: 'search',
    label: '搜索',
    subtext: '',
    action: 'focus-search',
    icon: Search,
  },
])

function navigate(item) {
  if (item.action === 'focus-search') {
    window.dispatchEvent(new CustomEvent('app:focus-search'))
    return
  }
  router.push(item.route)
}

function isActive(item) {
  if (item.key === 'profile') return route.path.startsWith('/users')
  if (item.key === 'recommend') return route.path.startsWith('/recommend')
  if (item.key === 'my-posts') return route.path.startsWith('/my-posts')
  if (item.key === 'hot') return route.path.startsWith('/hot')
  return route.path === item.route
}
</script>

<style scoped>
.sidebar-shell {
  display: grid;
  gap: 20px;
  padding-top: 6px;
}

.nav-group,
.sidebar-section {
  display: grid;
  gap: 6px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-text-muted);
}

.sidebar-divider {
  height: 1px;
  background: var(--kr-border);
}

.nav-item {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  width: 100%;
  padding: 10px 0;
  border: none;
  background: transparent;
  color: var(--kr-text-soft);
  text-align: left;
}

.nav-item.is-active {
  color: var(--kr-text);
}

.nav-item.is-active .nav-label {
  font-weight: 800;
}

.nav-item--secondary {
  color: var(--kr-text-muted);
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 18px;
}

.nav-copy {
  display: grid;
  gap: 3px;
}

.nav-label {
  font-size: 1.08rem;
  font-weight: 700;
  line-height: 1.1;
}

.nav-subtext {
  font-size: 13px;
  line-height: 1.5;
  color: var(--kr-text-muted);
}

@media (max-width: 1180px) {
  .sidebar-shell,
  .nav-group,
  .sidebar-section {
    gap: 12px;
  }

  .nav-group,
  .sidebar-section {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .sidebar-divider,
  .section-title {
    display: none;
  }
}
</style>
