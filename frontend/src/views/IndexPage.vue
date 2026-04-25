<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Connection, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const searchQuery = ref('')

function handleSearch() {
  const q = searchQuery.value.trim()
  if (q) {
    router.push({ path: '/search', query: { q } })
  }
}

function goTo(route) {
  router.push(route)
}

function logout() {
  authStore.logout()
  router.push('/')
}
</script>

<template>
  <div class="index-page">
    <section class="hero-band">
      <div class="hero-shell">
        <div class="hero-copy">
          <p class="hero-eyebrow">Knowledge Graph Community</p>
          <div class="hero-title-row">
            <span class="hero-mark">
              <el-icon :size="24"><Connection /></el-icon>
            </span>
            <h1>知识社区</h1>
          </div>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="goTo('/recommend')">进入推荐</el-button>
            <el-button size="large" plain @click="goTo('/hot')">查看热门趋势</el-button>
          </div>
        </div>

      <aside class="hero-panel">
          <div class="panel-kicker">Platform Access</div>
          <div class="panel-grid">
            <div class="panel-metric">
              <span class="metric-value">24h</span>
              <span class="metric-label">实时热门刷新</span>
            </div>
            <div class="panel-metric">
              <span class="metric-value">Explainable</span>
              <span class="metric-label">实时获取推荐理由</span>
            </div>
          </div>

          <div class="index-search">
            <div class="search-kicker">Search</div>
            <label class="search-field">
              <span class="search-field-icon" aria-hidden="true">
                <el-icon :size="20"><Search /></el-icon>
              </span>
              <input
                v-model="searchQuery"
                class="search-field-input"
                type="text"
                placeholder="搜索帖子、话题或作者"
                @keyup.enter="handleSearch"
              >
            </label>
            <el-button class="search-submit" type="primary" @click="handleSearch">执行搜索</el-button>
          </div>
        </aside>
      </div>
    </section>

    <section class="signal-band">
      <div class="signal-grid">
        <article class="signal-card">
          <span class="signal-index">01</span>
          <h2>推荐</h2>
          <p>按推荐、关注、最新三部分浏览内容，还包含我的特别推荐：）</p>
        </article>
        <article class="signal-card">
          <span class="signal-index">02</span>
          <h2>趋势</h2>
          <p>查看目前最热门的帖子。</p>
        </article>
        <article class="signal-card">
          <span class="signal-index">03</span>
          <h2>个性化推荐</h2>
          <p>注册时完成兴趣选择，后续推荐都会考虑这部分内容。</p>
        </article>
      </div>
    </section>

    <section class="entry-band">
      <div class="entry-shell">
        <div class="entry-copy">
          <p class="entry-eyebrow">Community Access</p>
          <h2>{{ authStore.isLoggedIn ? `你好，${authStore.username}` : '登录后解锁个性化推荐' }}</h2>
          <p>
            {{ authStore.isLoggedIn ? '你可以继续浏览推荐、发布内容，或回到首页查看热点趋势。' : '新用户可以先注册账号，已有账号可直接登录进入推荐。' }}
          </p>
        </div>

        <div class="entry-actions">
          <template v-if="authStore.isLoggedIn">
            <el-button type="primary" size="large" @click="goTo('/recommend')">继续浏览</el-button>
            <el-button size="large" plain @click="goTo('/create-post')">发布内容</el-button>
            <el-button text size="large" @click="logout">退出登录</el-button>
          </template>
          <template v-else>
            <el-button size="large" plain @click="goTo('/login')">登录</el-button>
            <el-button size="large" type="primary" @click="goTo('/register')">创建账号</el-button>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.index-page {
  min-height: 100vh;
  background: var(--cds-background);
}

.hero-band,
.signal-band,
.entry-band {
  padding: 32px;
}

.hero-band {
  padding-top: 64px;
}

.signal-band {
  background: var(--cds-layer-01);
}

.hero-shell,
.signal-grid,
.entry-shell {
  max-width: var(--cds-layout-max-width);
  margin: 0 auto;
}

.hero-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 420px;
  gap: 32px;
  align-items: stretch;
}

.hero-copy {
  display: grid;
  gap: 24px;
  padding: 32px;
  background: var(--cds-background);
  border-top: 4px solid var(--cds-link-primary);
}

.hero-eyebrow,
.panel-kicker,
.search-kicker,
.entry-eyebrow {
  color: var(--cds-text-muted);
  font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  letter-spacing: 0.32px;
  text-transform: uppercase;
}

.hero-title-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.hero-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  background: var(--cds-background-inverse);
  color: #ffffff;
}

.hero-copy h1 {
  max-width: 13ch;
  font-size: clamp(2.75rem, 6vw, 4.75rem);
  line-height: 1.08;
}

.hero-subtitle,
.entry-copy p,
.signal-card p {
  max-width: 64ch;
  color: var(--cds-text-secondary);
  font-size: 16px;
  line-height: 1.6;
}

.hero-actions,
.entry-actions {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.hero-panel {
  display: grid;
  gap: 24px;
  align-content: start;
  padding: 32px;
  background: var(--cds-layer-01);
  border-top: 4px solid var(--cds-background-inverse);
}

.panel-grid {
  display: grid;
  gap: 12px;
}

.panel-metric {
  display: grid;
  gap: 4px;
  padding: 16px 0;
  border-top: 1px solid var(--cds-border-subtle);
}

.panel-metric:first-child {
  border-top: none;
  padding-top: 0;
}

.metric-value {
  color: var(--cds-text-primary);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 400;
}

.metric-label {
  color: var(--cds-text-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.index-search {
  display: grid;
  gap: 12px;
}

.search-field {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 0 0 0 4px;
  background: var(--cds-background);
  box-shadow: inset 0 -1px 0 var(--cds-border-subtle);
  transition: box-shadow 0.2s ease;
}

.search-field:hover {
  box-shadow: inset 0 -2px 0 var(--cds-text-primary);
}

.search-field:focus-within {
  box-shadow: inset 0 -2px 0 var(--cds-link-primary);
}

.search-field-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--cds-text-muted);
}

.search-field-input {
  width: 100%;
  height: 56px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--cds-text-primary);
  font-size: 18px;
  line-height: 1.5;
}

.search-field-input::placeholder {
  color: #a8a8a8;
}

.search-field-input:focus,
.search-field-input:focus-visible,
.search-field-input:active {
  outline: none;
  box-shadow: none;
}

.search-submit {
  width: 100%;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.signal-card {
  display: grid;
  gap: 14px;
  padding: 24px;
  background: var(--cds-background);
  border-top: 3px solid var(--cds-link-primary);
}

.signal-index {
  color: var(--cds-text-muted);
  font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  letter-spacing: 0.32px;
}

.signal-card h2,
.entry-copy h2 {
  font-size: clamp(1.5rem, 3vw, 2.5rem);
  line-height: 1.2;
}

.entry-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  padding: 24px 0 12px;
  border-top: 1px solid var(--cds-border-subtle);
}

@media (max-width: 1024px) {
  .hero-shell,
  .entry-shell,
  .signal-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero-band,
  .signal-band,
  .entry-band {
    padding: 24px 16px;
  }

  .hero-copy,
  .hero-panel,
  .signal-card {
    padding: 24px;
  }

  .hero-title-row {
    grid-template-columns: 1fr;
  }

  .hero-actions,
  .entry-actions {
    flex-direction: column;
  }

  .hero-actions .el-button,
  .entry-actions .el-button {
    width: 100%;
  }
}
</style>
