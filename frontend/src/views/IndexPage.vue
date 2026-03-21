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
    <div class="index-center">
      <!-- 品牌区 -->
      <div class="index-brand">
        <span class="brand-icon">
          <el-icon :size="28"><Connection /></el-icon>
        </span>
        <h1 class="brand-title">知识推荐</h1>
        <p class="brand-subtitle">Knowledge Recommendation Community</p>
      </div>

      <!-- 搜索区 -->
      <div class="index-search">
        <el-input
          v-model="searchQuery"
          size="large"
          placeholder="搜索帖子、话题或作者..."
          :prefix-icon="Search"
          clearable
          @keyup.enter="handleSearch"
        />
      </div>

      <!-- 功能入口 -->
      <div class="index-entries">
        <el-button type="primary" size="large" @click="goTo('/recommend')">
          推荐首页
        </el-button>
        <el-button size="large" plain @click="goTo('/hot')">
          热门趋势
        </el-button>
      </div>

      <!-- 认证区 -->
      <div class="index-auth">
        <template v-if="authStore.isLoggedIn">
          <span class="auth-greeting">你好，{{ authStore.username }}</span>
          <el-button text @click="logout">退出</el-button>
        </template>
        <template v-else>
          <el-button size="large" @click="goTo('/login')">登录</el-button>
          <el-button size="large" type="primary" @click="goTo('/register')">注册</el-button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.index-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.index-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  max-width: 640px;
  width: 100%;
}

/* 品牌区 */
.index-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.brand-icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  color: var(--kr-primary);
  background: var(--kr-primary-soft);
  margin-bottom: 4px;
}

.brand-title {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--kr-text);
  margin: 0;
}

.brand-subtitle {
  color: var(--kr-text-muted);
  font-size: 0.9rem;
  margin: 0;
}

/* 搜索区 */
.index-search {
  width: 100%;
  max-width: 560px;
}

.index-search :deep(.el-input__wrapper) {
  border-radius: 999px;
  padding: 4px 20px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08);
}

.index-search :deep(.el-input__wrapper:hover),
.index-search :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

/* 功能入口 */
.index-entries {
  display: flex;
  gap: 16px;
}

/* 认证区 */
.index-auth {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--kr-border);
  width: 100%;
  max-width: 320px;
  justify-content: center;
}

.auth-greeting {
  color: var(--kr-text-soft);
  font-size: 0.95rem;
}

/* 响应式 */
@media (max-width: 480px) {
  .index-page {
    padding: 16px;
  }

  .index-center {
    gap: 24px;
  }

  .brand-title {
    font-size: 1.6rem;
  }

  .index-entries {
    flex-direction: column;
    width: 100%;
    max-width: 560px;
  }

  .index-entries .el-button {
    width: 100%;
  }

  .index-auth {
    max-width: 100%;
  }
}
</style>
