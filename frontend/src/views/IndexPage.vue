<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Connection, Reading, TrendCharts, UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const primaryRoute = computed(() => (authStore.isLoggedIn ? '/recommend' : '/login'))
const primaryLabel = computed(() => (authStore.isLoggedIn ? '进入我的推荐' : '去登录'))
const secondaryRoute = computed(() => (authStore.isLoggedIn ? '/posts' : '/register'))
const secondaryLabel = computed(() => (authStore.isLoggedIn ? '浏览帖子广场' : '立即注册'))

const featureCards = computed(() => [
  {
    title: '推荐首页',
    description: authStore.isLoggedIn ? '从个性化推荐开始今天的阅读。' : '登录后先看为你排序的重点内容。',
    icon: Reading,
    route: authStore.isLoggedIn ? '/recommend' : '/login',
    action: authStore.isLoggedIn ? '打开推荐' : '登录后查看',
  },
  {
    title: '热门话题',
    description: '用更短的时间把握社区里正在发生的讨论。',
    icon: TrendCharts,
    route: '/hot',
    action: '查看热门',
  },
  {
    title: '帖子广场',
    description: '按主题继续深入浏览，找到值得展开阅读的内容。',
    icon: Connection,
    route: '/posts',
    action: '浏览帖子',
  },
])

const editorialNotes = computed(() => [
  authStore.isLoggedIn ? `已登录身份：${authStore.username}` : '当前状态：未登录',
  '版式更偏向阅读，而不是控制台面板',
  '绿色作为唯一强调色，降低视觉噪声',
])

function goTo(route) {
  router.push(route)
}

function goToProfile() {
  router.push(`/users/${authStore.userId}`)
}

function logout() {
  authStore.logout()
  router.push('/')
}
</script>

<template>
  <div class="index-page">
    <div class="index-shell">
      <header class="masthead">
        <div class="brand-block">
          <div class="brand-mark">
            <el-icon :size="18"><Connection /></el-icon>
          </div>
          <div class="brand-copy">
            <h1 class="brand-title">知识推荐</h1>
            <p class="brand-subtitle">更清爽的阅读、推荐与讨论入口。</p>
          </div>
        </div>

        <nav class="masthead-nav">
          <el-button text @click="goTo('/posts')">帖子广场</el-button>
          <el-button text @click="goTo('/hot')">热门</el-button>
          <el-button v-if="!authStore.isLoggedIn" type="primary" @click="goTo('/login')">登录</el-button>
          <el-button v-else type="primary" @click="goTo('/recommend')">我的推荐</el-button>
        </nav>
      </header>

      <section class="hero-section">
        <div class="hero-main">
          <span class="hero-kicker">首页</span>
          <h2 class="hero-title">让推荐、阅读与讨论，像翻阅一份更干净的线上刊物。</h2>
          <p class="hero-deck">
            首页不再像一个功能面板，而是一个有节奏的阅读入口。你可以从推荐流开始，也可以直接进入热门话题和帖子广场。
          </p>

          <div class="hero-actions">
            <el-button type="primary" size="large" @click="goTo(primaryRoute)">
              {{ primaryLabel }}
              <el-icon class="button-icon"><ArrowRight /></el-icon>
            </el-button>
            <el-button size="large" plain @click="goTo(secondaryRoute)">
              {{ secondaryLabel }}
            </el-button>
          </div>
        </div>

        <aside class="hero-aside">
          <div v-if="authStore.isLoggedIn" class="account-panel">
            <span class="panel-kicker">我的账号</span>
            <div class="account-head">
              <el-avatar :size="52" :icon="UserFilled" class="account-avatar" />
              <div>
                <strong class="account-name">{{ authStore.username }}</strong>
                <p class="account-note">已登录，可以直接进入你的推荐流或继续管理个人资料。</p>
              </div>
            </div>
            <div class="account-actions">
              <el-button plain @click="goToProfile">个人资料</el-button>
              <el-button text class="logout-button" @click="logout">退出登录</el-button>
            </div>
          </div>

          <div v-else class="account-panel">
            <span class="panel-kicker">开始使用</span>
            <strong class="guest-title">先登录，再开始个性化阅读。</strong>
            <p class="guest-note">注册后可以保存偏好、接收推荐，并围绕主题继续追踪内容。</p>
          </div>

          <div class="edition-panel">
            <span class="panel-kicker">页面说明</span>
            <ul class="note-list">
              <li v-for="note in editorialNotes" :key="note" class="note-item">{{ note }}</li>
            </ul>
          </div>
        </aside>
      </section>

      <section class="feature-section">
        <article
          v-for="item in featureCards"
          :key="item.title"
          class="feature-card"
          @click="goTo(item.route)"
        >
          <div class="feature-top">
            <div class="feature-icon">
              <el-icon :size="18"><component :is="item.icon" /></el-icon>
            </div>
            <span class="feature-kicker">模块</span>
          </div>
          <h3 class="feature-title">{{ item.title }}</h3>
          <p class="feature-text">{{ item.description }}</p>
          <span class="feature-link">
            {{ item.action }}
            <el-icon :size="14"><ArrowRight /></el-icon>
          </span>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.index-page {
  min-height: 100vh;
  padding: 8px 0 32px;
}

