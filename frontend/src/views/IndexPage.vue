<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Connection,
  Reading,
  Search,
  TrendCharts,
  UserFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const primaryRoute = computed(() => (authStore.isLoggedIn ? '/recommend' : '/register'))
const primaryLabel = computed(() => (authStore.isLoggedIn ? '进入我的推荐' : '注册开始使用'))
const secondaryRoute = computed(() => (authStore.isLoggedIn ? '/hot' : '/login'))
const secondaryLabel = computed(() => (authStore.isLoggedIn ? '查看热门趋势' : '已有账号，去登录'))

const heroBullets = computed(() => [
  '更像阅读入口，而不是堆满按钮的功能页',
  '推荐、热门、搜索三条路径清晰分离',
  authStore.isLoggedIn ? '已登录后可直接进入你的个性化内容流' : '未登录也可以先浏览热门内容与社区方向',
])

const quickLinks = computed(() => [
  {
    title: '推荐首页',
    description: authStore.isLoggedIn ? '直接打开你的个性化推荐流。' : '登录后即可看到为你排序的内容。',
    route: authStore.isLoggedIn ? '/recommend' : '/login',
    action: authStore.isLoggedIn ? '打开推荐' : '登录后查看',
    icon: Reading,
  },
  {
    title: '热门趋势',
    description: '快速把握社区里正在被讨论的内容与帖子。',
    route: '/hot',
    action: '查看热门',
    icon: TrendCharts,
  },
  {
    title: authStore.isLoggedIn ? '个人资料' : '账号入口',
    description: authStore.isLoggedIn ? '管理资料、关注关系与发帖记录。' : '注册后可以保存偏好并追踪自己的阅读行为。',
    route: authStore.isLoggedIn ? `/users/${authStore.userId}` : '/register',
    action: authStore.isLoggedIn ? '打开资料' : '创建账号',
    icon: UserFilled,
  },
])

const editorialSteps = computed(() => [
  {
    index: '01',
    title: '先看方向',
    description: '从热门趋势了解此刻社区在讨论什么，先建立内容地图。',
  },
  {
    index: '02',
    title: '再进推荐',
    description: '登录后进入推荐流，让首页开始围绕你的兴趣排序。',
  },
  {
    index: '03',
    title: '持续追踪',
    description: '进入作者主页、个人资料与发帖记录，形成稳定的阅读路径。',
  },
])

const statusNotes = computed(() => [
  authStore.isLoggedIn ? `当前身份：${authStore.username}` : '当前身份：访客',
  authStore.isLoggedIn ? '推荐流、资料页、我的发帖已可直接访问。' : '推荐流与资料编辑需要登录后使用。',
  '首页已经统一为更克制的编辑化结构。',
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
        <button type="button" class="brand-block" @click="goTo('/')">
          <span class="brand-mark">
            <el-icon :size="18"><Connection /></el-icon>
          </span>
          <span class="brand-copy">
            <strong class="brand-title">知识推荐</strong>
            <span class="brand-subtitle">Knowledge feed, reading and discussion</span>
          </span>
        </button>

        <nav class="masthead-nav">
          <el-button text @click="goTo('/hot')">热门</el-button>
          <el-button text @click="goTo('/search')">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button
            v-if="authStore.isLoggedIn"
            type="primary"
            @click="goTo('/recommend')"
          >
            我的推荐
          </el-button>
          <template v-else>
            <el-button text @click="goTo('/login')">登录</el-button>
            <el-button type="primary" @click="goTo('/register')">注册</el-button>
          </template>
        </nav>
      </header>

      <section class="hero-section">
        <div class="hero-main">
          <span class="section-kicker">首页</span>
          <h1 class="hero-title">把推荐、阅读与讨论，收束成一个更稳定的知识入口。</h1>
          <p class="hero-deck">
            现在的首页不再强调功能堆叠，而是优先呈现阅读路径：先理解内容方向，再进入推荐流，最后沉淀到个人资料与发帖关系里。
          </p>

          <ul class="hero-bullets">
            <li v-for="item in heroBullets" :key="item" class="hero-bullet">
              {{ item }}
            </li>
          </ul>

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

        <aside class="hero-side">
          <section class="surface-card status-card">
            <span class="section-kicker">当前状态</span>

            <template v-if="authStore.isLoggedIn">
              <div class="account-head">
                <el-avatar :size="56" :icon="UserFilled" class="account-avatar" />
                <div class="account-copy">
                  <strong class="account-name">{{ authStore.username }}</strong>
                  <p class="account-note">你已经登录，可以直接进入推荐流、个人资料和我的发帖。</p>
                </div>
              </div>

              <div class="inline-actions">
                <el-button plain @click="goToProfile">个人资料</el-button>
                <el-button text class="danger-action" @click="logout">退出登录</el-button>
              </div>
            </template>

            <template v-else>
              <div class="guest-copy">
                <strong class="guest-title">先注册，再建立你的阅读偏好。</strong>
                <p class="account-note">登录后，你的推荐、收藏和发帖关系会形成一个更连续的内容路径。</p>
              </div>
            </template>

            <ul class="status-list">
              <li v-for="note in statusNotes" :key="note" class="status-item">{{ note }}</li>
            </ul>
          </section>
        </aside>
      </section>

      <section class="link-section">
        <div class="section-head">
          <span class="section-kicker">主要入口</span>
          <h2 class="section-title">三条最常用的进入路径</h2>
        </div>

        <div class="link-grid">
          <article
            v-for="item in quickLinks"
            :key="item.title"
            class="surface-card link-card"
            @click="goTo(item.route)"
          >
            <div class="link-card-top">
              <span class="feature-icon">
                <el-icon :size="18"><component :is="item.icon" /></el-icon>
              </span>
              <span class="micro-label">入口</span>
            </div>

            <h3 class="link-card-title">{{ item.title }}</h3>
            <p class="link-card-text">{{ item.description }}</p>

            <span class="link-card-action">
              {{ item.action }}
              <el-icon :size="14"><ArrowRight /></el-icon>
            </span>
          </article>
        </div>
      </section>

      <section class="editorial-section">
        <div class="section-head">
          <span class="section-kicker">使用方式</span>
          <h2 class="section-title">首页改成了一种更顺手的阅读节奏</h2>
        </div>

        <div class="step-grid">
          <article v-for="item in editorialSteps" :key="item.index" class="step-card">
            <span class="step-index">{{ item.index }}</span>
            <h3 class="step-title">{{ item.title }}</h3>
            <p class="step-text">{{ item.description }}</p>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.index-page {
  min-height: 100vh;
  padding: 12px 0 48px;
}

.index-shell {
  max-width: 1180px;
  margin: 0 auto;
  display: grid;
  gap: 40px;
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
  display: inline-flex;
  align-items: center;
  gap: 14px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--kr-text);
  text-align: left;
}

.brand-mark,
.feature-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  color: var(--kr-primary);
  background: var(--kr-primary-soft);
}

