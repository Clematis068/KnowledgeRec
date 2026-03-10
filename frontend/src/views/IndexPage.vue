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

const quickCards = [
  {
    title: '推荐首页',
    description: '先看重点内容。',
    icon: Reading,
  },
  {
    title: '热门话题',
    description: '快速扫社区趋势。',
    icon: TrendCharts,
  },
  {
    title: '知识广场',
    description: '按帖子继续深入。',
    icon: Connection,
  },
]

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
      <header class="topbar">
        <div class="brand">
          <div class="brand-mark">
            <el-icon :size="20"><Connection /></el-icon>
          </div>
          <div>
            <h1>KnowledgeRec</h1>
            <p>知识社区入口</p>
          </div>
        </div>

        <div class="topbar-actions">
          <el-button text @click="goTo('/posts')">帖子广场</el-button>
          <el-button text @click="goTo('/hot')">热门</el-button>
          <el-button v-if="!authStore.isLoggedIn" type="primary" @click="goTo('/login')">登录</el-button>
          <el-button v-else type="primary" @click="goTo('/recommend')">我的推荐</el-button>
        </div>
      </header>

      <section class="hero-card">
        <div class="hero-copy">
          <span class="hero-kicker">Index</span>
          <h2>一个更清爽的知识社区入口。</h2>
          <p>从这里进入推荐页、登录页或帖子广场。</p>

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

        <div class="hero-meta">
          <div v-if="authStore.isLoggedIn" class="user-card">
            <span class="meta-label">Account</span>
            <div class="user-head">
              <el-avatar :size="52" :icon="UserFilled" class="user-avatar" />
              <div>
                <strong>{{ authStore.username }}</strong>
                <p>已登录，可直接进入推荐页。</p>
              </div>
            </div>
            <div class="user-actions">
              <el-button plain @click="goToProfile">个人资料</el-button>
              <el-button text class="logout-button" @click="logout">退出登录</el-button>
            </div>
          </div>

          <div v-else class="meta-card">
            <span class="meta-label">状态</span>
            <strong>未登录</strong>
            <p>先登录，再进入推荐页。</p>
          </div>
        </div>
      </section>

      <section class="quick-grid">
        <article v-for="item in quickCards" :key="item.title" class="quick-card">
          <el-icon :size="20" class="quick-icon"><component :is="item.icon" /></el-icon>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.index-page {
  min-height: 100vh;
  padding: 24px;
}

.index-shell {
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.topbar,
.hero-card,
.quick-card,
.meta-card,
.user-card {
  border: 1px solid rgba(124, 58, 237, 0.12);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.74);
  box-shadow: 0 18px 44px rgba(76, 29, 149, 0.08);
  backdrop-filter: blur(18px);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark,
.quick-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, var(--kr-primary), #9f67ff);
}

.brand h1,
.hero-copy h2,
.quick-card h3,
.meta-card strong,
.user-card strong {
  letter-spacing: -0.04em;
}

.brand h1 {
  font-size: 20px;
}

.brand p,
.hero-copy p,
.quick-card p,
.meta-card p,
.user-card p {
  color: var(--kr-text-soft);
  line-height: 1.75;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) 320px;
  gap: 18px;
  padding: 30px;
}

.hero-kicker,
.meta-label {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kr-primary);
}

.hero-copy h2 {
  max-width: 12ch;
  font-size: clamp(2.6rem, 5vw, 4.6rem);
  line-height: 0.95;
}

.hero-copy p {
  margin-top: 16px;
  font-size: 16px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.button-icon {
  margin-left: 6px;
}

.hero-meta {
  display: grid;
}

.meta-card,
.user-card {
  padding: 18px;
}

.meta-card strong {
  display: block;
  margin-bottom: 8px;
  font-size: 28px;
  line-height: 1.05;
}

.user-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.user-avatar {
  background: linear-gradient(135deg, var(--kr-primary), #9f67ff);
}

.user-head strong {
  display: block;
  margin-bottom: 4px;
  font-size: 26px;
  line-height: 1.05;
}

.user-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.logout-button {
  color: #b42318;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.quick-card {
  padding: 22px;
}

.quick-card h3 {
  margin: 16px 0 8px;
  font-size: 24px;
}

@media (max-width: 900px) {
  .hero-card,
  .quick-grid {
    grid-template-columns: 1fr;
  }

  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .index-page {
    padding: 16px;
  }

  .topbar-actions,
  .hero-actions,
  .user-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