.index-shell {
  max-width: 1120px;
  margin: 0 auto;
  display: grid;
  gap: 34px;
}

.masthead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--kr-border);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark,
.feature-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: var(--kr-primary);
  background: var(--kr-primary-soft);
}

.brand-copy {
  display: grid;
  gap: 4px;
}

.brand-title,
.hero-title,
.feature-title,
.account-name,
.guest-title {
  letter-spacing: -0.05em;
}

.brand-title {
  font-size: 1.1rem;
  line-height: 1;
}

.brand-subtitle,
.hero-deck,
.account-note,
.guest-note,
.feature-text,
.note-item {
  color: var(--kr-text-soft);
  line-height: 1.85;
}

.brand-subtitle {
  max-width: 34rem;
  font-size: 0.95rem;
}

.masthead-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.75fr);
  gap: 42px;
  padding-bottom: 36px;
  border-bottom: 1px solid var(--kr-border);
}

.hero-kicker,
.panel-kicker,
.feature-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-text-muted);
}

.hero-title {
  max-width: 11ch;
  font-size: clamp(3.7rem, 8vw, 6.8rem);
  line-height: 0.9;
}

.hero-deck {
  max-width: 43rem;
  margin-top: 20px;
  font-size: 1.05rem;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 32px;
}

.button-icon {
  margin-left: 6px;
}

.hero-aside {
  display: grid;
  gap: 24px;
  align-content: start;
}

.account-panel,
.edition-panel {
  padding-top: 18px;
  border-top: 1px solid var(--kr-border);
}

.account-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.account-avatar {
  background: var(--kr-primary);
}

.account-name,
.guest-title {
  display: block;
  margin-bottom: 6px;
  font-size: clamp(1.5rem, 3vw, 2.15rem);
  line-height: 1;
}

.account-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  flex-wrap: wrap;
}

.logout-button {
  color: var(--kr-danger);
}

.note-list {
  list-style: none;
  display: grid;
  gap: 10px;
}

.note-item {
  position: relative;
  padding-left: 18px;
}

.note-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.78em;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--kr-primary);
}

.feature-section {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
}

.feature-card {
  padding: 0 0 22px;
  border-bottom: 1px solid var(--kr-border);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease;
}

.feature-card:hover {
  transform: translateY(-2px);
  border-color: var(--kr-border-strong);
}

.feature-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.feature-title {
  margin: 18px 0 10px;
  font-size: clamp(1.7rem, 2.8vw, 2.3rem);
  line-height: 1;
}

.feature-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 18px;
  font-weight: 700;
  color: var(--kr-primary-strong);
}

@media (max-width: 980px) {
  .hero-section,
  .feature-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .masthead,
  .masthead-nav,
  .hero-actions,
  .account-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-title {
    max-width: none;
  }
}
</style>