.brand-copy {
  display: grid;
  gap: 3px;
}

.brand-title,
.hero-title,
.section-title,
.link-card-title,
.account-name,
.guest-title,
.step-title {
  letter-spacing: -0.05em;
}

.brand-title {
  font-size: 1.12rem;
  line-height: 1;
}

.brand-subtitle {
  color: var(--kr-text-muted);
  font-size: 0.82rem;
  line-height: 1.4;
}

.masthead-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.28fr) minmax(300px, 0.72fr);
  gap: clamp(24px, 4vw, 56px);
  align-items: start;
}

.section-kicker,
.micro-label {
  display: inline-flex;
  width: fit-content;
  min-height: 28px;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-kicker {
  color: var(--kr-text-muted);
  background: var(--kr-accent-soft);
}

.micro-label {
  color: var(--kr-primary);
  background: rgba(26, 137, 23, 0.08);
}

.hero-main {
  display: grid;
  gap: 20px;
}

.hero-title {
  max-width: 11ch;
  font-size: clamp(3.6rem, 8vw, 7rem);
  line-height: 0.92;
}

.hero-deck,
.link-card-text,
.step-text,
.account-note,
.status-item {
  color: var(--kr-text-soft);
  line-height: 1.82;
}

.hero-deck {
  max-width: 44rem;
  font-size: 1.06rem;
}

.hero-bullets,
.status-list {
  list-style: none;
  display: grid;
  gap: 10px;
}

.hero-bullet,
.status-item {
  position: relative;
  padding-left: 18px;
}

.hero-bullet::before,
.status-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.82em;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--kr-primary);
}

.hero-actions,
.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.button-icon {
  margin-left: 6px;
}

.hero-side {
  min-width: 0;
}

.surface-card {
  border: 1px solid var(--kr-border);
  border-radius: 28px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(247, 247, 245, 0.9));
}

.status-card {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.account-head {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.account-avatar {
  flex-shrink: 0;
  background: var(--kr-primary);
}

.account-copy {
  display: grid;
  gap: 6px;
}

.account-name,
.guest-title {
  display: block;
  font-size: clamp(1.55rem, 3vw, 2.2rem);
  line-height: 0.98;
}

.guest-copy {
  display: grid;
  gap: 10px;
}

.danger-action {
  color: var(--kr-danger);
}

.section-head {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}

.section-title {
  max-width: 14ch;
  font-size: clamp(2.1rem, 4vw, 3.6rem);
  line-height: 0.96;
}

.link-grid,
.step-grid {
  display: grid;
  gap: 18px;
}

.link-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.link-card {
  display: grid;
  gap: 14px;
  padding: 22px;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background-color 0.18s ease;
}

.link-card:hover {
  transform: translateY(-2px);
  border-color: var(--kr-border-strong);
}

.link-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.link-card-title {
  font-size: clamp(1.7rem, 2.6vw, 2.3rem);
  line-height: 1;
}

.link-card-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: var(--kr-primary-strong);
}

.step-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.step-card {
  display: grid;
  gap: 14px;
  padding: 22px 0 0;
  border-top: 1px solid var(--kr-border);
}

.step-index {
  color: var(--kr-text-muted);
  font-size: 0.88rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.step-title {
  font-size: clamp(1.45rem, 2vw, 1.9rem);
  line-height: 1.05;
}

@media (max-width: 1024px) {
  .hero-section,
  .link-grid,
  .step-grid {
    grid-template-columns: 1fr;
  }

  .hero-title,
  .section-title {
    max-width: none;
  }
}

@media (max-width: 720px) {
  .index-page {
    padding-bottom: 28px;
  }

  .index-shell {
    gap: 28px;
  }

  .masthead,
  .masthead-nav,
  .hero-actions,
  .inline-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .status-card,
  .link-card {
    padding: 18px;
    border-radius: 22px;
  }
}
</style>
